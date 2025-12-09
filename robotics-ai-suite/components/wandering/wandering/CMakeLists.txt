# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.5)
project(wandering_app)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  if(NOT FUZZTEST_FUZZING_MODE)
    add_compile_options(-Wall -Wextra -Wpedantic -Werror -fstack-protector-all -Wno-deprecated-declarations)
  endif()
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(nav2_util REQUIRED)
find_package(nav2_costmap_2d REQUIRED)

include_directories(
  include
  include/wandering_app
)

set(dependencies
  rclcpp
  std_msgs
  nav_msgs
  geometry_msgs
  nav2_msgs
  nav2_util
  nav2_costmap_2d
  rclcpp_components
)

add_executable(wandering src/main.cpp src/MapEngine.cpp src/WanderingMapper.cpp src/GoalCatcher.cpp src/utils.cpp)
ament_target_dependencies(wandering ${dependencies})

install(TARGETS
  wandering
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  behavior_trees
  DESTINATION share/${PROJECT_NAME}/
  USE_SOURCE_PERMISSIONS
)

ament_package()
