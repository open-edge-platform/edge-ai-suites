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

#include "rvc_motion_controller_interface/rvc_motion_controller_interface.hpp"
namespace RVCMotionController {
RVCMotionControllerInterface::RVCMotionControllerInterface()
    : current_control_mode(UNDEFINED),
    distance_threshold(0.0),
    distance_threshold_tcp(0.0),
    base_link(""),
    ee_link("")
{
}

bool RVCMotionControllerInterface::init(rclcpp::Node::SharedPtr node)
{
    node_ = node;
    tfBuffer = std::make_shared<tf2_ros::Buffer>(node->get_clock(), std::chrono::seconds(20));
    listener = std::make_shared<tf2_ros::TransformListener>(*tfBuffer);
    geometry_msgs::msg::TransformStamped transform;
    tf2::Stamped<tf2::Transform> tf2;

    node->declare_parameter<double>("distance_threshold", 0.1);
    node->declare_parameter<double>("distance_threshold_tcp", 0.025);
    node->declare_parameter<std::string>("base_link", "base_link");
    node->declare_parameter<std::string>("ee_link", "ee_link");
    distance_threshold = node->get_parameter("distance_threshold").as_double();
    distance_threshold_tcp = node->get_parameter("distance_threshold_tcp").as_double();
    base_link = node->get_parameter("base_link").as_string();
    ee_link = node->get_parameter("ee_link").as_string();

    int counter = 0;
    RCLCPP_INFO(node_->get_logger(), "RVCMotionControllerInterface: waiting for transform server to resolve %s to %s", base_link.c_str(), ee_link.c_str());
    while (!tfBuffer->canTransform(base_link, ee_link, rclcpp::Time()))
    {

        rclcpp::sleep_for(std::chrono::milliseconds(500));
        counter++;
        if (counter > 10)
        {
            RCLCPP_INFO(node_->get_logger(), "waiting for transform server... FAILED");
            return false;
        }
    }
    return true;
}

} //namespace
