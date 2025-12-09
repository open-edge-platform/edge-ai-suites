// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <unordered_map>

#include <gtest/gtest.h>

#include "TrackerNode.h"

using namespace std;

std::shared_ptr<TrackerNode> trackerNode;

class InvalidInputTest : public rclcpp::Node
{
public:
  InvalidInputTest() : Node("test_invalid_input")
  {
    auto imageQos = rclcpp::SensorDataQoS();
    auto infoQos = rclcpp::QoS(10);
    this->pubImage_ =
      create_publisher<sensor_msgs::msg::Image>("/camera/color/image_raw", imageQos);
    this->pubDepthImage_ = create_publisher<sensor_msgs::msg::Image>(
      "/camera/aligned_depth_to_color/image_raw", imageQos);
    this->pubCameraInfo_ =
      create_publisher<sensor_msgs::msg::CameraInfo>("/camera/color/camera_info", infoQos);
  }
  ~InvalidInputTest() {}

  void runCameraInfoCallback(bool validInfo)
  {
    rclcpp::sleep_for(std::chrono::seconds(2));
    rclcpp::spin_some(shared_from_this());
    sensor_msgs::msg::CameraInfo cameraInfoMsg;
    if (validInfo) {
      cameraInfoMsg.width = 100;
      cameraInfoMsg.height = 100;
      cameraInfoMsg.header.frame_id = "test";
    }
    this->pubCameraInfo_->publish(cameraInfoMsg);
    rclcpp::spin_some(shared_from_this());
    rclcpp::sleep_for(std::chrono::seconds(15));
  }

  void runCameraFrameCallback()
  {
    rclcpp::spin_some(shared_from_this());
    sensor_msgs::msg::Image frame;
    this->pubImage_->publish(frame);
    this->pubDepthImage_->publish(frame);
    rclcpp::spin_some(shared_from_this());
    rclcpp::sleep_for(std::chrono::seconds(2));
  }

private:
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pubImage_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pubDepthImage_;
  rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr pubCameraInfo_;
};

TEST(testInvalidImageCallback, testInvalidImageCallback)
{
  trackerNode = make_shared<TrackerNode>();
  std::atomic<bool> initialized(false);
  std::thread trackerInitThread([&]() {
    if (trackerNode->init()) {
      initialized = true;
    }
  });
  auto tstInvalidInput = make_shared<InvalidInputTest>();
  tstInvalidInput->runCameraInfoCallback(false);
  // we expect that tracker is not initialized
  if (initialized) {
    cerr << "Tracker should not be initialized!" << endl;
    trackerNode->stop();
    trackerInitThread.join();
    trackerNode.reset();
    FAIL();
  }

  tstInvalidInput->runCameraInfoCallback(true);
  if (!initialized) {
    cerr << "Tracker should be initialized!" << endl;
    trackerNode->stop();
    trackerInitThread.join();
    trackerNode.reset();
    FAIL();
  }
  trackerInitThread.join();
  std::thread rosSpin([]() { rclcpp::spin(trackerNode); });
  tstInvalidInput->runCameraFrameCallback();
  if (trackerNode->getReceivedFramesCount() > 0) {
    cerr << "Tracker should not have received frames!" << endl;
    trackerNode->stop();
    trackerNode.reset();
    rosSpin.join();
    FAIL();
  }
  // all tests were ok; close the session
  trackerNode->stop();
  // shutdown ROS
  rclcpp::shutdown();
  trackerNode.reset();
  rosSpin.join();
  SUCCEED();
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  // initialize ROS
  rclcpp::init(argc, argv);

  bool all_successful = RUN_ALL_TESTS();

  if (all_successful) {
    std::cout << "Test failed" << std::endl;
  } else {
    std::cout << "Test successful" << std::endl;
  }

  // shutdown ROS
  rclcpp::shutdown();

  return all_successful;
}
