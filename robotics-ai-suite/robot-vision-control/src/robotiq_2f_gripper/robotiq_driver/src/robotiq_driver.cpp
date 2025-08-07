// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include "robotiq_driver/robotiq_driver.hpp"
#include <vector>
#include <memory>
#include <string>

namespace robotiq_driver {
hardware_interface::CallbackReturn RobotiqPositionHardwareInterface::on_init(const HardwareInfo & system_info)
{
    gripper_position_commands_ = -1.0;
    gripper_position_commands_previous_ = -1.0;
    info_ = system_info;

    for (const hardware_interface::ComponentInfo & joint : info_.joints)
    {
        RCLCPP_DEBUG(
            rclcpp::get_logger("RobotiqDriverHW"),
            "RobotiqPositionHardwareInterface ACCEPTED joint name %s, first interface %s",
            joint.name.c_str(),
            joint.command_interfaces[0].name.c_str());

        if (joint.command_interfaces.size() != 1)
        {
            RCLCPP_FATAL(
                rclcpp::get_logger("RobotiqDriverHW"),
                "Joint '%s' has %lu command interfaces found. 1 expected.", joint.name.c_str(),
                joint.command_interfaces.size());
            return hardware_interface::CallbackReturn::ERROR;
        }

        if (joint.command_interfaces[0].name != hardware_interface::HW_IF_POSITION)
        {
            RCLCPP_FATAL(
                rclcpp::get_logger("RobotiqDriverHW"),
                "RobotiqPositionHardwareInterface Joint '%s' have %s "
                "command interfaces found as first command interface. '%s' expected.",
                joint.name.c_str(),
                joint.command_interfaces[0].name.c_str(),
                hardware_interface::HW_IF_POSITION);
            return hardware_interface::CallbackReturn::ERROR;
        }

        if (joint.state_interfaces[0].name != hardware_interface::HW_IF_POSITION)
        {
            RCLCPP_FATAL(
                rclcpp::get_logger("RobotiqDriverHW"),
                "Joint '%s' have %s state interface as first state interface. '%s' expected.",
                joint.name.c_str(),
                joint.state_interfaces[0].name.c_str(),
                hardware_interface::HW_IF_POSITION);
            return hardware_interface::CallbackReturn::ERROR;
        }
    }

    status_ = 2;
    return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface> RobotiqPositionHardwareInterface::export_state_interfaces()
{
    std::vector<hardware_interface::StateInterface> state_interfaces;

    for (size_t i = 0; i < info_.joints.size(); ++i)
    {
        RCLCPP_DEBUG(
            rclcpp::get_logger("RobotiqDriverHW"),
            "RobotiqPositionHardwareInterface::export_state_interfaces: JOINT: %s",
            info_.joints[i].name.c_str());

        state_interfaces.emplace_back(
            hardware_interface::StateInterface(
                info_.joints[i].name, hardware_interface::HW_IF_POSITION, &gripper_position_));
    }

    for (auto & sensor : info_.sensors)
    {
        for (uint j = 0; j < sensor.state_interfaces.size(); ++j)
        {
            RCLCPP_DEBUG(
                rclcpp::get_logger("RobotiqDriverHW"),
                "RobotiqPositionHardwareInterface::export_state_interfaces: SENSOR %s",
                sensor.name.c_str());
        }
    }

    state_interfaces.emplace_back(
        hardware_interface::StateInterface(
            "gripper",
            "object_grasped",
            &object_grasped_));
    return state_interfaces;
}

std::vector<hardware_interface::CommandInterface> RobotiqPositionHardwareInterface::export_command_interfaces()
{
    std::vector<hardware_interface::CommandInterface> command_interfaces;

    for (size_t i = 0; i < info_.joints.size(); ++i)
    {
        RCLCPP_DEBUG(
            rclcpp::get_logger("RobotiqDriverHW"),
            "RobotiqPositionHardwareInterface::export_command_interfaces: SENSOR %s",
            info_.joints[i].name.c_str());

        if (info_.joints[i].name == "gpio" || info_.joints[i].name == "speed_scaling")
        {
            continue;
        }

        command_interfaces.emplace_back(
            hardware_interface::CommandInterface(
                info_.joints[i].name, hardware_interface::HW_IF_POSITION, &gripper_position_commands_));
    }

    return command_interfaces;
}

hardware_interface::CallbackReturn RobotiqPositionHardwareInterface::on_activate(
    const rclcpp_lifecycle::State & previous_state)
{
    RCLCPP_INFO(rclcpp::get_logger("RobotiqDriverHW"), "on_activate ... ");
    // NOTE: the read is actively waiting to receive a response from the socket after sending the request.
    status_ = 1;
    // this take long and as this is running in the same process of the main robot, that get slowed down
    // a lot and complains of loss packets... so i am decoupling it like this:
    position_poll_thread_ =
        std::make_shared<std::thread>(std::bind(&RobotiqPositionHardwareInterface::communicateWithGripper, this) );

    RCLCPP_INFO(
        rclcpp::get_logger(
            "RobotiqDriverHW"), "RobotiqDriverHW driver successfully started!");

    return hardware_interface::CallbackReturn::SUCCESS;
}

bool checkSocket(int socket_fd)
{
    int value = 0;
    socklen_t len = sizeof(value);

    if (getsockopt(socket_fd, SOL_SOCKET, SO_ERROR, &value, &len) == -1)
    {
        RCLCPP_ERROR(
            rclcpp::get_logger("RobotiqDriverHW"),
            "error getting socket error code: %s, value %d",
            strerror(errno),value);
        return false;
    }

    return true;
}

float RobotiqPositionHardwareInterface::getGripperPosition()
{
    char buffer[64] = {0};
    std::ostringstream stringStream;
    stringStream << "GET POS";
    std::string copyOfStr = stringStream.str();

    int ret =send(sock, copyOfStr.c_str(), strlen(copyOfStr.c_str()), 0);
    if ( ret <0 || !checkSocket(sock))
    {
        RCLCPP_FATAL(rclcpp::get_logger("RobotiqDriverHW"), "Socket error: %d", ret);
        return -1.0;
    }
    ret = recv(sock, buffer, 64, 0);
    if ( ret <0 || !checkSocket(sock))
    {
        RCLCPP_FATAL(rclcpp::get_logger("RobotiqDriverHW"), "Socket error: %d", ret);        
        return -1.0;
    }


    return (static_cast<double>(atol(&buffer[0]))) / 255.0f;

}

void RobotiqPositionHardwareInterface::setGripperPosition(double value)
{
    std::ostringstream stringStream;
    stringStream << "SET POS " << (unsigned int)(value * 255.0) << "\n";
    std::string copyOfStr = stringStream.str();

    auto ret = send(sock, copyOfStr.c_str(), strlen(copyOfStr.c_str()), 0);

    if ( ret <0 || !checkSocket(sock))
    {
        return;
    }

    char buffer[64] = {0};
    ret = recv(sock, buffer, 64, 0);

    if ( ret <0 || !checkSocket(sock))
    {
        return;
    }

    RCLCPP_DEBUG(rclcpp::get_logger("RobotiqDriverHW"), "write %s return %s", copyOfStr.c_str(), buffer);
}

void RobotiqPositionHardwareInterface::communicateWithGripper(void)
{
    const int maxBufferSize = 64;
    try
    {
        while (status_ == 1)
        {
            usleep(500000);

            std::string robot_ip = info_.hardware_parameters["gripper_ip"];
            RCLCPP_INFO(rclcpp::get_logger("RobotiqDriverHW"), "Gripper ip: %s", robot_ip.c_str());
            struct sockaddr_in serv_addr;

            if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0)
            {
                RCLCPP_FATAL(rclcpp::get_logger("RobotiqDriverHW"), "\n Socket creation error \n");
                continue;
            }

            serv_addr.sin_family = AF_INET;
            serv_addr.sin_port = htons(PORT);

            // Convert IPv4 and IPv6 addresses from text to binary form
            if (inet_pton(AF_INET, robot_ip.c_str(), &serv_addr.sin_addr) <= 0)
            {
                RCLCPP_FATAL(rclcpp::get_logger("RobotiqDriverHW"), "\nInvalid address/ Address not supported \n");
                continue;
            }

            if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0)
            {
                RCLCPP_FATAL(
                    rclcpp::get_logger("RobotiqDriverHW"),
                    "Connection to the gripper FAILED at %s\n", robot_ip.c_str());
                continue;
            }

            RCLCPP_INFO(
                rclcpp::get_logger("RobotiqDriverHW"),
                "Connection to the gripper succeded at %s", robot_ip.c_str());
            char buffer[maxBufferSize] = {0};

            while (status_ == 1)
            {
                if (!checkSocket(sock))
                {
                    break;
                }

                gripper_position_ = getGripperPosition();
                memset(buffer, 0, maxBufferSize);

                std::string str("GET OBJ");

                if (!checkSocket(sock))
                {
                    break;
                }

                auto ret = send(sock, str.c_str(), strlen(str.c_str()), 0);

                if ( ret <0 || !checkSocket(sock))
                {
                    break;
                }

                ret = recv(sock, buffer, maxBufferSize, 0);

                if ( ret <0 || !checkSocket(sock))
                {
                    break;
                }


                object_grasped_ = atol(&buffer[0]);

                if ((gripper_position_commands_ != gripper_position_commands_previous_) &&
                    (status_ == 1))
                {
                    setGripperPosition(gripper_position_commands_);
                    gripper_position_commands_previous_ = gripper_position_commands_;
                }

                usleep(50000);
            }

            if (!checkSocket(sock))
            {
                continue;
            }

            close(sock);
        }
    } catch (std::exception & e)
    {
        std::cerr << "Exception caught : " << e.what() << std::endl;
        RCLCPP_ERROR(rclcpp::get_logger("RobotiqDriverHW"), "EXCEPTION: %s ", e.what());
    }

    RCLCPP_INFO(rclcpp::get_logger("RobotiqDriverHW"), "EXITING POLL THREAD?????");
}

hardware_interface::CallbackReturn RobotiqPositionHardwareInterface::on_deactivate(
    const rclcpp_lifecycle::State & previous_state)
{
    RCLCPP_INFO(rclcpp::get_logger("RobotiqDriverHW"), "deactivating ...please wait...");

    status_ = 0;

    RCLCPP_INFO(rclcpp::get_logger("RobotiqDriverHW"), "System successfully stopped!");
    return hardware_interface::CallbackReturn::SUCCESS;
}

return_type RobotiqPositionHardwareInterface::read(const rclcpp::Time &, const rclcpp::Duration &)
{
    return return_type::OK;
}

return_type RobotiqPositionHardwareInterface::write(const rclcpp::Time &, const rclcpp::Duration &)
{
    return return_type::OK;
}

}

#include "pluginlib/class_list_macros.hpp"

PLUGINLIB_EXPORT_CLASS(robotiq_driver::RobotiqPositionHardwareInterface, hardware_interface::SystemInterface)
