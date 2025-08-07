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

#ifndef __STATE_MACHINE_HPP__
#define __STATE_MACHINE_HPP__

#include "rclcpp/rclcpp.hpp"

#include <std_srvs/srv/trigger.hpp>
#include "geometry_msgs/msg/pose.hpp"
#include "std_msgs/msg/float64_multi_array.hpp"
#include "std_msgs/msg/byte.hpp"
#include "std_msgs/msg/bool.hpp"
#include "std_msgs/msg/u_int16.hpp"

#include "rvc_motion_controller_interface/rvc_motion_controller_interface.hpp"

#include "gui_settings/msg/gui_settings_msg.hpp"
#include "rvc_messages/msg/pose_stamped_list.hpp"
#include "rvc_messages/msg/pose_stamped.hpp"
#include "state_machine_msgs/msg/state_machine_msgs.hpp"
#include "rvc_grasp_interface/rvc_grasp_interface.hpp"

using namespace RVCMotionController;
using vector6d_t = std::array<double, 6>;

/// @brief /// @brief StateMachine Class will handle all the use case of the demo giving commands to the robot controllers
class StateMachine : public rclcpp::Node
{
private:

    /// @brief internal run function to be called on a fixed timer to handle the state machine
    void run(void);

    /// @brief Callback upon receiving a new message from the marker server, some controls on rviz2 has changed
    /// @param Message received from the rviz2 gui, it brings all the parameters, even if not changed
    void settingsCallback(const gui_settings::msg::GuiSettingsMsg::SharedPtr);
    /// @brief Simple wrapper to change state, useful if debug needed
    /// @param newState
    void switchState(int newState);

    rclcpp::Publisher<std_msgs::msg::UInt16>::SharedPtr state_machine_pub;
    rclcpp::TimerBase::SharedPtr state_machine_timer_;

    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr target_picked_pub;
    rclcpp::Subscription<std_msgs::msg::UInt16>::SharedPtr gripperDetectionSubscriber;
    rclcpp::Subscription<gui_settings::msg::GuiSettingsMsg>::SharedPtr settingsSubscriber;

    std::chrono::steady_clock::time_point gripperCloseCommandWasSentAt;
    bool gripperCloseCommandWasSent;

    int objectDetected;
    int enableController;
    double controllerSpeed;
    double controllerSpeedGUI;
    int sendToSafePos;
    std::string object_pose_topic;
    enum
    {
        start_state = 0,
        init_state = 1,
        sync_state = 2 ,
        going_to_safe_position_state = 3,
        going_to_intermediate_drop_object_state = 4 ,
        going_to_drop_object_state = 5 ,
        tracking_outer_point_state = 6,
        tracking_inner_point_state = 7,
        closing_gripper_state = 8 ,
        opening_gripper_state = 9,
    };
    const std::string stateName[10] =
    {
        "start_state",
        "init_state",
	"sync_state",
        "going_to_safe_position_state",
        "going_to_intermediate_drop_object_state",
        "going_to_drop_object_state",
        "tracking_outer_point_state",
        "tracking_inner_point_state",
        "closing_gripper_state",
        "opening_gripper_state",
    };

    uint16_t state;
    uint16_t lastPublishedState;
    std::string lastDropObject;

    bool defectiveObjectDetected;

    bool enableFullCycle;
    bool enableTrackingOnCloseGripper;

    std::map<std::string, geometry_msgs::msg::Pose> objectPoseMap;
    geometry_msgs::msg::Pose safe_point_pose;
    geometry_msgs::msg::Pose drop_pose;
    vector6d_t safe_point_joints;

    RVCMotionControllerInterface *motionController;
    RVCControl::RVCGraspInterface *graspPlugin;

    void openGripper();
    void closeGripper();
    rclcpp::Subscription<std_msgs::msg::UInt16>::SharedPtr actualControllerSubscriber;
    std::string globalObjectClassId;
    bool receivedSettings;
    bool firstGraspReceived;
    geometry_msgs::msg::Pose outerDestinationTCPPose;
    geometry_msgs::msg::Pose innerDestinationTCPPose;


public:
    /// @brief Constructor, parameterless
    StateMachine();
    /// @brief Destructor
    ~StateMachine();
    /// @brief second stage initializer, called after the goal controller has been initialized
    /// @param motionController pointer to the instatiaded object of interface RVCMotionControllerInterface
    /// @return true if initialization successfull
    bool init(RVCMotionControllerInterface *motionController, RVCControl::RVCGraspInterface *graspPlugin);
};

#endif //__STATE_MACHINE_HPP__
