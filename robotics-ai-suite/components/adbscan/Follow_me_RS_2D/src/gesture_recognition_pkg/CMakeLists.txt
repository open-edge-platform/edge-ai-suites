# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(gesture_recognition_pkg)
# Default to C++17
set(CMAKE_CXX_STANDARD 17)
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()
# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(follow_me_interfaces REQUIRED)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})
# Install Python executables
install(PROGRAMS
  gesture_recognition_pkg/gesture_recognition_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  gesture_recognition_pkg/traj_and_img_publisher_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  gesture_recognition_pkg/traj_and_img_publisher_node_v2.py
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  gesture_recognition_pkg/traj_and_img_publisher_node_v3.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config
  DESTINATION share/${PROJECT_NAME}/
)
ament_package()