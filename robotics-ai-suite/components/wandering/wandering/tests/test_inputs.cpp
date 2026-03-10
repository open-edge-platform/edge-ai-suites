// Copyright (c) 2021 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <string>

#include "WanderingMapper.h"

class InputTest : public WanderingMapper
{
public:
  InputTest() {}

  bool testWrongMapTopicInput()
  {
    // Send intentionally wrong data type to ROS topic
    // /global_costmap/costmap expects occupancy grid
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr negativeTopicPublisher_;
    negativeTopicPublisher_ =
      this->create_publisher<geometry_msgs::msg::Twist>("/global_costmap/costmap", 10);
    rclcpp::spin_some(shared_from_this());
    geometry_msgs::msg::Twist cmd;
    cmd.angular.z = 0;
    negativeTopicPublisher_->publish(cmd);
    rclcpp::spin_some(shared_from_this());
    rclcpp::sleep_for(std::chrono::seconds(1));
    rclcpp::spin_some(shared_from_this());
    negativeTopicPublisher_ = nullptr;
    if (this->mapEngine_->isMapValid()) {
      std::cerr << "Map should not be valid!" << std::endl;
      return false;
    }

    if (this->initialized_) {
      return false;
    }

    return true;
  }

  bool testBadMapData()
  {
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr badMapDataPublisher_;
    badMapDataPublisher_ =
      this->create_publisher<nav_msgs::msg::OccupancyGrid>("/global_costmap/costmap", 10);
    nav_msgs::msg::OccupancyGrid mapGrid;
    mapGrid.info.resolution = 0;
    mapGrid.info.width = 0;
    mapGrid.info.height = 0;
    mapGrid.info.origin.position.x = 0;
    mapGrid.info.origin.position.y = 0;
    rclcpp::spin_some(shared_from_this());
    badMapDataPublisher_->publish(mapGrid);
    rclcpp::spin_some(shared_from_this());
    rclcpp::sleep_for(std::chrono::seconds(1));
    rclcpp::spin_some(shared_from_this());
    badMapDataPublisher_ = nullptr;
    if (this->mapEngine_->isMapValid()) {
      std::cerr << "Map should not be valid!" << std::endl;
      return false;
    }

    if (this->initialized_) {
      return false;
    }

    return true;
  }

  bool testWrongXYWandering()
  {
    rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr badWanderXYPublisher_;
    badWanderXYPublisher_ =
      this->create_publisher<geometry_msgs::msg::PoseStamped>("/wander/to", 1);
    rclcpp::spin_some(shared_from_this());
    geometry_msgs::msg::PoseStamped pose_msg;

    badWanderXYPublisher_->publish(pose_msg);
    rclcpp::spin_some(shared_from_this());
    rclcpp::sleep_for(std::chrono::seconds(1));
    rclcpp::spin_some(shared_from_this());
    badWanderXYPublisher_ = nullptr;
    if (this->mapEngine_->isMapValid()) {
      std::cerr << "Map should not be valid!" << std::endl;
      return false;
    }

    if (this->initialized_) {
      return false;
    }

    return true;
  }

  bool testEmptyMap()
  {
    if (this->mapEngine_->init()) {
      return false;
    }

    if (this->areTfFramesPresent()) {
      return false;
    }

    geometry_msgs::msg::PoseStamped pose;
    if (this->mapEngine_->setRobotPose(pose)) {
      return false;
    }

    if (this->mapEngine_->shouldReset()) {
      return false;
    }

    double x, y;
    if (this->mapEngine_->getNextGoalCoord(x, y)) {
      return false;
    }

    return true;
  }

  bool testBlankGoalCatcher()
  {
    if (this->goalCatcher_->init()) {
      return false;
    }

    if (this->goalCatcher_->isMoving()) {
      return false;
    }

    if (this->goalCatcher_->getSentGoals().size() > 0) {
      return false;
    }

    if (this->goalCatcher_->getBlockedGoals().size() > 0) {
      return false;
    }

    return true;
  }

private:
};

/*
In ROS2 Humble it's not possible to create topics with the same name
but different types.  See:

https://github.com/ros2/ros2/issues/1095
https://github.com/ros2/ros2/issues/1213

TEST(topicNegTest, topicNegTest)
{
    std::shared_ptr<InputTest> inputTester = std::make_shared<InputTest>();
    if (inputTester) {
      ASSERT_TRUE(inputTester->testWrongMapTopicInput());
      SUCCEED();
    } else {
      FAIL();
    }
}
*/

TEST(wrongMapDataTest, wrongMapDataTest)
{
  std::shared_ptr<InputTest> inputTester = std::make_shared<InputTest>();
  if (inputTester) {
    ASSERT_TRUE(inputTester->testBadMapData());
    SUCCEED();
  } else {
    FAIL();
  }
}

TEST(wrongXYMapGoalTest, wrongXYMapGoalTest)
{
  std::shared_ptr<InputTest> inputTester = std::make_shared<InputTest>();
  if (inputTester) {
    ASSERT_TRUE(inputTester->testWrongXYWandering());
    SUCCEED();
  } else {
    FAIL();
  }
}

TEST(testEmptyMap, testEmptyMap)
{
  std::shared_ptr<InputTest> inputTester = std::make_shared<InputTest>();
  if (inputTester) {
    ASSERT_TRUE(inputTester->testEmptyMap());
    SUCCEED();
  } else {
    FAIL();
  }
}

TEST(testBlankGoalCatcher, testBlankGoalCatcher)
{
  std::shared_ptr<InputTest> inputTester = std::make_shared<InputTest>();
  if (inputTester) {
    ASSERT_TRUE(inputTester->testBlankGoalCatcher());
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

  bool all_successful = RUN_ALL_TESTS();

  // shutdown ROS
  rclcpp::shutdown();

  return all_successful;
}
