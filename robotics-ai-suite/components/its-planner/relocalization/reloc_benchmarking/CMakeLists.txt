# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(reloc_benchmarking)

set(CMAKE_CXX_STANDARD 17)
set(GCC_COVERAGE_COMPILE_FLAGS "-fno-strict-overflow -fno-delete-null-pointer-checks")

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_core REQUIRED)
find_package(std_srvs REQUIRED)

set(library_name reloc_benchmarking)

set(dependencies
  rclcpp
  geometry_msgs
  nav2_core
  std_srvs
)

add_executable(reloc_benchmarking src/reloc_benchmarking.cpp)

ament_target_dependencies(${library_name}
  ${dependencies}
)

install(TARGETS
  reloc_benchmarking
  DESTINATION lib/${PROJECT_NAME})

ament_package()
