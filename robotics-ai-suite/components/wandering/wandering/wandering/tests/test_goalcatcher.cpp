// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <string>

#include "dummyactionserver.hpp"
#include "dummygoalcatcher.hpp"

static std::shared_ptr<NavGoalActionServer> action_server_;

TEST_F(DummyGoalCatcher, testValidGoal)
{
  action_server_->setDuration(3);
  ASSERT_TRUE(sendGoalTest());
  SUCCEED();
}

TEST_F(DummyGoalCatcher, testNonValidGoal)
{
  action_server_->setDuration(3);
  action_server_->setToCancel();
  ASSERT_TRUE(sendAbortedGoalTest());
  SUCCEED();
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  // initialize ROS
  rclcpp::init(argc, argv);

  action_server_ = make_shared<NavGoalActionServer>();

  std::thread server_thread([]() { rclcpp::spin(action_server_); });

  bool all_successful = RUN_ALL_TESTS();

  // shutdown ROS
  rclcpp::shutdown();
  action_server_.reset();
  server_thread.join();

  return all_successful;
}
