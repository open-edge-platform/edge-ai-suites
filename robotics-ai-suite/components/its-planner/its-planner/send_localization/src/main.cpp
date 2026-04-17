// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "../include/send_localization.hpp"
#include "rclcpp/rclcpp.hpp"


int main(int argc, char ** argv)
{
  try {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<SendLocalization>();
    rclcpp::spin(node);
    rclcpp::shutdown();
  } catch (const rclcpp::exceptions::InvalidQosOverridesException &e) {
    RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Exception: %s", e.what());
    rclcpp::shutdown();
    return 1;  
  }
  return 0;
}
