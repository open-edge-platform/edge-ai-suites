// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#ifndef WANDERING__TESTS__DUMMYGOALCATCHER_HPP_
#define WANDERING__TESTS__DUMMYGOALCATCHER_HPP_

#include <gtest/gtest.h>

#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "GoalCatcher.h"
#include "geometry_msgs/msg/pose_stamped.hpp"

#define GAZEBO_ROBOT_RADIUS 0.22

using std::cerr;
using std::endl;
using std::make_shared;
using std::string;

class DummyGoalCatcher : public ::testing::Test
{
public:
  DummyGoalCatcher()
  {
    this->node_ = rclcpp::Node::make_shared("goalcatcher_test");
    this->goalCatcher_ = std::make_shared<GoalCatcher>(
      this->node_.get(), string("map"), string("base_link"), GAZEBO_ROBOT_RADIUS);
  }

  ~DummyGoalCatcher() {}

  bool sendGoalTest()
  {
    if (!this->goalCatcher_->init()) {
      return false;
    }

    geometry_msgs::msg::PoseStamped::SharedPtr msg =
      std::make_shared<geometry_msgs::msg::PoseStamped>();
    if (!msg) {
      return false;
    } else {
      msg->pose.position.x = 1.0;
      msg->pose.position.y = 1.0;

      nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal =
        std::make_shared<nav2_msgs::action::NavigateToPose::Goal>();
      goal->pose = *msg;

      this->goalCatcher_->send_goal(goal, this->node_->now());
      rclcpp::spin_some(this->node_);
      if (!this->goalCatcher_->isMoving()) {
        cerr << "Goal Catcher should be in moving state" << endl;
        return false;
      }

      while (this->goalCatcher_->isMoving()) {
        rclcpp::spin_some(this->node_);
      }
      // We send a goal which is near and should be reported as visited
      double x = 1.05;
      double y = 1.05;
      if (!this->goalCatcher_->isVisited(x, y)) {
        cerr << "Coord already visited, but goal catcher does not report it!" << endl;
        return false;
      }

      return true;
    }
  }

  bool sendAbortedGoalTest()
  {
    if (!this->goalCatcher_->init()) {
      return false;
    }

    geometry_msgs::msg::PoseStamped::SharedPtr msg =
      std::make_shared<geometry_msgs::msg::PoseStamped>();
    if (!msg) {
      return false;
    } else {
      msg->pose.position.x = 1.0;
      msg->pose.position.y = 1.0;

      nav2_msgs::action::NavigateToPose::Goal::SharedPtr goal =
        std::make_shared<nav2_msgs::action::NavigateToPose::Goal>();
      goal->pose = *msg;

      this->goalCatcher_->send_goal(goal, this->node_->now());
      rclcpp::spin_some(this->node_);
      while (this->goalCatcher_->isMoving()) {
        rclcpp::spin_some(this->node_);
      }

      if (!this->goalCatcher_->isGoalBlocked(msg->pose.position.x, msg->pose.position.y)) {
        cerr << "Coord should be blocked!" << endl;
        return false;
      }

      return true;
    }
  }

private:
  rclcpp::Node::SharedPtr node_;
  std::shared_ptr<GoalCatcher> goalCatcher_;
};

#endif  // WANDERING__TESTS__DUMMYGOALCATCHER_HPP_
