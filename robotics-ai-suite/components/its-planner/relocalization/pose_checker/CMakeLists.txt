# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(pose_checker)

set(CMAKE_CXX_STANDARD 17)
set(GCC_COVERAGE_COMPILE_FLAGS "-fno-strict-overflow -fno-delete-null-pointer-checks")

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(nav2_core REQUIRED)
find_package(its_planner REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_amcl REQUIRED)
find_package(std_srvs REQUIRED)

set(library_name pose_checker)

set(dependencies
  rclcpp
  nav2_msgs
  nav2_core
  its_planner
  nav2_costmap_2d
  geometry_msgs
  nav2_amcl
  std_srvs
)

add_executable(pose_checker src/pose_checker.cpp)

ament_target_dependencies(${library_name}
  ${dependencies}
)

install(TARGETS
  pose_checker
  DESTINATION lib/${PROJECT_NAME})

ament_package()
