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

#pragma once
#ifndef ROBOTIQ_DRIVER__HARDWARE_INTERFACE_HPP_
#define ROBOTIQ_DRIVER__HARDWARE_INTERFACE_HPP_

// System
#include <memory>
#include <string>
#include <vector>

#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "hardware_interface/visibility_control.h"

#include "rclcpp/rclcpp.hpp"

using hardware_interface::HardwareInfo;
using hardware_interface::return_type;


#include <stdio.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#define PORT 63352

namespace robotiq_driver {
/// @brief Robotiq position interface implementing the ros hardware interface
class RobotiqPositionHardwareInterface : public hardware_interface::SystemInterface
{
public:
    RCLCPP_SHARED_PTR_DEFINITIONS(RobotiqPositionHardwareInterface);
    /// @brief Configuration to be performed when ros framework calls this function
    hardware_interface::CallbackReturn on_init(const hardware_interface::HardwareInfo & system_info) final;
    /// @return vector of interfaces
    std::vector<hardware_interface::StateInterface> export_state_interfaces() final;

    /// @brief export command interfaces bound to this driver (finger_joint)
    /// @return vector of interfaces
    std::vector<hardware_interface::CommandInterface> export_command_interfaces() final;

    /**
     * @brief Called by framework on driver activation
     * 
     * @param previous_state 
     * @return hardware_interface::CallbackReturn returns status of activation
     */
    hardware_interface::CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) final;
    /**
     * @brief Called by framework on driver deactivation
     * 
     * @param previous_state 
     * @return hardware_interface::CallbackReturn returns status of deactivation
     */
    hardware_interface::CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) final;
    /// @return controller name
    std::string get_name() const final
    {
        return info_.name;
    }

    /**
     * @brief read API implementation
     * 
     * @return return_type return to the framework if operation was successful
     */

    return_type read(const rclcpp::Time &, const rclcpp::Duration &) final;
    /**
     * @brief write API implementation
     * 
     * @return return_type return to the framework if operation was successful
     */
    return_type write(const rclcpp::Time &, const rclcpp::Duration &) final;


protected:
    float getGripperPosition();
    void setGripperPosition(double value);
    double gripper_position_commands_,gripper_position_commands_previous_, gripper_position_;
    double object_grasped_;
    HardwareInfo info_;
    int status_;

private:
    int sock;
    rclcpp::TimerBase::SharedPtr position_poll_timer_;

    std::shared_ptr<std::thread> position_poll_thread_;
    void communicateWithGripper(void);

};
}

#endif // ROBOTIQ_DRIVER__HARDWARE_INTERFACE_HPP_
