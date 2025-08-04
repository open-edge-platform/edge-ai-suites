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

#include "rvc_grasp_interface/rvc_grasp_interface.hpp"

namespace RVCControl {
void RVCGraspInterface::RvcMessagesCallback(const rvc_messages::msg::PoseStampedList::SharedPtr msgList)
{
    this->OnMessageReceive(std::move(msgList));
}

bool RVCGraspInterface::init(rclcpp::Node::SharedPtr node)
{
    node_ = std::move(node);
    node_->declare_parameter<std::string>("object_pose_topic", "object_poses");

    auto object_pose_topic = node_->get_parameter("object_pose_topic").as_string();
    RCLCPP_INFO(
        node_->get_logger(), "Tracking object detection topic at %s",
        object_pose_topic.c_str() );

    base_link = node_->get_parameter("base_link").as_string();
    ee_link = node_->get_parameter("ee_link").as_string();

    auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw( rmw_qos_profile_sensor_data),
                           rmw_qos_profile_sensor_data);
    RvcMessagesSubscriber = node_->create_subscription<rvc_messages::msg::PoseStampedList>(
        object_pose_topic, qos, std::bind(
            &RVCGraspInterface::RvcMessagesCallback, this,
            std::placeholders::_1) );
    return true;
}

}
