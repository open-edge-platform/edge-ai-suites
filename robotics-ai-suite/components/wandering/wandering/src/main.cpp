// SPDX-License-Identifier: Apache-2.0
/*
Copyright (C) 2025 Intel Corporation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
*/

#include <memory>

#include "rclcpp/rclcpp.hpp"

#include "WanderingMapper.h"


int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  try {
    auto wanderingWrapper = std::make_shared<WanderingMapper>();
    rclcpp::spin(wanderingWrapper);
  } catch (...) {
    std::cerr << "Failed to run WanderingWrapper. " << std::endl;
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
