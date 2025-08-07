# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
## BEGIN_TUTORIAL
## This CMakeLists.txt file for rviz_plugin_tutorials builds the
## TeleopPanel, ImuDisplay, and PlantFlagTool tutorials.

cmake_minimum_required(VERSION 3.8)
project(rvc_panel_rviz2_plugin)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

option(USE_SENSOR_DATA "USE_SENSOR_DATA" ON)

if (USE_SENSOR_DATA)
  add_compile_definitions(BUILD_SENSOR_DATA)
endif()

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(pluginlib REQUIRED)
find_package(Qt5 REQUIRED COMPONENTS Widgets)
find_package(rclcpp REQUIRED)
find_package(rviz_common REQUIRED)
find_package(rviz_rendering REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(image_transport REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(gui_settings REQUIRED)
find_package(rvc_messages REQUIRED)
find_package(rviz_default_plugins REQUIRED)
find_package(state_machine_msgs REQUIRED)

## This setting causes Qt's "MOC" generation to happen automatically.
set(CMAKE_AUTOMOC ON)

## Here we specify the list of source files.
## The generated MOC files are included automatically as headers.
set(SRC_FILES
  src/rvc_panel.cpp
)

## An rviz plugin is just a shared library, so here we declare the
## library to be called ``${PROJECT_NAME}`` (which is
## "rviz_plugin_tutorials", or whatever your version of this project
## is called) and specify the list of source files we collected above
## in ``${SRC_FILES}``. We also add the needed dependencies.
add_library(${PROJECT_NAME} SHARED ${SRC_FILES})
ament_target_dependencies(${PROJECT_NAME}
  geometry_msgs
  rclcpp
  rviz_common
  rviz_rendering
  sensor_msgs
  std_msgs 
  tf2_ros 
  geometry_msgs 
  tf2_geometry_msgs 
  std_srvs
  gui_settings
  rvc_messages
  rviz_default_plugins
  state_machine_msgs
  image_transport
)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${Qt5Widgets_INCLUDE_DIRS})

## Here we export the plugins and meshes so they can be found by RViz at runtime.
pluginlib_export_plugin_description_file(rviz_common plugin_description.xml)
#register_rviz_ogre_media_exports(DIRECTORIES "media")

## END_TUTORIAL

ament_export_dependencies(
  geometry_msgs
  rclcpp
  rviz_common
  rviz_rendering
  sensor_msgs)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

install(TARGETS
  ${PROJECT_NAME}
  ARCHIVE DESTINATION lib/${PROJECT_NAME}
  LIBRARY DESTINATION lib/${PROJECT_NAME}
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

#install(DIRECTORY media/ DESTINATION share/${PROJECT_NAME}/media)

install(DIRECTORY icons/ DESTINATION share/${PROJECT_NAME}/icons)

#install(PROGRAMS scripts/send_test_msgs.py DESTINATION lib/${PROJECT_NAME})

ament_package()
