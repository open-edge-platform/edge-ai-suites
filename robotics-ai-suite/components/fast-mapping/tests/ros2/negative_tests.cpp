// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <gtest/gtest.h>

#include <rclcpp/rclcpp.hpp>

#include "FastMappingNode.h"

std::shared_ptr<rclcpp::Node> handle;
bool invalidNameException = false;

#define GTEST_COUT std::cerr << "[SDL_TEST] [ INFO ]"

class FastMappingTest : public testing::Test
{
public:
  FastMappingTest() {}

  ~FastMappingTest() {}
};

TEST_F(FastMappingTest, CheckInvalidNameExceptionTest) { ASSERT_TRUE(invalidNameException); }

int main(int argc, char ** argv)
{
  int returnCode = 0;

  try {
    // Initialize Google Test framework
    testing::InitGoogleTest(&argc, argv);
    // Initialize ROS 2
    rclcpp::init(argc, argv);
    // Create FastMappingNode instance
    std::shared_ptr<FastMappingNode> fm = std::make_shared<FastMappingNode>();

    try {
      fm->init();
    } catch (const rclcpp::exceptions::NameValidationError & e) {
      RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "FastMapping exception: %s ", e.what());
      invalidNameException = true;
      returnCode = -1;
    }

    // Create a node for negative testing
    auto handle = std::make_shared<rclcpp::Node>("negative_tester_node");
    // Run all tests and return the result
    returnCode = RUN_ALL_TESTS();
  } catch (const rclcpp::exceptions::InvalidParameterTypeException & e) {
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Invalid parameter type exception: %s", e.what());
    returnCode = -1;
  } catch (const std::exception & e) {
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Standard exception: %s", e.what());
    returnCode = -1;
  } catch (...) {
    // Houston!! we have a problem!
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Unknown exception occurred.");
    returnCode = -1;
  }

  return returnCode;
}
