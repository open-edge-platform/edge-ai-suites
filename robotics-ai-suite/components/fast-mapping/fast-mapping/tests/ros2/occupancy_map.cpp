// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <cmath>
#include <nav_msgs/msg/map_meta_data.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <nav_msgs/srv/get_map.hpp>
#include <rclcpp/logging.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>
#include <rosbag2_cpp/reader.hpp>
#include <rosbag2_cpp/readers/sequential_reader.hpp>
#include <rosbag2_transport/play_options.hpp>
#include <rosbag2_transport/rosbag2_transport.hpp>
#include <rosbag2_transport/visibility_control.hpp>
#include <visualization_msgs/msg/marker_array.hpp>

static std::string bagfile;

class Occupancy3DMapTest : public testing::Test
{
public:
  typedef std::function<void(std::shared_ptr<visualization_msgs::msg::MarkerArray>)> MarkerArrayCb;

  Occupancy3DMapTest()
  {
    gotOccupiedVoxels = false;
    gotFreeVoxels = false;
  }

  ~Occupancy3DMapTest() {}

  void readOccupancyMap3D(const std::shared_ptr<visualization_msgs::msg::MarkerArray const> & map);
  bool gotOccupiedVoxels;
  bool gotFreeVoxels;

  std::shared_ptr<visualization_msgs::msg::MarkerArray const> occupancyMap3D;

  /*
   * Vector containing the <x,y,z> coordonates of the occupied voxels.
   */
  std::vector<geometry_msgs::msg::Point> occupiedVoxels;

  /*
   * Vector containing the <x,y,z> coordonates of the free voxels.
   */
  std::vector<geometry_msgs::msg::Point> freeVoxels;
};

void Occupancy3DMapTest::readOccupancyMap3D(
  const std::shared_ptr<visualization_msgs::msg::MarkerArray const> & map)
{
  for (const auto & marker : map->markers) {
    if (marker.ns == std::string("occupied-voxels")) {
      if (!marker.points.empty()) {
        gotOccupiedVoxels = true;
        occupiedVoxels = marker.points;
      }
    } else if (marker.ns == std::string("free-voxels")) {
      if (!marker.points.empty()) {
        gotFreeVoxels = true;
        freeVoxels = marker.points;
      }
    }
  }
}

TEST_F(Occupancy3DMapTest, CheckOccupancyMap)
{
  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("map_validator");

  // Start FastMapping and subscribe to the the 3D occupancy map.
  MarkerArrayCb func =
    std::bind(&Occupancy3DMapTest::readOccupancyMap3D, this, std::placeholders::_1);
  auto map_qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable();
  auto sub = node->create_subscription<visualization_msgs::msg::MarkerArray>(
    "/world/occupancy", map_qos, func);

  // Try a few times, because the server may not be up yet.
  int i = 100;

  rclcpp::WallRate loop_rate(std::chrono::seconds(1));
  while (!gotOccupiedVoxels && !gotFreeVoxels && i > 0) {
    rclcpp::spin_some(node);
    loop_rate.sleep();
    i--;
  }

  // Check sizes of the free and occupied voxels
  ASSERT_GE(static_cast<int>(occupiedVoxels.size()), 1);
  ASSERT_GE(static_cast<int>(freeVoxels.size()), 1);

  bool hasTopic = true;
  std::string map_topic("/world/occupancy");

  rosbag2_cpp::StorageOptions storage_options;
  rosbag2_cpp::ConverterOptions converter_options;

  storage_options.uri = bagfile;
  storage_options.storage_id = "sqlite3";
  converter_options.output_serialization_format = "cdr";

  rosbag2_cpp::Reader reader(std::make_unique<rosbag2_cpp::readers::SequentialReader>());
  reader.open(storage_options, converter_options);

  std::vector<geometry_msgs::msg::Point> freePointsRef;
  std::vector<geometry_msgs::msg::Point> occupiedPointsRef;

  while (reader.has_next()) {
    auto msg = reader.read_next();
    if (msg->topic_name == map_topic) {
      visualization_msgs::msg::MarkerArray reference_map;
      rclcpp::Serialization<visualization_msgs::msg::MarkerArray> serialization;
      rclcpp::SerializedMessage serializedMsg(*msg->serialized_data);
      serialization.deserialize_message(&serializedMsg, &reference_map);

      for (const auto & marker : reference_map.markers) {
        if (marker.ns == std::string("occupied-voxels")) {
          occupiedPointsRef = marker.points;
        } else if (marker.ns == std::string("free-voxels")) {
          freePointsRef = marker.points;
        }
      }
    }
  }

  if (!freePointsRef.size() && !occupiedPointsRef.size()) {
    RCLCPP_ERROR(
      rclcpp::get_logger("rclcpp"), "Cannot find topics %s in the rosbag %s", map_topic.c_str(),
      bagfile.c_str());
    hasTopic = false;
  }

  ASSERT_TRUE(hasTopic);

  auto comparePoint =
    [&](const geometry_msgs::msg::Point & lhs, const geometry_msgs::msg::Point & rhs) {
      auto tolerance = .04;  // size of a voxel
      auto dist = std::sqrt(pow(lhs.x - rhs.x, 2) + pow(lhs.y - rhs.y, 2) + pow(lhs.z - rhs.z, 2));
      unsigned int total = occupiedPointsRef.size();
      unsigned int limit = (occupiedPointsRef.size() * 98) / 100;

      if (dist > tolerance) {
        total -= 1;
      }

      return total < limit ? false : true;
    };

  // Compare occupied points of the map
  bool match = std::equal(
    occupiedVoxels.begin(), occupiedVoxels.end(), occupiedPointsRef.begin(), comparePoint);
  ASSERT_TRUE(match);
}

int main(int argc, char ** argv)
{
  testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);

  // Get the name of the rosbag file.
  bagfile = std::string(argv[1]);
  RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "Reference rosbag file %s", bagfile.c_str());

  auto success = RUN_ALL_TESTS();
  rclcpp::shutdown();

  return success;
}
