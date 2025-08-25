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

#pragma once

#ifndef __LINEAR_MOTION_CONTROLLER_HPP__
#define __LINEAR_MOTION_CONTROLLER_HPP__

#include "tcp_server.hpp"
#include "tcp_socket.hpp"

#include <rclcpp/rclcpp.hpp>
#include "rvc_messages/msg/pose_stamped.hpp"
#include <sensor_msgs/msg/joint_state.hpp>
#include <std_msgs/msg/u_int16.hpp>
#include <std_msgs/msg/float64_multi_array.hpp>

#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>

#include "rvc_motion_controller_interface/rvc_motion_controller_interface.hpp"

/// @brief Linear Goal Controller implementation of linear trajectory planning
/** This Goal Controller implements the simplest strategy:
 * In space: from current position to destination, the trajectory are segmented in a linear way:
 * if the goal is in TCP mode, the TCP (gripper) will travel from current to goal in a spacial linear trajectory
 * In time, the trajectory segments become shorter the closer the TCP is to the goal with a arctan profile (so not linear)
 * If the Goal Controller is in Joint Mode (as opposed to TCP Mode), the single joints angles will have the above behaviour:
 * each joint increments/decrements the angle linearly towards the goal
 **/



namespace RVCMotionController {

class URPendantMotionController : public RVCMotionControllerInterface
{
public:
    /// @brief Constructor
    URPendantMotionController();
    /// @param node ros node
    bool init(rclcpp::Node::SharedPtr node);
    double getGripperPositionFeedback(void);

private:
struct Command {
    typedef enum {
        sendPose = 0,
        receiveJoints = 65, //A
        receiveIsNear = 66, //B
        receiveGripperSensor = 67, //C
    } type;
};

    /// @brief Implementation of the pure virtual function for a linear controller
    /// @param destPose
    /// @param controllerSpeed
    void setControllerSpeed(const double controllerSpeed);
    void sendGoal(const geometry_msgs::msg::Pose destPose);

    /// @brief implementation of send goal with vector6d_t as input
    /// @param dest 6 double elements vector input
    /// @param controllerSpeed speed input
    void sendGoal(const std::vector<vector6d_t> dest, const bool recomputeTraj);
    void sendGripperPosition(double pos);

    virtual bool isGoalNear();
    rclcpp::Publisher<std_msgs::msg::Float64MultiArray>::SharedPtr  gripper_controller_goal_pub;

    URPendantMotionController &operator=(const URPendantMotionController &) = delete;


void printQuat(tf2::Quaternion q);
    private:
        std::string robot_program;
        std::string robot_ip;
        int robot_port;

        rclcpp::Subscription<rvc_messages::msg::PoseStamped>::SharedPtr m_sub_object_poses;
        std::string lastPoseString;

        std::unique_ptr<tf2_ros::Buffer> tfBuffer;
        std::shared_ptr<tf2_ros::TransformListener> tfListener;
        rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr m_pub_joint_states;
        rclcpp::Publisher<std_msgs::msg::UInt16>::SharedPtr m_pub_gripper_sensor;
        sensor_msgs::msg::JointState::SharedPtr joint_states;
        rclcpp::Node::SharedPtr node_;
        std::shared_ptr<TCPServer> tcpServer;
        std::shared_ptr<TCPServer> tcpServerPrimary;
        int clientFD;
        bool isNear;
        bool initialized;
        uint16_t gripperSensor, previousGripperSensor;
        double gripperPositionFeedback;

};
}
#endif //__LINEAR_MOTION_CONTROLLER_HPP__
