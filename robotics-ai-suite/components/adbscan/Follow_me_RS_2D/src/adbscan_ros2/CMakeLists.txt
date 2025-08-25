# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(adbscan_ros2_follow_me)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++17
set(CMAKE_CXX_STANDARD 17)

if("$ENV{ROS_DISTRO}" STRLESS "humble")
    add_compile_definitions(PRE_ROS_HUMBLE)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Wformat-overflow=1)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(nav2_dynamic_msgs REQUIRED)
find_package(pcl_conversions REQUIRED)
find_package(PCL 1.12 REQUIRED COMPONENTS common io kdtree)
find_package(follow_me_interfaces REQUIRED)
find_package(Eigen3 REQUIRED)

include_directories(include)

set(HEADER_FILES src/ADBScan.h src/dbscan_adaptiveK.h src/doDBSCAN.hpp src/print_info.h src/Util.hpp)
add_library(adbscan_lib src/dbscan_adaptiveK.cpp src/doDBSCAN.cpp src/print_info.cpp src/Util.cpp ${HEADER_FILES})

set(dependencies "geometry_msgs" "rclcpp" "nav2_dynamic_msgs" "PCL" "pcl_conversions" "sensor_msgs" "visualization_msgs" "follow_me_interfaces")
add_executable(adbscan_pub src/adbscan_pub.cpp)
ament_target_dependencies(adbscan_pub ${dependencies})

include_directories(${EIGEN3_INCLUDE_DIR})
include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

add_executable(adbscan_sub src/adbscan_sub.cpp src/print_info.cpp src/doDBSCAN.cpp src/Util.cpp src/dbscan_adaptiveK.cpp)
ament_target_dependencies(adbscan_sub ${dependencies})
target_link_libraries (adbscan_sub ${PCL_LIBRARIES})

add_executable(adbscan_sub_w_gesture src/adbscan_sub_w_gesture.cpp src/print_info.cpp src/doDBSCAN.cpp src/Util.cpp src/dbscan_adaptiveK.cpp)
ament_target_dependencies(adbscan_sub_w_gesture ${dependencies})
target_link_libraries (adbscan_sub_w_gesture ${PCL_LIBRARIES})

add_executable(adbscan_sub_w_gesture_audio src/adbscan_sub_w_gesture_audio.cpp src/print_info.cpp src/doDBSCAN.cpp src/Util.cpp src/dbscan_adaptiveK.cpp)
ament_target_dependencies(adbscan_sub_w_gesture_audio ${dependencies})
target_link_libraries (adbscan_sub_w_gesture_audio ${PCL_LIBRARIES})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  set(TESTFILES
    test/main.cpp
    test/test_adbscan_clusters.cpp)
  ament_add_gtest(${PROJECT_NAME}_test ${TESTFILES})
  target_link_libraries(${PROJECT_NAME}_test adbscan_lib)

  install(TARGETS
    ${PROJECT_NAME}_test
    DESTINATION lib/${PROJECT_NAME})
endif()

install(TARGETS
  adbscan_pub
  adbscan_sub
  adbscan_sub_w_gesture
  adbscan_sub_w_gesture_audio
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}/
)
ament_package()
