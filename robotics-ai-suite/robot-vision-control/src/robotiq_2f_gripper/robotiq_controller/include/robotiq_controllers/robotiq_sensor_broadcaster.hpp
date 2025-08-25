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

#ifndef ROBOTIQ_CONTROLLERS__STATE_BROADCASTER_HPP_
#define ROBOTIQ_CONTROLLERS__STATE_BROADCASTER_HPP_

#include <memory>
#include <string>
#include <vector>

#include "controller_interface/controller_interface.hpp"
#include "rclcpp_lifecycle/lifecycle_publisher.hpp"
#include "rclcpp_lifecycle/node_interfaces/lifecycle_node_interface.hpp"
#include "std_msgs/msg/u_int16.hpp"

namespace robotiq_controllers
{
  /// @brief This controller broadcasts the finger joint position, which is how much is opened or closed
class RobotiqSensorBroadcaster : public controller_interface::ControllerInterface
{
public:
    /// @brief Sensor broadcaster constructor
  RobotiqSensorBroadcaster();
  rclcpp::Clock clock;
  controller_interface::InterfaceConfiguration command_interface_configuration() const override;

    /// @brief Called from ros when configuring state interfaces
    /// @return result
  controller_interface::InterfaceConfiguration state_interface_configuration() const override;

  rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn on_init() override;
  controller_interface::return_type update(const rclcpp::Time & time, const rclcpp::Duration & period) override;

  rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
  on_configure(const rclcpp_lifecycle::State& previous_state) override;

  rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
  on_activate(const rclcpp_lifecycle::State& previous_state) override;

  rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn
  on_deactivate(const rclcpp_lifecycle::State& previous_state) override;

protected:
  std::vector<std::string> sensor_names_;
  rclcpp::Time last_publish_time_;
  double publish_rate_;

  std::shared_ptr<rclcpp::Publisher<std_msgs::msg::UInt16>> object_grasped_state_publisher_;
  std_msgs::msg::UInt16 object_grasped_state_msg_;
};
}  // namespace robotiq_controllers
#endif  // ROBOTIQ_CONTROLLERS__STATE_BROADCASTER_HPP_
