# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0
# ##############################################################################
# Set minimum required version of cmake, project name and compile options
# ##############################################################################
cmake_minimum_required(VERSION 3.5)
project(followme_turtlebot3_gazebo)

# This package supports both ROS2 distributions with modern Gazebo:
# - Humble: Gazebo Fortress on Ubuntu 22.04  
# - Jazzy: Gazebo Harmonic on Ubuntu 24.04
if(DEFINED ENV{ROS_DISTRO})
  if("$ENV{ROS_DISTRO}" STREQUAL "humble" OR "$ENV{ROS_DISTRO}" STREQUAL "jazzy")
    message(STATUS "Building ${PROJECT_NAME} for ROS2 $ENV{ROS_DISTRO}")
  else()
    message(STATUS "Skipping ${PROJECT_NAME} for ROS2 $ENV{ROS_DISTRO} - only supported on Humble and Jazzy")
    return()
  endif()
endif()

# Default to C++17
set(CMAKE_CXX_STANDARD 17)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

if(MSVC)
  add_compile_definitions(_USE_MATH_DEFINES)
endif()

# ##############################################################################
# Find ament packages and libraries for ament and system dependencies
# ##############################################################################
find_package(ament_cmake REQUIRED)

# Use different Gazebo packages based on ROS distro:
# Humble: Gazebo Fortress (ros-gz-*) 
# Jazzy: Gazebo Harmonic (ros-gz-*)
if("$ENV{ROS_DISTRO}" STREQUAL "humble")
  find_package(ros_gz_sim REQUIRED)
  set(GAZEBO_DEPENDENCIES "ros_gz_sim")
else()
  find_package(ros_gz_sim REQUIRED)
  set(GAZEBO_DEPENDENCIES "ros_gz_sim")
endif()

find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(tf2 REQUIRED)

# ##############################################################################
# Build
# ##############################################################################
if("$ENV{ROS_DISTRO}" STREQUAL "humble")
  # Gazebo Fortress setup for Humble
  include_directories(include)
  set(dependencies "geometry_msgs" "nav_msgs" "rclcpp" "sensor_msgs" "tf2" "ros_gz_sim")
else()
  # Gazebo Harmonic setup for Jazzy 
  link_directories(${GAZEBO_LIBRARY_DIRS})
  include_directories(include ${GAZEBO_INCLUDE_DIRS})
  set(dependencies "geometry_msgs" "nav_msgs" "rclcpp" "sensor_msgs" "tf2")
endif()

set(EXEC_NAME "turtlebot3_drive")

add_executable(${EXEC_NAME} src/turtlebot3_drive.cpp)
ament_target_dependencies(${EXEC_NAME} ${dependencies})

# ##############################################################################
# Install
# ##############################################################################
install(TARGETS ${EXEC_NAME} DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY launch models rviz urdf scripts
        DESTINATION share/${PROJECT_NAME}/)

# Install worlds directory only if it contains files
file(GLOB WORLD_FILES "${CMAKE_CURRENT_SOURCE_DIR}/worlds/*")
if(WORLD_FILES)
  install(DIRECTORY worlds DESTINATION share/${PROJECT_NAME}/)
endif()

install(DIRECTORY include/ DESTINATION include/)

# ##############################################################################
# Macro for ament package
# ##############################################################################
ament_export_include_directories(include)
if("$ENV{ROS_DISTRO}" STREQUAL "humble")
  ament_export_dependencies(ros_gz_sim)
else()
  ament_export_dependencies(ros_gz_sim)
endif()
ament_export_dependencies(geometry_msgs)
ament_export_dependencies(nav_msgs)
ament_export_dependencies(rclcpp)
ament_export_dependencies(sensor_msgs)
ament_export_dependencies(tf2)
ament_package()
