// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <chrono>
#include <string>
#include <thread>

#include "WanderingMapper.h"
#include "dummyactionserver.hpp"

#define TARGET_GOAL 34

constexpr int TEST_SHUTDOWN_SLEEP_SECONDS = 10;

static std::shared_ptr<NavGoalActionServer> action_server_;

class WanderingTest : public WanderingMapper
{
public:
  WanderingTest() {}

  bool testMapProcessing()
  {
    action_server_->setDuration(2);
    while (!this->initialized_) {
      rclcpp::spin_some(shared_from_this());
    }
    uint32_t total_visited_places = 0;
    uint32_t previous_visited_places = 0;
    while (!this->isMapped()) {
      rclcpp::spin_some(shared_from_this());
      uint32_t visitedPlaces = this->goalCatcher_->getSentGoals().size();
      if (visitedPlaces < previous_visited_places) {
        total_visited_places += previous_visited_places;
      }
      previous_visited_places = visitedPlaces;
      if (total_visited_places > TARGET_GOAL) {
        while (this->goalCatcher_->isMoving()) {
          rclcpp::spin_some(shared_from_this());
        }
        break;
      }
    }

    return true;
  }
};

TEST(testBasic, testBasic)
{
  std::shared_ptr<WanderingTest> wandering_mapper_ = std::make_shared<WanderingTest>();
  if (wandering_mapper_) {
    ASSERT_TRUE(wandering_mapper_->testMapProcessing());
    SUCCEED();
  } else {
    FAIL();
  }
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  // initialize ROS
  rclcpp::init(argc, argv);

  action_server_ = std::make_shared<NavGoalActionServer>();

  std::thread server_thread([]() { rclcpp::spin(action_server_); });

  bool all_successful = RUN_ALL_TESTS();
  RCLCPP_INFO(rclcpp::get_logger("wandering_mapper"), "Sleep before shutting down ros");
  rclcpp::sleep_for(std::chrono::seconds(TEST_SHUTDOWN_SLEEP_SECONDS));

  // shutdown ROS
  rclcpp::shutdown();
  action_server_.reset();
  server_thread.join();

  return all_successful;
}
