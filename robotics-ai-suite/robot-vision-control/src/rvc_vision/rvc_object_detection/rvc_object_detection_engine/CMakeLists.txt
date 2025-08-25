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

project(rvc_object_detection_engine)
add_compile_options(-std=c++17)

option(USE_SENSOR_DATA "USE_SENSOR_DATA" ON)

if (USE_SENSOR_DATA)
  add_compile_definitions(BUILD_SENSOR_DATA)
endif()

# find ROS dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(rvc_vision_messages REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(pluginlib REQUIRED)
#find non-ROS dependencies

find_package(rvc_ai_interface REQUIRED)

message("Openvino version is " ${InferenceEngine_VERSION})
#include_directories(include ${OpenCV_INCLUDE_DIRS} )
include_directories(include  )

add_library(rvc_object_detection_composable_plugin SHARED
    src/rvc_object_detection.cpp
)

ament_target_dependencies(rvc_object_detection_composable_plugin
    ament_index_cpp
    rclcpp
    sensor_msgs
    rvc_vision_messages
    cv_bridge
    image_transport
    rclcpp_components
    rvc_ai_interface
    pluginlib
)
target_compile_features(rvc_object_detection_composable_plugin PRIVATE cxx_std_17)
target_link_libraries(rvc_object_detection_composable_plugin ${OpenCV_LIBS})

rclcpp_components_register_node(rvc_object_detection_composable_plugin PLUGIN "RVC::ObjectDetection" EXECUTABLE rvc_object_detection)

ament_target_dependencies(rvc_object_detection_composable_plugin
    rclcpp
    rclcpp_components
    class_loader
)
install(TARGETS rvc_object_detection_composable_plugin
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
#ament_export_include_directories(include)
ament_export_libraries(rvc_object_detection_composable_plugin)
ament_export_dependencies(${dependencies})

ament_package()
