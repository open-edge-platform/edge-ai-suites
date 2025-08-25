// SPDX-License-Identifier: Apache-2.0
/*
Copyright (C) 2025 Intel Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
*/

#ifndef GoalCatcher_H
#define GoalCatcher_H
#include <functional>
#include <future>
#include <memory>
#include <thread>
#include <vector>

#include <rclcpp_action/rclcpp_action.hpp>
#include <rclcpp_components/register_node_macro.hpp>

#include "visualization_msgs/msg/marker_array.hpp"

#include <nav2_msgs/action/navigate_to_pose.hpp>
#include "nav2_util/robot_utils.hpp"

class GoalCatcher
{
public:
  GoalCatcher(rclcpp::Node *node, std::string globalFrame, std::string robotFrame, double robotRadius);

  bool init();
  void send_goal(nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal, rclcpp::Time timestamp);
  bool isMoving();
  bool isRotating();
  bool isGoalBlocked(double x, double y) const;
  bool isVisited(double x, double y) const;
  void resetVisitedPlaces();
  std::vector<nav2_msgs::action::NavigateToPose::Goal> getSentGoals() const;
  std::vector<nav2_msgs::action::NavigateToPose::Goal> getBlockedGoals() const;

private:
    void goal_response_callback(const rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr &goal_handle);
    void feedback_callback(rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr, const std::shared_ptr<const nav2_msgs::action::NavigateToPose::Feedback> feedback);
    void result_callback(const rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::WrappedResult &result);
    bool isActionServerUp() const;
  
  rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SharedPtr client_ptr_;
  nav2_msgs::action::NavigateToPose::Goal navGoal_;
  std::vector<nav2_msgs::action::NavigateToPose::Goal> blockedGoals_;
  std::vector<nav2_msgs::action::NavigateToPose::Goal> sentGoals_;
  rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SendGoalOptions navGoalOptions_;
  geometry_msgs::msg::PoseStamped start_pose_;
  std::string global_frame_;
  std::string robot_base_frame_;
  bool isMoving_;
  bool isRotating_;
  int32_t navigationTime_;
  visualization_msgs::msg::MarkerArray markersMsg_;
  double robotRadius_;
  rclcpp::Node *node_;
};

#endif
