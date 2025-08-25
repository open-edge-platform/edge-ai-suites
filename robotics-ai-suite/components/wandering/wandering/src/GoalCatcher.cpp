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

#include <std_msgs/msg/string.hpp>
#include <rclcpp/rclcpp.hpp>

#include "GoalCatcher.h"

GoalCatcher::GoalCatcher(rclcpp::Node *node, std::string globalFrame, std::string robotFrame, double robotRadius):
  global_frame_(globalFrame), robot_base_frame_(robotFrame),
  isMoving_(false), isRotating_(false), navigationTime_(0), robotRadius_(robotRadius), node_(node)
  {
    this->client_ptr_ = rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(node_, "navigate_to_pose");

    this->navGoal_.pose.header.frame_id = global_frame_;
    this->navGoalOptions_.goal_response_callback = std::bind(&GoalCatcher::goal_response_callback, this, std::placeholders::_1);
    this->navGoalOptions_.feedback_callback = std::bind(&GoalCatcher::feedback_callback, this, std::placeholders::_1, std::placeholders::_2);
    this->navGoalOptions_.result_callback = std::bind(&GoalCatcher::result_callback, this, std::placeholders::_1);
  }

bool GoalCatcher::init() {
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Initializing GoalCatcher...");
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Waiting for action server to be up. Max timeout: 2 secs.");
    return this->isActionServerUp();
  }

void GoalCatcher::send_goal(nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal, rclcpp::Time timestamp)
  {
    if (!this->isActionServerUp())
      return;
    if (this->isGoalBlocked(goal->pose.pose.position.x, goal->pose.pose.position.y)) {
      RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Goal (%f, %f) is blocked.", goal->pose.pose.position.x, goal->pose.pose.position.y);
      return;
    }
    if (this->isVisited(goal->pose.pose.position.x, goal->pose.pose.position.y)) {
      RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "We were at or near the goal (%f, %f).", goal->pose.pose.position.x,  goal->pose.pose.position.y);
      return;
    }

    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Sending target goal [%f, %f, %f]", goal->pose.pose.position.x, goal->pose.pose.position.y, goal->pose.pose.position.z);
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Moving...");

    this->navGoal_ = *goal;
    this->navGoal_.pose.header.frame_id = global_frame_;
    this->navGoal_.pose.header.stamp = timestamp;

    this->client_ptr_->async_send_goal(this->navGoal_, this->navGoalOptions_);

    this->isMoving_ = true;
    this->isRotating_ = !this->navGoal_.behavior_tree.empty();
    this->sentGoals_.push_back(this->navGoal_);
  }

// void GoalCatcher::goal_response_callback(std::shared_future<rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr> future) {
void GoalCatcher::goal_response_callback(const rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr &goal_handle) {
    if(!goal_handle) {
      this->isMoving_ = false;
      this->isRotating_ = false;
      RCLCPP_ERROR(rclcpp::get_logger("wandering_mapper"), "Goal was rejected by server");
    } else {
      this->isMoving_ = true;
      this->isRotating_ = !this->navGoal_.behavior_tree.empty();
      RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Goal %s accepted by server (status=%d), waiting for result", rclcpp_action::to_string(goal_handle->get_goal_id()).c_str(), goal_handle->get_status());
    }
}

void GoalCatcher::feedback_callback(rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr goal_handle, const std::shared_ptr<const nav2_msgs::action::NavigateToPose::Feedback> feedback) {
    this->navigationTime_ = feedback->navigation_time.sec;

    RCLCPP_INFO_STREAM_THROTTLE(rclcpp::get_logger("wandering_mapper"),
                                *this->node_->get_clock(),
                                1000,
                                "Feedback goal " << rclcpp_action::to_string(goal_handle->get_goal_id())
                                << ", feedback: recoveries=" << feedback->number_of_recoveries
                                << ", distance_remaining=" << feedback->distance_remaining);
}

void GoalCatcher::result_callback(const rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::WrappedResult &result) {
    this->isMoving_ = false;
    this->isRotating_ = false;
    RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Result for goal %s", rclcpp_action::to_string(result.goal_id).c_str());
    switch (result.code) {
      case rclcpp_action::ResultCode::SUCCEEDED:
        RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Goal was reached");
        break;
      case rclcpp_action::ResultCode::ABORTED:
        RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Goal was aborted. Will add it to the blocked list");
        this->blockedGoals_.push_back(this->navGoal_);
        return;
      case rclcpp_action::ResultCode::CANCELED:
        RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Goal was canceled");
        this->blockedGoals_.push_back(this->navGoal_);
        return;
      default:
        RCLCPP_WARN(rclcpp::get_logger("wandering_mapper"), "Unknown result code");
        return;
    }
}

bool GoalCatcher::isMoving() {
  return this->isMoving_;
}

bool GoalCatcher::isRotating() {
  return this->isRotating_;
}

bool GoalCatcher::isGoalBlocked(double x, double y) const {
  for (auto& blockedGoal : this->blockedGoals_) {
    double x_diff = fabs(x - blockedGoal.pose.pose.position.x);
    double y_diff = fabs(y - blockedGoal.pose.pose.position.y);

    if (x_diff < this->robotRadius_ &&
        y_diff < this->robotRadius_)
      return true;
  }

  return false;
}

bool GoalCatcher::isVisited(double x, double y) const {
  for (auto& sentGoal : this->sentGoals_) {
    double x_diff = fabs(x - sentGoal.pose.pose.position.x);
    double y_diff = fabs(y - sentGoal.pose.pose.position.y);

    if (x_diff < 2 * this->robotRadius_ &&
        y_diff < 2 * this->robotRadius_)
      return true;
  }

  return false;
}

bool GoalCatcher::isActionServerUp() const {
    if(!this->client_ptr_->wait_for_action_server(std::chrono::milliseconds(2000)))
    {
      RCLCPP_ERROR(rclcpp::get_logger("wandering_mapper"), "Action server not available after waiting 2secs.");
      return false;
    }

    return true;
}

void GoalCatcher::resetVisitedPlaces() {
  this->sentGoals_.clear();
  this->blockedGoals_.clear();
  this->client_ptr_->async_cancel_all_goals();
}

std::vector<nav2_msgs::action::NavigateToPose::Goal> GoalCatcher::getSentGoals() const {
  return this->sentGoals_;
}

std::vector<nav2_msgs::action::NavigateToPose::Goal> GoalCatcher::getBlockedGoals() const {
  return this->blockedGoals_;
}
