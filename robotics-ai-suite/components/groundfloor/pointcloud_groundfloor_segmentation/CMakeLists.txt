# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

cmake_minimum_required(VERSION 3.8)
project(pointcloud_groundfloor_segmentation VERSION 1.0.0)
cmake_policy(SET CMP0074 NEW)

set(CMAKE_CXX_STANDARD 17)

if((CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang") AND NOT FUZZTEST_FUZZING_MODE)
  add_compile_options(-Wall -Wextra -Wpedantic -Werror -fstack-protector-all -Wno-deprecated-declarations)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(pcl_conversions REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(depth_image_proc REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_eigen REQUIRED)
find_package(PCL REQUIRED COMPONENTS common)
find_package(Eigen3 REQUIRED)

include_directories(include SYSTEM
  ${PCL_INCLUDE_DIRS}
  ${tf2_ros_INCLUDE_DIRS}
  ${tf2_eigen_INCLUDE_DIRS}
)

### RealSense ground floor segmentation node

add_executable(${PROJECT_NAME}
  src/groundfloor_segmentation_node.cpp
  src/Monitor.cpp
)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(${PROJECT_NAME} PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17

ament_target_dependencies(${PROJECT_NAME}
  rclcpp
  pcl_conversions
  sensor_msgs
  depth_image_proc
  tf2_ros
)

target_link_libraries(${PROJECT_NAME}
  ${PCL_LIBRARIES}
)

### Pointcloud input node

add_executable(pointcloud_input_node
  src/pointcloud_input_node.cpp
)

target_include_directories(pointcloud_input_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(pointcloud_input_node PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17

ament_target_dependencies(pointcloud_input_node
  rclcpp
  sensor_msgs
  tf2_ros
)

target_link_libraries(pointcloud_input_node
  ${PCL_LIBRARIES}
)

ament_package()

# ####################################################################
# install
# ####################################################################

install(TARGETS pointcloud_input_node
  DESTINATION lib/${PROJECT_NAME})

install(TARGETS ${PROJECT_NAME}
  DESTINATION lib/${PROJECT_NAME})

install(
  DIRECTORY launch params rviz
  DESTINATION share/${PROJECT_NAME}
)

####################################################################
# tests
####################################################################
IF(BUILD_TEST)
  include(${CMAKE_SOURCE_DIR}/cmake/gtest.cmake)
  add_subdirectory(test)
ENDIF(BUILD_TEST)
