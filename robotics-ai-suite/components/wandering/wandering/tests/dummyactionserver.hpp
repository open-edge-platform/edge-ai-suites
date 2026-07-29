// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#ifndef WANDERING__TESTS__DUMMYACTIONSERVER_HPP_
#define WANDERING__TESTS__DUMMYACTIONSERVER_HPP_

#include <functional>
#include <iostream>
#include <memory>
#include <thread>

#include <nav2_msgs/action/navigate_to_pose.hpp>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rclcpp_components/register_node_macro.hpp"

class NavGoalActionServer : public rclcpp::Node
{
public:
  using NavToPose = nav2_msgs::action::NavigateToPose;
  using GoalHandleNavToPose = rclcpp_action::ServerGoalHandle<NavToPose>;

  explicit NavGoalActionServer(const rclcpp::NodeOptions & options = rclcpp::NodeOptions())
  : Node("navgoal_action_server", options)
  {
    using std::placeholders::_1;
    using std::placeholders::_2;
    this->counter_ = 0;
    this->duration_ = 0;
    this->action_server_ = rclcpp_action::create_server<NavToPose>(
      this, "navigate_to_pose", std::bind(&NavGoalActionServer::handle_goal, this, _1, _2),
      std::bind(&NavGoalActionServer::handle_cancel, this, _1),
      std::bind(&NavGoalActionServer::handle_accepted, this, _1));
  }

  void setDuration(uint32_t duration) { this->duration_ = duration; }

  void setToCancel() { this->shouldCancel_ = true; }

private:
  rclcpp_action::Server<NavToPose>::SharedPtr action_server_;

  rclcpp_action::GoalResponse handle_goal(
    const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const NavToPose::Goal> goal)
  {
    RCLCPP_INFO(this->get_logger(), "Received goal request!");
    (void)uuid;
    this->currentGoal_ = goal;
    this->counter_ = 0;

    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
  }

  rclcpp_action::CancelResponse handle_cancel(
    const std::shared_ptr<GoalHandleNavToPose> goal_handle)
  {
    RCLCPP_INFO(this->get_logger(), "Received request to cancel goal");
    (void)goal_handle;

    return rclcpp_action::CancelResponse::ACCEPT;
  }

  void handle_accepted(const std::shared_ptr<GoalHandleNavToPose> goal_handle)
  {
    using std::placeholders::_1;
    // this needs to return quickly to avoid blocking the executor, so spin up a new thread
    std::thread{std::bind(&NavGoalActionServer::execute, this, _1), goal_handle}.detach();
  }

  void execute(const std::shared_ptr<GoalHandleNavToPose> goal_handle)
  {
    RCLCPP_INFO(this->get_logger(), "Executing goal");
    rclcpp::Rate loop_rate(1);
    const auto goal = goal_handle->get_goal();
    auto feedback = std::make_shared<NavToPose::Feedback>();
    auto & navTime = feedback->navigation_time;
    feedback->distance_remaining = 0.5;
    navTime = rclcpp::Duration(1, 0);
    auto result = std::make_shared<NavToPose::Result>();

    while (true) {
      loop_rate.sleep();
      if (this->shouldCancel_ && rclcpp::ok() && (this->counter_ >= this->duration_)) {
        goal_handle->abort(result);
        RCLCPP_INFO(this->get_logger(), "Goal aborted!");
        return;
      }

      // Publish feedback
      goal_handle->publish_feedback(feedback);
      RCLCPP_INFO(this->get_logger(), "Publish feedback");

      // Check if goal is done
      if ((this->counter_ >= this->duration_) && rclcpp::ok()) {
        goal_handle->succeed(result);
        RCLCPP_INFO(this->get_logger(), "Goal succeeded");
        return;
      }

      this->counter_++;
    }
  }

  std::shared_ptr<const NavToPose::Goal> currentGoal_;
  bool shouldCancel_;
  uint32_t counter_, duration_;
};  // class NavGoalActionServer

#endif  // WANDERING__TESTS__DUMMYACTIONSERVER_HPP_
