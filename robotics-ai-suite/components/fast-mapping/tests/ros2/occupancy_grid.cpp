// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <nav_msgs/msg/map_meta_data.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <nav_msgs/srv/get_map.hpp>
#include <rclcpp/logging.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp/serialization.hpp>
#include <rclcpp/serialized_message.hpp>
#include <rosbag2_cpp/reader.hpp>
#include <rosbag2_cpp/readers/sequential_reader.hpp>
#include <rosbag2_storage/storage_options.hpp>
#include <rosbag2_transport/play_options.hpp>
#include <rosbag2_transport/visibility_control.hpp>

static std::string bagfile;

class OccupancyGridTest : public testing::Test
{
public:
  typedef std::function<void(std::shared_ptr<nav_msgs::msg::OccupancyGrid>)> OccupancyGridCb;

  OccupancyGridTest() { gotOccupancyMap2D = false; }

  ~OccupancyGridTest() {}

  bool gotOccupancyMap2D;

  void readOccupancyMap2D(const std::shared_ptr<nav_msgs::msg::OccupancyGrid const> & map);

  std::shared_ptr<nav_msgs::msg::OccupancyGrid const> occupancyMap2D;
};

void OccupancyGridTest::readOccupancyMap2D(
  const std::shared_ptr<nav_msgs::msg::OccupancyGrid const> & map)
{
  gotOccupancyMap2D = true;
  occupancyMap2D = map;
}

TEST_F(OccupancyGridTest, CheckOccupancyGrid)
{
  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("map_validator");
  nav_msgs::msg::OccupancyGrid occupancyGridRef;
  std::string map_topic("/world/map");
  bool hasTopic = true;

  rosbag2_storage::StorageOptions storage_options;
  rosbag2_cpp::ConverterOptions converter_options;

  storage_options.uri = bagfile;
  storage_options.storage_id = "sqlite3";
  converter_options.output_serialization_format = "cdr";

  rosbag2_cpp::Reader reader(std::make_unique<rosbag2_cpp::readers::SequentialReader>());
  reader.open(storage_options, converter_options);

  while (reader.has_next()) {
    auto msg = reader.read_next();
    if (msg->topic_name == map_topic) {
      rclcpp::Serialization<nav_msgs::msg::OccupancyGrid> serialization;
      rclcpp::SerializedMessage serializedMsg(*msg->serialized_data);
      serialization.deserialize_message(&serializedMsg, &occupancyGridRef);
    }
  }

  if (!occupancyGridRef.data.size()) {
    RCLCPP_ERROR(
      rclcpp::get_logger("rclcpp"), "Cannot find topics %s in the rosbag %s", map_topic.c_str(),
      bagfile.c_str());
    hasTopic = false;
  }

  ASSERT_TRUE(hasTopic);

  OccupancyGridCb func =
    std::bind(&OccupancyGridTest::readOccupancyMap2D, this, std::placeholders::_1);
  auto map_qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable();
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

  // Compare the two maps
  auto genMapWidth = occupancyMap2D->info.width;
  auto refMapWidth = occupancyGridRef.info.width;

  ASSERT_TRUE(genMapWidth == refMapWidth);

  auto genMapHeight = occupancyMap2D->info.height;
  auto refMapHeight = occupancyGridRef.info.height;

  ASSERT_TRUE(genMapHeight == refMapHeight);

  unsigned int match = 0;
  unsigned int limit = ((genMapWidth * refMapWidth) * 95) / 100;
  unsigned int mapSize = genMapHeight * genMapWidth;

  for (size_t i = 0; i < mapSize; i++) {
    unsigned char refMapVal = occupancyGridRef.data[i];
    unsigned char genMapVal = occupancyMap2D->data[i];

    if (refMapVal == genMapVal) {
      match += 1;
    }
  }
  // Test will succeed if more then 98% of the map matches
  ASSERT_GE(match, limit);
}

int main(int argc, char ** argv)
{
  int returnCode = 0;

  try {
    // Initialize GoogleTest
    testing::InitGoogleTest(&argc, argv);
    // Check if the rosbag file name is provided
    if (argc <= 1) {
      std::cerr << "Usage: " << argv[0] << " <rosbag_file>" << std::endl;
      returnCode = -1;
    }
    // Declare the bagfile variable and assign it the provided argument
    bagfile = std::string(argv[1]);
    // Initialize ROS 2
    rclcpp::init(argc, argv);
    // Log the name of the rosbag file
    RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "The rosbag %s", bagfile.c_str());
    // Run all the tests
    returnCode = RUN_ALL_TESTS();
  } catch (const std::exception & e) {
    std::cerr << "Standard exception: " << e.what() << std::endl;
    returnCode = -1;
  } catch (...) {
    // Houston!! we have a problem!
    std::cerr << "Unknown exception occurred." << std::endl;
    returnCode = -1;
  }

  return returnCode;
}
