// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "FastMappingNode.h"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  std::shared_ptr<FastMappingNode> fm = std::make_shared<FastMappingNode>();
  int returnCode = 0;  // Variable to store the return code

  try {
    fm->init();
    if (!rclcpp::ok()) {
      std::cerr << "FastMapping node failed to start or was stopped by user..." << std::endl;
      returnCode = -1;
    } else {
      fm->start();
      rclcpp::spin(fm);
      fm->stop();
    }
  } catch (const std::exception & e) {
    std::cerr << e.what() << '\n';
    returnCode = -1;
  }

  rclcpp::shutdown();

  return returnCode;
}
