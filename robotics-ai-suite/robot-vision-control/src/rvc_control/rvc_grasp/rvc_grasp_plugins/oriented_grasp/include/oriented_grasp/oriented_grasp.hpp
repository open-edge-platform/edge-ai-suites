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
#include <queue>

namespace RVCControl {
class OrientedGrasp : public RVCGraspInterface
{
public:
    OrientedGrasp();
    bool init(rclcpp::Node::SharedPtr node);
    void OnMessageReceive(rvc_messages::msg::PoseStampedList::SharedPtr msg);
    bool getPreGrasp(geometry_msgs::msg::Pose & pose);
    bool getGrasp(geometry_msgs::msg::Pose & pose);
    bool isTargetAcquired() { return targetAcquired;};
    std::string getCurrentObject() { return classIdCurrent;};
private:
    double alpha_;
    geometry_msgs::msg::Quaternion filtered_orientation_;
    bool initialized_;
    geometry_msgs::msg::Quaternion filter_orientation(const geometry_msgs::msg::Quaternion& orientation);
    std::vector<geometry_msgs::msg::Pose> detectAllPossibleGrasps(const geometry_msgs::msg::Pose basePose);
    geometry_msgs::msg::Pose getBestGrasp(const std::vector<geometry_msgs::msg::Pose> grasps);
    double getPoseDistance(const geometry_msgs::msg::Pose poseA, const geometry_msgs::msg::Pose poseB);
    double computeInclination(const geometry_msgs::msg::Pose pose);
    geometry_msgs::msg::Pose ensureHorizontalPose(const geometry_msgs::msg::Pose pose);
    geometry_msgs::msg::Pose adjustVerticalInclination(const geometry_msgs::msg::Pose pose);
    int applyHysteresis(const std::vector<geometry_msgs::msg::Pose> poses, const std::vector<double> dotProducts);

    geometry_msgs::msg::Pose innerDestinationTCPPose;
    geometry_msgs::msg::Pose outerDestinationTCPPose;
    std::unique_ptr<tf2_ros::Buffer> tfBuffer;
    std::shared_ptr<tf2_ros::TransformListener> tfListener;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr marker_pub;
    visualization_msgs::msg::Marker marker;
    double pregrasp_distance;
    double grasp_z_offset;
    rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr debugPublisher;
    rclcpp::Publisher<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr debugCovariancePublisher;
    bool targetAcquired;
    std::string classIdCurrent;
    bool canPerformTFTranform;
    double grasp_distance_threshold;
    double grasp_min_horizontal_incl;
    double grasp_vertical_inclination;
    double grasp_vertical_delta_inclination;
    double grasp_reference_point_x;
    double grasp_reference_point_y;
    double grasp_reference_point_z;
    double grasp_polar_coordinate_r;
    double grasp_polar_coordinate_theta;
    double grasp_polar_coordinate_phi;
    long unsigned int hysteresis_queue_size;
    std::queue<geometry_msgs::msg::Pose> lastPoses;

protected:
    enum Axis {X, Y, Z};
    geometry_msgs::msg::Pose getRotatedPose(const geometry_msgs::msg::Pose basePose, Axis axis, double rotationAngle);
};
}
