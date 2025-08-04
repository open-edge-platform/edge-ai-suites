# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(robot_config)

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(gazebo_ros REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)


include_directories(include)
link_directories(
  ${gazebo_dev_LIBRARY_DIRS}
)


# Install the python module for this package
#ament_python_install_package(${PROJECT_NAME})
#ament_export_dependencies(ament_cmake_python)
#ament_export_dependencies(rclpy)

ament_python_install_package(${PROJECT_NAME} PACKAGE_DIR scripts)

file(GLOB SCRIPT_FILES "${CMAKE_CURRENT_SOURCE_DIR}/scripts/*.py")
install(PROGRAMS ${SCRIPT_FILES} DESTINATION lib/${PROJECT_NAME})


install(DIRECTORY launch config urdf worlds models rviz params maps DESTINATION share/${PROJECT_NAME})
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/robot_config.dsv.in")

ament_package()
