// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <nav_msgs/msg/map_meta_data.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <nav_msgs/srv/get_map.hpp>
#include <rclcpp/rclcpp.hpp>
#include <visualization_msgs/msg/marker_array.hpp>

//    ==============================  ========================================  ==============
//    Default name of output topic    Message type                              Description
//    ==============================  ========================================  ==============
//    |node|/world/3d_map             `visualization_msgs::msg::marker_array`_  3D scene model
//    |node|/world/plane_info         `visualization_msgs::msg::marker_array`_  metadata of modeled planes
//    |node|/world/occupancy          `visualization_msgs::msg::marker_array`_  3D occupancy map
//    |node|/world/map                `nav_msgs::msg::occupancy_grid`_          2D occupancy map
//    ==============================  ========================================  ===============

class FastMappingTest : public testing::Test
{
public:
  typedef std::function<void(std::shared_ptr<visualization_msgs::msg::MarkerArray>)> MarkerArrayCb;
  typedef std::function<void(std::shared_ptr<nav_msgs::msg::OccupancyGrid>)> OccupancyGridCb;
  FastMappingTest()
  {
    gotOccupancyMap2D = false;
    gotOccupancyMap3D = false;
    got3DMap = false;
  }

  ~FastMappingTest() {}

  void readOccupancyMap2D(const std::shared_ptr<nav_msgs::msg::OccupancyGrid const> & map);
  void readOccupancyMap3D(const std::shared_ptr<visualization_msgs::msg::MarkerArray const> & map);
  void read3DMap(const std::shared_ptr<visualization_msgs::msg::MarkerArray const> & map);

  bool gotOccupancyMap2D;
  bool gotOccupancyMap3D;
  bool got3DMap;

  // Saved maps - not used at the moment (used for map content validation)
  std::shared_ptr<nav_msgs::msg::OccupancyGrid const> occupancyMap2D;
  std::shared_ptr<visualization_msgs::msg::MarkerArray const> occupancyMap3D;
  std::shared_ptr<visualization_msgs::msg::MarkerArray const> map3D;
};

// ROS callbacks
void FastMappingTest::readOccupancyMap2D(
  const std::shared_ptr<nav_msgs::msg::OccupancyGrid const> & map)
{
  gotOccupancyMap2D = true;
  occupancyMap2D = map;
}

void FastMappingTest::readOccupancyMap3D(
  const std::shared_ptr<visualization_msgs::msg::MarkerArray const> & map)
{
  gotOccupancyMap3D = true;
  occupancyMap3D = map;
}

void FastMappingTest::read3DMap(
  const std::shared_ptr<visualization_msgs::msg::MarkerArray const> & map)
{
  got3DMap = true;
  map3D = map;
}

// Unit tests
TEST_F(FastMappingTest, CheckOcupancyMap2DTest)
{
  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("smoke_tester_node");

  OccupancyGridCb func =
    std::bind(&FastMappingTest::readOccupancyMap2D, this, std::placeholders::_1);
  auto map_qos = rclcpp::QoS(rclcpp::KeepLast(10)).transient_local().reliable();
  auto sub = node->create_subscription<nav_msgs::msg::OccupancyGrid>("/world/map", map_qos, func);

  // Try a few times, because the server may not be up yet.
  int i = 30;

  rclcpp::WallRate loop_rate(std::chrono::seconds(1));
  while (!gotOccupancyMap2D && i > 0) {
    rclcpp::spin_some(node);
    loop_rate.sleep();
    i--;
  }
  // Check that the callback was called at least once.
  ASSERT_TRUE(gotOccupancyMap2D);
  // Check that the size if the data vector holding the 3D map is bigger then 1.
  ASSERT_GE(occupancyMap2D->data.size(), uint32_t(1));
}

TEST_F(FastMappingTest, Check3DTest)
{
  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("smoke_tester_node");

  MarkerArrayCb func = std::bind(&FastMappingTest::read3DMap, this, std::placeholders::_1);
  auto map_qos = rclcpp::QoS(rclcpp::KeepLast(10)).transient_local().reliable();
  auto sub = node->create_subscription<visualization_msgs::msg::MarkerArray>(
    "/world/fused_map", map_qos, func);

  // Try a few times, because the server may not be up yet.
  int i = 30;

  rclcpp::WallRate loop_rate(std::chrono::seconds(1));
  while (!got3DMap && i > 0) {
    rclcpp::spin_some(node);
    loop_rate.sleep();
    i--;
  }

  // Check that the callback was called at least once.
  ASSERT_TRUE(got3DMap);
  // Check that the size if the markers vector holding the 3D map is bigger then 1.
  ASSERT_GE(map3D->markers.size(), uint32_t(1));
}

int main(int argc, char ** argv)
{
  int returnCode = 0;

  try {
    // Initialize GoogleTest framework
    testing::InitGoogleTest(&argc, argv);
    // Initialize ROS 2
    rclcpp::init(argc, argv);
    // Run all the tests
    returnCode = RUN_ALL_TESTS();
    // Shutdown ROS 2
    rclcpp::shutdown();
  } catch (const testing::internal::GoogleTestFailureException & e) {
    std::cerr << "GoogleTestFailureException: " << e.what() << '\n';
    rclcpp::shutdown();
    returnCode = -1;
  } catch (const std::exception & e) {
    std::cerr << "Standard exception: " << e.what() << '\n';
    rclcpp::shutdown();
    returnCode = -1;
  } catch (...) {
    std::cerr << "Unknown exception occurred." << '\n';
    rclcpp::shutdown();
    returnCode = -1;
  }

  return returnCode;
}
