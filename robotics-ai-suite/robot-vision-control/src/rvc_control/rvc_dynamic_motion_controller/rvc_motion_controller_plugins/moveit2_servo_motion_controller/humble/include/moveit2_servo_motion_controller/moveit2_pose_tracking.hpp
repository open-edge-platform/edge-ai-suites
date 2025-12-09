/*********************************************************************
 * SPDX-License-Identifier: BSD-3-Clause
 * SPDX-FileCopyrightText: (C) 2008-2013, Willow Garage, Inc.
 * Software License Agreement (BSD License)
 *
 *  Copyright (c) 2020, PickNik Inc.
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above
 *     copyright notice, this list of conditions and the following
 *     disclaimer in the documentation and/or other materials provided
 *     with the distribution.
 *   * Neither the name of PickNik Inc. nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 *  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 *  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 *  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 *  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 *  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 *  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 *********************************************************************/
/*
   Author: Andy Zelenak
   Desc: Servoing. Track a pose setpoint in real time.
*/

#pragma once

//#include <atomic>
#include <moveit_servo/make_shared_from_pool.h>
#include <moveit_servo/servo_parameters.h>
#include <moveit_servo/servo.h>
//#include <optional>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2_ros/transform_listener.h>
#include <rclcpp/rclcpp.hpp>

#include <geometry_msgs/msg/twist_stamped.hpp>
#include <std_msgs/msg/float64.hpp>
// Conventions:
// Calculations are done in the planning_frame_ unless otherwise noted.

enum class PoseTrackingStatusCode : int8_t
{
  INVALID = -1,
  SUCCESS = 0,
  NO_RECENT_TARGET_POSE = 1,
  NO_RECENT_END_EFFECTOR_POSE = 2,
  STOP_REQUESTED = 3
};

const std::unordered_map<PoseTrackingStatusCode, std::string> POSE_TRACKING_STATUS_CODE_MAP(
    { { PoseTrackingStatusCode::INVALID, "Invalid" },
      { PoseTrackingStatusCode::SUCCESS, "Success" },
      { PoseTrackingStatusCode::NO_RECENT_TARGET_POSE, "No recent target pose" },
      { PoseTrackingStatusCode::NO_RECENT_END_EFFECTOR_POSE, "No recent end effector pose" },
      { PoseTrackingStatusCode::STOP_REQUESTED, "Stop requested" } });

/**
 * Class PoseTracking - subscribe to a target pose.
 * Servo toward the target pose.
 */
class PoseTracking
{
public:
  /** \brief Constructor. Loads ROS parameters under the given namespace. */
  PoseTracking(const rclcpp::Node::SharedPtr& node, const moveit_servo::ServoParameters::SharedConstPtr& servo_parameters,
               const planning_scene_monitor::PlanningSceneMonitorPtr& planning_scene_monitor);

  PoseTrackingStatusCode moveToPose();
  bool isGoalAchieved() { return goalAchieved; }

  /** \brief A method for a different thread to stop motion and return early from control loop */
  void stopMotion();

  /**
   * Get the End Effector link transform.
   * The transform from the MoveIt planning frame to EE link
   *
   * @param transform the transform that will be calculated
   * @return true if a valid transform was available
   */
  //bool getCommandFrameTransform(geometry_msgs::msg::TransformStamped& transform);
  bool getCommandFrameTransform(Eigen::Isometry3d& transform);

  /** \brief Re-initialize the target pose to an empty message. Can be used to reset motion between waypoints. */
  void resetTargetPose();

  // moveit_servo::Servo instance. Public so we can access member functions like setPaused()
  std::unique_ptr<moveit_servo::Servo> servo_;

private:
  /** \brief Load ROS parameters for controller settings. */
  void readROSParams();

  /** \brief Return true if a target pose has been received within timeout [seconds] */
  bool haveRecentTargetPose(const double timeout);

  /** \brief Return true if an end effector pose has been received within timeout [seconds] */
  bool haveRecentEndEffectorPose(const double timeout);

  /** \brief Check if XYZ, roll/pitch/yaw tolerances are satisfied */
  bool satisfiesPoseTolerance();


public:
  /** \brief Subscribe to the target pose on this topic */
  void setTargetPose(const geometry_msgs::msg::PoseStamped::ConstSharedPtr& msg);
  void setSpeed(const double speed);
  double getGripperPositionFeedback(void);
private:
  std::shared_ptr<rclcpp::ParameterEventHandler> param_subscriber_;


  /** \brief Use PID controllers to calculate a full spatial velocity toward a pose */
  geometry_msgs::msg::TwistStamped::ConstSharedPtr calculateTwistCommand();

  /** \brief Reset flags and PID controllers after a motion completes */
  void doPostMotionReset();

  rclcpp::Node::SharedPtr node_;
  moveit_servo::ServoParameters::SharedConstPtr servo_parameters_;
  double publish_period;

  planning_scene_monitor::PlanningSceneMonitorPtr planning_scene_monitor_;
  moveit::core::RobotModelConstPtr robot_model_;
  // Joint group used for controlling the motions
  std::string manipulator_move_group_name_;
  std::string gripper_move_group_name_;
  std::string gripper_joint_name_;

  rclcpp::WallRate loop_rate_;

  // ROS interface to Servo
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr twist_stamped_pub_;

  // Transforms w.r.t. planning_frame_
  Eigen::Isometry3d command_frame_transform_;
  rclcpp::Time command_frame_transform_stamp_ = rclcpp::Time(0, 0, RCL_ROS_TIME);
  geometry_msgs::msg::PoseStamped target_pose_;


  double controllerSpeed;
  mutable std::mutex target_pose_mtx_;

  // Subscribe to target pose
  //rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr target_pose_sub_;

  tf2_ros::Buffer transform_buffer_;
  tf2_ros::TransformListener transform_listener_;

  // Expected frame name, for error checking and transforms
  std::string planning_frame_;

  // Flag that a different thread has requested a stop.
  std::atomic<bool> stop_requested_;

  std::optional<double> angular_error_;

  tf2_ros::Buffer tfBuffer;
  tf2_ros::TransformListener listener;
  Eigen::Vector3d positional_tolerance;
  double angular_tolerance;
  bool goalAchieved;
  bool firstSetTargetReceived;

};

// using alias
using PoseTrackingPtr = std::shared_ptr<PoseTracking>;


