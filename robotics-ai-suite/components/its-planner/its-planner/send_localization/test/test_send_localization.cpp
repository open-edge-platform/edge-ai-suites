// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <math.h>
#include <memory>
#include <string>
#include <vector>
#include <iostream>
#include <fstream>

#include "gtest/gtest.h"
#include "rclcpp/rclcpp.hpp"
#include "../include/send_localization.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

// Conditional includes based on ROS2 distribution
#ifdef ROS2_HUMBLE
#include "nav2_msgs/srv/global_localization.hpp"
#endif

#include "std_srvs/srv/empty.hpp"
#include "nav2_msgs/srv/clear_entire_costmap.hpp"

// Global service pointer
rclcpp::Service<std_srvs::srv::Empty>::SharedPtr global_loc_srv_;

// Conditional callback declarations based on ROS2 distribution
#ifdef ROS2_HUMBLE
void fastGlobalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Request> & request,
  std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Response>/*response*/);
#else  // ROS2_JAZZY or other
void reinitializeGlobalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/);
#endif

void globalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/);

void clearEntireCostmapCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::ClearEntireCostmap::Request>/*req*/,
  std::shared_ptr<nav2_msgs::srv::ClearEntireCostmap::Response>/*res*/);

std::ofstream poses_file_;

class RclCppFixture
{
public:
  RclCppFixture() {rclcpp::init(0, nullptr);}
  ~RclCppFixture() {rclcpp::shutdown();}
};
RclCppFixture g_rclcppfixture;

// Test fixture class for proper resource management
class SendLocalizationTestFixture : public ::testing::Test
{
protected:
  void SetUp() override
  {
    // Create test file
    poses_file_.open("last_known_poses.txt");
    poses_file_ << 0.0 << "," << 0.0 << "\n";
    poses_file_.close();

    // Create nodes
    node = std::make_shared<SendLocalization>();
    node_test = rclcpp::Node::make_shared("service_test");

    // Create services
#ifdef ROS2_HUMBLE
    fast_global_loc_srv_ = node_test->create_service<nav2_msgs::srv::GlobalLocalization>(
      "fast_global_localization",
      &fastGlobalLocalizationCallback);
#else  // ROS2_JAZZY or other
    reinitialize_global_loc_srv_ = node_test->create_service<std_srvs::srv::Empty>(
      "reinitialize_global_localization",
      &reinitializeGlobalLocalizationCallback);
#endif

    global_loc_srv_ = node_test->create_service<std_srvs::srv::Empty>(
      "reinitialize_global_localization", &globalLocalizationCallback);

    clear_entire_costmap_ = node_test->create_service<nav2_msgs::srv::ClearEntireCostmap>(
      "global_costmap/clear_entirely_global_costmap", &clearEntireCostmapCallback);
  }

  void TearDown() override
  {
    // Explicit cleanup in proper order
#ifdef ROS2_HUMBLE
    fast_global_loc_srv_.reset();
#else
    reinitialize_global_loc_srv_.reset();
#endif
    global_loc_srv_.reset();
    clear_entire_costmap_.reset();
    
    // Reset nodes
    node.reset();
    node_test.reset();
    
    // Small delay to allow DDS cleanup
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  std::shared_ptr<SendLocalization> node;
  std::shared_ptr<rclcpp::Node> node_test;

#ifdef ROS2_HUMBLE
  rclcpp::Service<nav2_msgs::srv::GlobalLocalization>::SharedPtr fast_global_loc_srv_;
#else
  rclcpp::Service<std_srvs::srv::Empty>::SharedPtr reinitialize_global_loc_srv_;
#endif
  rclcpp::Service<nav2_msgs::srv::ClearEntireCostmap>::SharedPtr clear_entire_costmap_;
};

TEST_F(SendLocalizationTestFixture, test_send_localization)
{
  EXPECT_EQ(node->SendLocalizationCMD(), 1);
}

// Conditional callback implementations based on ROS2 distribution
#ifdef ROS2_HUMBLE
void fastGlobalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Request> & request,
  std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Response>/*response*/)
{
  // Test that request contains expected data for Humble
  EXPECT_GT(request->center_x.size(), 0);
  EXPECT_GT(request->center_y.size(), 0);
  EXPECT_GT(request->sigma.size(), 0);
  EXPECT_GT(request->weights.size(), 0);
}
#else  // ROS2_JAZZY or other
void reinitializeGlobalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/)
{
  // For Jazzy, just verify the service was called
  // No parameters to check since it's an Empty service
}
#endif

void globalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/)
{
  // Empty callback for global localization service
}

void clearEntireCostmapCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::ClearEntireCostmap::Request>/*req*/,
  std::shared_ptr<nav2_msgs::srv::ClearEntireCostmap::Response>/*res*/)
{
  // Empty callback for clear costmap service
}
