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
// #include "../src/send_localization.cpp"
#include "../include/send_localization.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "nav2_msgs/srv/global_localization.hpp"

#include "std_srvs/srv/empty.hpp"
#include "nav2_msgs/srv/clear_entire_costmap.hpp"

rclcpp::Service<std_srvs::srv::Empty>::SharedPtr global_loc_srv_;

void fastGlobalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Request> & request,
  std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Response>/*response*/);

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

TEST(SendLocalizationTest, test_send_localization)
{

  poses_file_.open("last_known_poses.txt");
  poses_file_ << 0.0 << "," << 0.0 << "\n";
  poses_file_.close();

  auto node = std::make_shared<SendLocalization>();

  std::shared_ptr<rclcpp::Node> node_test = rclcpp::Node::make_shared("service_test");

  rclcpp::Service<nav2_msgs::srv::GlobalLocalization>::SharedPtr fast_global_loc_srv_ =
    node_test->create_service<nav2_msgs::srv::GlobalLocalization>(
    "fast_global_localization",
    &fastGlobalLocalizationCallback);

  rclcpp::Service<nav2_msgs::srv::ClearEntireCostmap>::SharedPtr clear_entire_costmap_ =
    node_test->create_service<nav2_msgs::srv::ClearEntireCostmap>(
    "global_costmap/clear_entirely_global_costmap", &clearEntireCostmapCallback);

  EXPECT_EQ(node->SendLocalizationCMD(), 1);
}

void fastGlobalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Request> & request,
  std::shared_ptr<nav2_msgs::srv::GlobalLocalization::Response>/*response*/)
{
}

void globalLocalizationCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<std_srvs::srv::Empty::Request>/*req*/,
  std::shared_ptr<std_srvs::srv::Empty::Response>/*res*/)
{
}

void clearEntireCostmapCallback(
  const std::shared_ptr<rmw_request_id_t>/*request_header*/,
  const std::shared_ptr<nav2_msgs::srv::ClearEntireCostmap::Request>/*req*/,
  std::shared_ptr<nav2_msgs::srv::ClearEntireCostmap::Response>/*res*/)
{
}
