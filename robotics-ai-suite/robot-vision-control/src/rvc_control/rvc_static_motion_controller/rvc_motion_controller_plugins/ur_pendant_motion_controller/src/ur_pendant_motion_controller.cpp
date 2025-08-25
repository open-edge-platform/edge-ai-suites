// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: (C) 2025 Intel Corporation
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

#include "ur_pendant_motion_controller/ur_pendant_motion_controller.hpp"
#include <ament_index_cpp/get_package_share_directory.hpp>

using namespace std::chrono_literals;

namespace RVCMotionController {


static const std::string SERVER_IP_REPLACE("{{SERVER_IP_REPLACE}}");
static const std::string SERVER_PORT_REPLACE("{{SERVER_PORT_REPLACE}}");


URPendantMotionController::URPendantMotionController()
  : 
    robot_program(""),
    robot_ip("1.2.3.4"),
    robot_port(30002),
    clientFD(-1),    
    isNear(false),
    initialized(false)
{
}

double URPendantMotionController::getGripperPositionFeedback(void)
{
    return gripperPositionFeedback;
}

bool URPendantMotionController::isGoalNear()
{
    if (!initialized)
    {
        RCLCPP_FATAL(rclcpp::get_logger("PP"), "URPendantMotionController NOT INITIALIZED!");
        return false;
    }

    RCLCPP_DEBUG_THROTTLE(
        node_->get_logger(),
        *node_->get_clock(), 1000, "URPendantMotionController::isGoalNear(): RESULT: %d", isNear);
    return isNear;
}

bool URPendantMotionController::init(rclcpp::Node::SharedPtr node)
{
    node_ = std::move(node);
    auto res = RVCMotionControllerInterface::init(node_);

    RCLCPP_INFO(rclcpp::get_logger("URPMC"), "URPendantMotionController init ret: %d", res);

    if (!res)
        return res;

    node_->declare_parameter<std::string>("robot_program", std::string("robot_program.txt"));
    node_->declare_parameter<std::string>("robot_ip", std::string("10.62.226.75"));
    node_->declare_parameter<std::string>("server_ip", std::string("127.0.0.1"));
    node_->declare_parameter<int>("server_port", 50005);
    node_->declare_parameter<int>("robot_port", 30002);
    std::string package_share_directory = ament_index_cpp::get_package_share_directory("ur_pendant_motion_controller");
    robot_program = package_share_directory + "/resources/" + node_->get_parameter("robot_program").as_string();

    auto server_ip = node_->get_parameter("server_ip").as_string();
    auto server_port = node_->get_parameter("server_port").as_int();
    robot_ip = node_->get_parameter("robot_ip").as_string();
    robot_port = node_->get_parameter("robot_port").as_int();
    std::ifstream ifs(robot_program);

    if (ifs.fail())
    {
        RCLCPP_FATAL(rclcpp::get_logger("URPMC"), "CANNOT FIND %s", robot_program.c_str());
        return false;
    }

    std::string prog((std::istreambuf_iterator<char>(ifs)), (std::istreambuf_iterator<char>()));

    while (prog.find(SERVER_IP_REPLACE) != std::string::npos)
    {
        prog.replace(prog.find(SERVER_IP_REPLACE), SERVER_IP_REPLACE.length(), server_ip);
    }

    while (prog.find(SERVER_PORT_REPLACE) != std::string::npos)
    {
        prog.replace(prog.find(SERVER_PORT_REPLACE), SERVER_PORT_REPLACE.length(), std::to_string(server_port));
    }

    // RCLCPP_INFO_STREAM(node_->get_logger(), "FILE: " << robot_program << " CONTENT:\n" << prog);
    TCPSocket sock;
    RCLCPP_INFO_STREAM(rclcpp::get_logger("URPMC"), "Connecting to: " << robot_ip << ":" << std::to_string(robot_port) );
    sock.setup(robot_ip, robot_port);
    size_t len = prog.size();
    const uint8_t * data = reinterpret_cast<const uint8_t *>(prog.c_str());
    size_t written;
    RCLCPP_INFO_STREAM(rclcpp::get_logger("URPMC"), "Writing content...");

    sock.write(data, len, written);
    RCLCPP_INFO_STREAM(rclcpp::get_logger("URPMC"), "Writing content...DONE");
    unsigned char readbuf[1024];
    long unsigned int reallyread;

    // flush sock
    sock.read(readbuf, 1024, reallyread);


    tfBuffer = std::make_unique<tf2_ros::Buffer>(node_->get_clock() );
    tfListener = std::make_shared<tf2_ros::TransformListener>(*tfBuffer);


    m_pub_joint_states =
        node_->create_publisher<sensor_msgs::msg::JointState>(
        "joint_states",
        rclcpp::SystemDefaultsQoS());
    m_pub_gripper_sensor = node_->create_publisher<std_msgs::msg::UInt16>(
        "gripper_sensor_broadcaster/object_grasped",
        rclcpp::SystemDefaultsQoS());

    joint_states = std::make_shared<sensor_msgs::msg::JointState>();
    joint_states->name.push_back("shoulder_pan_joint");
    joint_states->name.push_back("shoulder_lift_joint");
    joint_states->name.push_back("elbow_joint");
    joint_states->name.push_back("wrist_1_joint");
    joint_states->name.push_back("wrist_2_joint");
    joint_states->name.push_back("wrist_3_joint");
    joint_states->name.push_back("finger_joint");

    //initial: safe position (home)
    lastPoseString = "( 0.347, -0.271, 0.45, 1.529, 0.578, 0.568 )";

    tcpServer = std::make_shared<TCPServer>(50005);

    std::function<void(const int)> connectLambda = [this](const int fd)
        {
            RCLCPP_INFO(rclcpp::get_logger("TCPServer"), " CLIENT CONNECTED with fd %d!", fd);
            clientFD = fd;
            return fd;
        };


    std::function<void(const int, char *,
        int)> receivedMessageLambda = [this](const int clientFd, char * msg, int length)
        {
            (void)clientFd;

            std::string message = std::string(msg);
            std::stringstream ss(message);
            char command = ' ';

            while(!ss.eof())
            {

                ss >> command;

                if (ss.fail()) {
                    RCLCPP_FATAL(
                            rclcpp::get_logger(
                                "URPMC"), "1 receivedMessageLambda: Extraction failed! State of stringstream: %s ", ss.str().c_str());
                    return;
                }

                switch (command) {
                case Command::sendPose:
                    {
                        RCLCPP_INFO(
                            rclcpp::get_logger(
                                "URPMC"), "receivedMessageLambda: CLIENT sent command sendPose: %d, replying with: %s", msg[0],
                            lastPoseString.c_str());
                    }
                    break;
                case Command::receiveJoints:
                    {
                        joint_states->position.clear();

                        float s;
                        for (int i =0; i < 7; i++)
                        {
                            ss >> s;
                            if (ss.fail()) {
                                RCLCPP_INFO(
                                        rclcpp::get_logger(
                                            "URPMC"), "receivedMessageLambda: receiveJoints : Extraction failed! State of stringstream: %s ", ss.str().c_str());
                                return;
                            }

                            joint_states->position.push_back(s);

                            if (ss.peek() == ',')
                            {
                                ss.ignore();
                            }
                        }

                        if (joint_states->position.size() > 6)
                        {
                            gripperPositionFeedback = joint_states->position[6];
                        }

                        joint_states->header.stamp = node_->now();
                        m_pub_joint_states->publish(*joint_states);

                    }

                    break;
                case Command::receiveIsNear:
                    {
                        ss >> isNear;
                        if (ss.fail()) {
                            RCLCPP_INFO(rclcpp::get_logger(
                                "URPMC"), "receivedMessageLambda: RECEIVEISNEAR received: Extraction failed! State of stringstream: %s ", ss.str().c_str());                            
                            return;
                        }                        
                    }
                    break;
                case Command::receiveGripperSensor:
                    {

                        ss >> gripperSensor;

                        if (gripperSensor != previousGripperSensor)
                        {
                            previousGripperSensor = gripperSensor;
                            std_msgs::msg::UInt16 object_grasped_state_msg;
                            object_grasped_state_msg.data = gripperSensor;
                            m_pub_gripper_sensor->publish(object_grasped_state_msg);
                        }
                    }
                    break;

                default:
                RCLCPP_INFO(rclcpp::get_logger("URPMC"),"Skipping unknown message %s",msg);
                    break;
                }

            }
            return;
        };


    tcpServer->setConnectCallback(std::move(connectLambda));
    tcpServer->setMessageCallback(std::move(receivedMessageLambda));
    tcpServer->start();


    initialized = res;

    return res;
}

void URPendantMotionController::printQuat(tf2::Quaternion q)
{
    std::stringstream stream;
    stream << std::fixed << std::setprecision(3) << " ( " <<
        " 1.0, " <<     //COMMAND MOVE TO POSE == 1.0
        q.getAngle() * q.getAxis()[0] << ", " <<
        q.getAngle() * q.getAxis()[1] << ", " <<
        q.getAngle() * q.getAxis()[2] << " )";
    lastPoseString = stream.str();
    RCLCPP_INFO(
        rclcpp::get_logger(
            "XXX"), " ==> sending ===> (if home, it should be 0.463, -0.401, 0.445, R: 1.528, 0.576, 0.584) ===> %s",
        lastPoseString.c_str());
}

void URPendantMotionController::setControllerSpeed(const double controllerSpeed)
{
    (void)controllerSpeed;
    RCLCPP_INFO(rclcpp::get_logger("URpendant"), "setControllerSpeed unimplemented!");
}

void URPendantMotionController::sendGoal(const geometry_msgs::msg::Pose destPose)
{
    if (clientFD == -1)
    {
        return;
    }
    isNear = false;

    static geometry_msgs::msg::Pose previousPose;

    if ((previousPose.position.x == destPose.position.x) &&
        (previousPose.position.y == destPose.position.y) &&
        (previousPose.position.z == destPose.position.z))
    {
        return;
    }

    previousPose = destPose;

    tf2::Quaternion q;
    fromMsg(destPose.orientation, q);

    tf2::Quaternion rotq(q.y(), -q.x(), -q.w(), q.z());

    RCLCPP_DEBUG(
        rclcpp::get_logger("XXX"), "SOURCE QUATERNION ===> %f %f %f %f, angle %f axis %f %f %f",
        q.x(), q.y(), q.z(), q.w(), q.getAngle(), q.getAxis()[0], q.getAxis()[1], q.getAxis()[2]);
    q = rotq;


    std::stringstream stream;
    stream << std::fixed << std::setprecision(3) << " ( " <<
        " 1.0, " <<     //COMMAND MOVE TO POSE == 1.0
        -destPose.position.x << ", " <<
        -destPose.position.y << ", " <<
        destPose.position.z << ", " <<
        q.getAngle() * q.getAxis()[0] << ", " <<
        q.getAngle() * q.getAxis()[1] << ", " <<
        q.getAngle() * q.getAxis()[2] << " )";
    lastPoseString = stream.str();
    RCLCPP_DEBUG(
        rclcpp::get_logger(
            "XXX"), " ==> sending ===> (if home, it should be 0.463, -0.401, 0.445, R: 1.528, 0.576, 0.584) ===> %s",
        lastPoseString.c_str());


    long unsigned written;
    tcpServer->write(clientFD, (uint8_t *) lastPoseString.c_str(), lastPoseString.length(), written);
}

void URPendantMotionController::sendGoal(const std::vector<vector6d_t> dest, const bool republish)
{
    (void)dest;
    (void)republish;
}

void URPendantMotionController::sendGripperPosition(double pos)
{
    RCLCPP_INFO(node_->get_logger(), " received gripper pos %f", pos);

    std::stringstream stream;
    stream << std::fixed << std::setprecision(3) << " ( " << " 2.0, " << pos << " )";
    auto gripperPos = stream.str();
    RCLCPP_INFO(rclcpp::get_logger("XXX"), " ==> sending  ===> %s", gripperPos.c_str());

    long unsigned written;
    tcpServer->write(clientFD, (uint8_t *) gripperPos.c_str(), gripperPos.length(), written);

}

}

#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(
    RVCMotionController::URPendantMotionController,
    RVCMotionController::RVCMotionControllerInterface)
