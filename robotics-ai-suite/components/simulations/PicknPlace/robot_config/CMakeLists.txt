# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(robot_config)

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)

# Message dependencies
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

# URDF processing
find_package(xacro REQUIRED)

include_directories(include)

# Install Python package
ament_python_install_package(${PROJECT_NAME} PACKAGE_DIR scripts)

# Install Python scripts
file(GLOB SCRIPT_FILES "${CMAKE_CURRENT_SOURCE_DIR}/scripts/*.py")
install(PROGRAMS ${SCRIPT_FILES} DESTINATION lib/${PROJECT_NAME})

# Install directories
install(DIRECTORY 
  launch 
  config 
  urdf 
  worlds 
  models 
  rviz 
  params 
  maps 
  DESTINATION share/${PROJECT_NAME}
)

# Environment hooks
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/robot_config.dsv.in")

ament_package()
