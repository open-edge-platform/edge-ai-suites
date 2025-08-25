# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(univloc_msgs)

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  # we dont use add_compile_options with pedantic in message packages because
  # the Python C extensions dont comply with it
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic -Werror")
endif()

if("$ENV{ROS_VERSION}" EQUAL "1")
  find_package(
    catkin REQUIRED COMPONENTS message_generation message_runtime geometry_msgs
                               roscpp sensor_msgs std_msgs)

  add_message_files(
    FILES
    Descriptor.msg
    CvKeypoint.msg
    Keyframe.msg
    KeyframeUpdate.msg
    Landmark.msg
    CameraInfo.msg
    Map.msg
    Node.msg
    ImuStatus.msg
    LidarStatus.msg
    Octree.msg
    Ofusion.msg
    VoxelBlock.msg
    OctreeParam.msg)
  generate_messages(DEPENDENCIES geometry_msgs sensor_msgs std_msgs)

  add_service_files(FILES MapBasedComm.srv)

  catkin_package(CATKIN_DEPENDS message_runtime)

  include_directories(${catkin_INCLUDE_DIRS})

elseif("$ENV{ROS_VERSION}" EQUAL "2")
  find_package(ament_cmake REQUIRED)
  find_package(rosidl_default_generators REQUIRED)
  # find_package(message_generation REQUIRED) find_package(message_runtime
  # REQUIRED)
  find_package(geometry_msgs REQUIRED)
  find_package(rclcpp REQUIRED)
  find_package(sensor_msgs REQUIRED)
  find_package(std_msgs REQUIRED)

  set(INTERFACES_LIST
      "msg/Descriptor.msg"
      "msg/CvKeypoint.msg"
      "msg/Keyframe.msg"
      "msg/KeyframeUpdate.msg"
      "msg/Landmark.msg"
      "msg/CameraInfo.msg"
      "msg/Map.msg"
      "msg/Node.msg"
      "msg/ImuStatus.msg"
      "msg/LidarStatus.msg"
      "msg/Octree.msg"
      "msg/Ofusion.msg"
      "msg/VoxelBlock.msg"
      "msg/OctreeParam.msg"
      "srv/MapBasedComm.srv")

  set(DEPENDENCIES_LIST "std_msgs" "sensor_msgs" "geometry_msgs")

  rosidl_generate_interfaces(${PROJECT_NAME} ${INTERFACES_LIST} DEPENDENCIES
                             ${DEPENDENCIES_LIST})

  ament_export_dependencies(rosidl_default_runtime)
  ament_package()
endif()
