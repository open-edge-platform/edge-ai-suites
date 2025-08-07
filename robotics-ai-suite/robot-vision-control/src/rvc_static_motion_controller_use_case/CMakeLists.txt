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

cmake_minimum_required(VERSION 3.5)
project(rvc_static_motion_controller_use_case)

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

option(USE_SENSOR_DATA "USE_SENSOR_DATA" ON)

if (USE_SENSOR_DATA)
  add_compile_definitions(BUILD_SENSOR_DATA)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_eigen REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(gui_settings REQUIRED)
find_package(rvc_messages REQUIRED)
find_package(state_machine_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rvc_motion_controller_interface)
find_package(rvc_grasp_interface)
find_package(sensor_msgs)



find_package(PkgConfig REQUIRED)

add_executable(${PROJECT_NAME} 
    src/node_main.cpp
    src/state_machine.cpp
)

ament_target_dependencies(${PROJECT_NAME}
  ament_cmake
  std_msgs
  rclcpp
  tf2_ros
  tf2_geometry_msgs
  tf2_eigen
  tf2
  gui_settings
  rvc_messages
  state_machine_msgs
  std_srvs
  rvc_motion_controller_interface
  pluginlib
  rvc_grasp_interface
  sensor_msgs
)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

  #target_link_libraries(${PROJECT_NAME})

install(TARGETS ${PROJECT_NAME}
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY config launch urdf meshes cameraurdf
	DESTINATION share/${PROJECT_NAME})

install(
  DIRECTORY include/
  DESTINATION include
)

ament_export_include_directories(
  include
)

ament_package()
