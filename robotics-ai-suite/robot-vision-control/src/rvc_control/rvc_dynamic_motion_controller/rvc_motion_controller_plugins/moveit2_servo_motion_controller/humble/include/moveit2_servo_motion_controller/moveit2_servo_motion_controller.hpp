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

#ifndef __MOVEIT2_SERVO_MOTION_CONTROLLER_HPP__
#define __MOVEIT2_SERVO_MOTION_CONTROLLER_HPP__

#include "rvc_motion_controller_interface/rvc_motion_controller_interface.hpp"

#include <std_msgs/msg/int8.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>

#include <moveit_servo/servo.h>
#include "moveit2_pose_tracking.hpp"
#include <moveit_servo/servo_parameters.h>

#include <moveit/planning_scene_interface/planning_scene_interface.h>
#include <std_msgs/msg/float64_multi_array.hpp>

/** This Goal Controller uses moveit2 servo
 **/

namespace RVCMotionController {
class Moveit2ServoMotionController : public RVCMotionControllerInterface
{
public:
    /// @brief Constructor
    /// @param node ros node
    Moveit2ServoMotionController ();
    virtual ~Moveit2ServoMotionController();
    bool init ( rclcpp::Node::SharedPtr node );


    /// @brief Implementation of the pure virtual function for a linear controller
    /// @param destPose
    /// @param controllerSpeed
    void setControllerSpeed(const double controllerSpeed);
    void sendGoal ( const geometry_msgs::msg::Pose destPose);

    /// @brief implementation of send goal with vector6d_t as input
    /// @param dest 6 double elements vector input
    /// @param controllerSpeed speed input
    void sendGoal ( const std::vector<vector6d_t> dest, const bool recomputeTraj );
    void sendGripperPosition(double pos);
    double getGripperPositionFeedback(void)
    {
        return poseTracker->getGripperPositionFeedback();
    }
    virtual bool isGoalNear();
private:
    std::unique_ptr<PoseTracking> poseTracker;
    bool initialized;

    std::shared_ptr<std::thread> move_to_pose_thread;
    std::shared_ptr<moveit::core::RobotState> kinematic_state ;

    moveit_servo::StatusCode status_ = moveit_servo::StatusCode::INVALID;
    rclcpp::Subscription<std_msgs::msg::Int8>::SharedPtr sub_;
    void statusCB ( const std_msgs::msg::Int8::ConstSharedPtr msg );

    geometry_msgs::msg::PoseStamped currentPose;
    rclcpp::Publisher<std_msgs::msg::Float64MultiArray>::SharedPtr  gripper_controller_goal_pub;
};
}
#endif //__MOVEIT2_SERVO_MOTION_CONTROLLER_HPP__

