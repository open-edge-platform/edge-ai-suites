# INTEL CONFIDENTIAL
#
# Copyright (C) 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you (License). Unless the License provides otherwise,
# you may not use, modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written
# permission.
#
# This software and the related documents are provided as is, with no
# express or implied warranties, other than those that are expressly stated
# in the License.

cmake_minimum_required(VERSION 3.8)

# Suppress CMake developer warnings from third-party dependencies (PCL/FLANN)
set(CMAKE_SUPPRESS_DEVELOPER_WARNINGS 1 CACHE INTERNAL "No dev warnings")

# Set CMake policies BEFORE project() to suppress warnings from dependencies
if(POLICY CMP0074)
  cmake_policy(SET CMP0074 NEW)  # Use <PackageName>_ROOT variables
endif()
if(POLICY CMP0144)
  cmake_policy(SET CMP0144 NEW)  # Use upper-case <PACKAGENAME>_ROOT variables
endif()

project(rvc_pose_detector)
set(PROJECT_NAME_PLUGIN ${PROJECT_NAME}_composable_plugin)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
  add_compile_definitions(POSE_STAMPED)
endif()

option(USE_SENSOR_DATA "USE_SENSOR_DATA" ON)

if (USE_SENSOR_DATA)
  add_compile_definitions(BUILD_SENSOR_DATA)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)

find_package(ament_index_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(pcl_conversions REQUIRED)
find_package(tf2_eigen REQUIRED)

find_package(rvc_messages REQUIRED)
find_package(rvc_vision_messages REQUIRED)
find_package(message_filters REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_eigen REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(tf2_sensor_msgs REQUIRED)

# find non-ROS dependencies
find_package(PCL REQUIRED)

# configure our executable
add_library(${PROJECT_NAME_PLUGIN} SHARED
    src/rvc_pose_detector.cpp
    src/matcher.cpp
)
ament_target_dependencies(${PROJECT_NAME_PLUGIN}
    ament_index_cpp
    rclcpp
    std_msgs
    sensor_msgs
    geometry_msgs
    rvc_messages
    rvc_vision_messages
    rclcpp_components
    class_loader
    pcl_conversions
    message_filters
    tf2_eigen
    tf2_ros
    tf2_geometry_msgs 
    tf2_sensor_msgs 
)
target_include_directories(${PROJECT_NAME_PLUGIN} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${PCL_INCLUDE_DIRS}
)

target_precompile_headers(${PROJECT_NAME_PLUGIN} PRIVATE 
  include/rvc_pose_detector.hpp
  include/matcher.hpp
)

target_compile_features(${PROJECT_NAME_PLUGIN} PRIVATE c_std_99 cxx_std_17)  # Require C99 and C++17
target_link_libraries(${PROJECT_NAME_PLUGIN} ${PCL_LIBRARIES})

rclcpp_components_register_node(${PROJECT_NAME_PLUGIN} PLUGIN "RVC::PoseDetector" EXECUTABLE ${PROJECT_NAME})


install(TARGETS ${PROJECT_NAME_PLUGIN}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # uncomment the line when a copyright and license is not present in all source files
  #set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # uncomment the line when this package is not in a git repo
  #set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

install(DIRECTORY config DESTINATION share/${PROJECT_NAME})

ament_package()
