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

#ifndef __RVC_MOTION_CONTROLLER_INTERFACE_HPP__
#define __RVC_MOTION_CONTROLLER_INTERFACE_HPP__

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/macros.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "geometry_msgs/msg/pose.hpp"
#include "tf2/LinearMath/Vector3.h"

#include "tf2_ros/transform_listener.h"
#include <sensor_msgs/msg/joint_state.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2_ros/buffer.h>

using vector6d_t = std::array<double, 6>;
using namespace geometry_msgs;

/// @brief Any defined controllers have to inerit from this to be used in the StateMachine node
namespace RVCMotionController
{
class RVCMotionControllerInterface
{
public:
    RCLCPP_SMART_PTR_ALIASES_ONLY(RVCMotionControllerInterface)

    /**
     * @brief initialization api
     * 
     * @param node the rclcpp::Node associated
     * @return true if succeded
     * @return false if failed
     */
    virtual bool init(rclcpp::Node::SharedPtr node);

    /**
     * @brief Set the Controller Speed 
     * 
     * @param controllerSpeed new speed
     */
    virtual void setControllerSpeed(const double controllerSpeed) = 0;

    /// @brief Send the target goal Pose to the controller. Pure virtual function
    /// @param destPose target Pose
    /// @param controllerSpeed Speed of the robot
    virtual void sendGoal(const geometry_msgs::msg::Pose destPose) = 0;
    /// @brief Send the target angles to the controller. Deprecated.
    /// @param dest 6 joint angles in radians
    /// @param controllerSpeed Speed of the robot
    virtual void sendGoal(std::vector<vector6d_t> dest, const bool recomputeTraj) = 0;
    /**
     * @brief send the gripper position
     * 
     * @param position 
     */
    virtual void sendGripperPosition(double position) = 0;
    /// @brief Controller gives an indication if the target is close enough
    /// @return true if the goal is close enough

    virtual bool isGoalNear() = 0;
    /// @brief returns current value of the gripper position.
    /// @return current value of the gripper position.
    virtual double getGripperPositionFeedback(void) = 0;

    /// @brief Virtual Destructor
    virtual ~RVCMotionControllerInterface() {};

protected:
    /// @brief  Empty Constructor for pluginlib
    /// @param node a rclcpp node shared pointer
    RVCMotionControllerInterface();

    /// @brief enumeration with the different control modes, used in current_control_mode
    enum
    {
        UNDEFINED = 0,
        JOINT_CONTROL_MODE,
        TCP_CONTROL_MODE
    };

    /// @brief ros node
    rclcpp::Node::SharedPtr node_;

    /// @brief previous configured goal in Joint Space
    vector6d_t lastJointGoal;
    /// @brief previous configured goal in Cartesian Space
    geometry_msgs::msg::Pose lastTCPGoal;

    /// @brief internal state representing if controller is currently in Joint or Cartesian space control mode
    int current_control_mode;

private:
    /// @brief  Private copy constructor
    RVCMotionControllerInterface(const RVCMotionControllerInterface&);

    /// @brief Private copy assignment operator
    RVCMotionControllerInterface& operator=(const RVCMotionControllerInterface&);

    /// @brief this variable publicly exposes the current value of the gripper position.
    double distance_threshold, distance_threshold_tcp;
    geometry_msgs::msg::Pose currentTCPPose;

    std::shared_ptr<tf2_ros::Buffer> tfBuffer;
    std::shared_ptr<tf2_ros::TransformListener> listener;
    std::string base_link, ee_link;
};
} //namespace RVCMotionController

#endif //__RVC_MOTION_CONTROLLER_INTERFACE_HPP__
