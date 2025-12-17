# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

# https://docs.ros.org/en/humble/The-ROS2-Project/Contributing/Code-Style-Language-Versions.html#id5
cmake_minimum_required(VERSION 3.14.4)

project(fast_mapping)

if (NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release")
endif()

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Werror -Wno-missing-field-initializers -Wno-deprecated-copy -std=c++17")

if (CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 8.0)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-error=class-memaccess")
endif()

if("$ENV{ROS_DISTRO}" STRLESS "humble")
    add_definitions(-DPRE_ROS_HUMBLE)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_gtest REQUIRED)
find_package(ament_lint_auto REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(message_filters REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(OpenCV REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosbag2_cpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_eigen REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(visualization_msgs REQUIRED)

# Includes
include_directories(
  include
  ${EIGEN3_INCLUDE_DIRS}
  ${CMAKE_CURRENT_SOURCE_DIR}/src/fast_mapping_lib
  ${CMAKE_CURRENT_SOURCE_DIR}/src/fast_mapping_lib/se
)

# Supereight conf. option
add_definitions(-DSE_FIELD_TYPE=OFusion -Wno-unknown-pragmas)

# dependencies
set(dependencies
  cv_bridge
  Eigen3
  geometry_msgs
  message_filters
  nav_msgs
  OpenCV
  rclcpp
  rosbag2_cpp
  sensor_msgs
  std_srvs
  tf2
  tf2_eigen
  tf2_geometry_msgs
  tf2_ros
  visualization_msgs
)

# FastMapping Node
add_executable(fast_mapping_node
  src/FastMappingNode.cpp
  src/MapManager.cpp
  src/Subscribers.cpp
  src/main.cpp
)

# Build OctoMap library and link
add_subdirectory(src/fast_mapping_lib)
target_link_libraries(fast_mapping_node fast_mapping_lib )

ament_target_dependencies(fast_mapping_node ${dependencies})

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

install(TARGETS
  fast_mapping_node
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

ament_package()

if(BUILD_TESTING)
  find_package(rosbag2_cpp REQUIRED)
  find_package(rosbag2_transport REQUIRED)
  find_package(rosbag2_storage REQUIRED)
  set(ROS2_TEST_PATH tests/ros2)
  ament_add_gtest_executable(fast_mapping_smoke_test_exec ${ROS2_TEST_PATH}/gtests.cpp)
  ament_target_dependencies(fast_mapping_smoke_test_exec ${dependencies})
  ament_add_test(fast_mapping_smoke-test
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/${ROS2_TEST_PATH}/fm_smoke_test_launch.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    ENV
      TEST_LAUNCH_DIR=${TEST_LAUNCH_DIR}
      TEST_EXECUTABLE=$<TARGET_FILE:fast_mapping_smoke_test_exec>
    TIMEOUT 30
  )

  ament_add_gtest_executable(occupancy_grid_test_exec ${ROS2_TEST_PATH}/occupancy_grid.cpp)
  ament_target_dependencies(occupancy_grid_test_exec
    ${dependencies}
    rosbag2_cpp
    rosbag2_transport
    rosbag2_storage
  )
  ament_add_test(occupancy_grid_test
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/${ROS2_TEST_PATH}/map_validation_launch.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    ENV
      TEST_LAUNCH_DIR=${TEST_LAUNCH_DIR}
      TEST_EXECUTABLE=$<TARGET_FILE:occupancy_grid_test_exec>
    TIMEOUT 30
  )

  ament_add_gtest_executable(sdl_depth_topic_exec
                              src/FastMappingNode.cpp
                              src/Subscribers.cpp
                              src/MapManager.cpp
                              ${ROS2_TEST_PATH}/negative_tests.cpp)
  target_link_libraries(sdl_depth_topic_exec fast_mapping_lib)
  ament_target_dependencies(sdl_depth_topic_exec ${dependencies})
  ament_add_test(sdl_depth_topic-test
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/${ROS2_TEST_PATH}/sdl_depth_topic_test_launch.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    ENV
      TEST_LAUNCH_DIR=${TEST_LAUNCH_DIR}
      TEST_EXECUTABLE=$<TARGET_FILE:sdl_depth_topic_exec>
  )

  ament_add_gtest_executable(sdl_depth_info_topic_exec
                              src/FastMappingNode.cpp
                              src/Subscribers.cpp
                              src/MapManager.cpp
                              ${ROS2_TEST_PATH}/negative_tests.cpp)
  target_link_libraries(sdl_depth_info_topic_exec fast_mapping_lib)
  ament_target_dependencies(sdl_depth_info_topic_exec ${dependencies})
  ament_add_test(sdl_depth_info_topic-test
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/${ROS2_TEST_PATH}/sdl_depth_info_topic_test_launch.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    ENV
      TEST_LAUNCH_DIR=${TEST_LAUNCH_DIR}
      TEST_EXECUTABLE=$<TARGET_FILE:sdl_depth_info_topic_exec>
  )
endif()
