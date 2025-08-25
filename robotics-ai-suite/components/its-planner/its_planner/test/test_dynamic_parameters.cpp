// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation

#include <memory>
#include "gtest/gtest.h"
#include "nav2_util/lifecycle_node.hpp"
#include "its_planner/its_planner.hpp"
#include "rclcpp/rclcpp.hpp"

class RclCppFixture
{
public:
  RclCppFixture() {rclcpp::init(0, nullptr);}
  ~RclCppFixture() {rclcpp::shutdown();}
};
RclCppFixture g_rclcppfixture;

TEST(ITSPlannerTest, testDynamicParameter)
{
  auto node = std::make_shared<rclcpp_lifecycle::LifecycleNode>("ITSPlannerTest");
  auto costmap = std::make_shared<nav2_costmap_2d::Costmap2DROS>("global_costmap");
  costmap->on_configure(rclcpp_lifecycle::State());
  auto planner =
    std::make_unique<its_planner::ITSPlanner>();
  auto tf = std::make_shared<tf2_ros::Buffer>(node->get_clock());
  planner->configure(node, "test", tf, costmap);
  planner->activate();

  auto rec_param = std::make_shared<rclcpp::AsyncParametersClient>(
    node->get_node_base_interface(), node->get_node_topics_interface(),
    node->get_node_graph_interface(),
    node->get_node_services_interface());

  auto results = rec_param->set_parameters_atomically(
    {rclcpp::Parameter("test.interpolation_resolution", 0.05),
      rclcpp::Parameter("test.roadmap", "PROBABLISTIC"),
      rclcpp::Parameter("test.n", 2),
      rclcpp::Parameter("test.w", 32),
      rclcpp::Parameter("test.h", 32),
      rclcpp::Parameter("test.build_road_map_once", true),
      rclcpp::Parameter("test.catmull_spline", false),
      rclcpp::Parameter("test.smoothing_window", 15),
      rclcpp::Parameter("test.smoothing_window", 15),
      rclcpp::Parameter("test.buffer_size", 20),
      rclcpp::Parameter("test.min_samples", 500)});

  rclcpp::spin_until_future_complete(
    node->get_node_base_interface(),
    results);

  EXPECT_EQ(node->get_parameter("test.interpolation_resolution").as_double(), 0.05);
  EXPECT_EQ(node->get_parameter("test.roadmap").as_string(), "PROBABLISTIC");
  EXPECT_EQ(node->get_parameter("test.n").as_int(), 2);
  EXPECT_EQ(node->get_parameter("test.w").as_int(), 32);
  EXPECT_EQ(node->get_parameter("test.h").as_int(), 32);
  EXPECT_EQ(node->get_parameter("test.build_road_map_once").as_bool(), true);
  EXPECT_EQ(node->get_parameter("test.catmull_spline").as_bool(), false);
  EXPECT_EQ(node->get_parameter("test.smoothing_window").as_int(), 15);
  EXPECT_EQ(node->get_parameter("test.buffer_size").as_int(), 20);
  EXPECT_EQ(node->get_parameter("test.min_samples").as_int(), 500);
}
