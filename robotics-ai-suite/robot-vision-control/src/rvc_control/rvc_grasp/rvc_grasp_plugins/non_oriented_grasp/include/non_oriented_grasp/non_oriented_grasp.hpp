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

#include <rclcpp/rclcpp.hpp>
#include "rvc_grasp_interface/rvc_grasp_interface.hpp"
#include <geometry_msgs/msg/pose.hpp>
#include <visualization_msgs/msg/marker.hpp>
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>

namespace RVCControl {
class NonOrientedGrasp : public RVCGraspInterface
{
public:
    NonOrientedGrasp();
    bool init(rclcpp::Node::SharedPtr node);    
    void OnMessageReceive(rvc_messages::msg::PoseStampedList::SharedPtr msg);
    bool getPreGrasp(geometry_msgs::msg::Pose & pose);
    bool getGrasp(geometry_msgs::msg::Pose & pose);
    bool isTargetAcquired() { return targetAcquired;};
    std::string getCurrentObject() { return classIdCurrent;};
private:
    geometry_msgs::msg::Pose innerDestinationTCPPose;
    geometry_msgs::msg::Pose outerDestinationTCPPose;
    std::unique_ptr<tf2_ros::Buffer> tfBuffer;
    std::shared_ptr<tf2_ros::TransformListener> tfListener;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr marker_pub;
    visualization_msgs::msg::Marker marker;
    double pregrasp_distance;
    double grasp_z_offset;
    rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr debugPublisher;
    bool targetAcquired;
    std::string classIdCurrent;
    bool canPerformTFTranform;

};
}
