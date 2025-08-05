# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(robot_config_plugins)

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  # we dont use add_compile_options with pedantic in message packages
  # because the Python C extensions dont comply with it
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic -Wno-inconsistent-missing-override")
endif()

if(WIN32)
  add_compile_definitions(
    # For math constants
    _USE_MATH_DEFINES
    # Minimize Windows namespace collision
    NOMINMAX
    WIN32_LEAN_AND_MEAN
  )
endif()

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(gazebo_dev REQUIRED)
find_package(gazebo_ros REQUIRED)
find_package(gazebo REQUIRED)
find_package(gazebo_plugins REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_srvs REQUIRED)
find_package(std_msgs REQUIRED)


link_directories(
  ${gazebo_dev_LIBRARY_DIRS}
)

# gazebo_ros_namespace
add_library(gazebo_ros_namespace SHARED
  src/gazebo_ros_namespace.cpp
)
ament_target_dependencies(gazebo_ros_namespace 
  "gazebo_dev"
  "gazebo_ros"
  "std_srvs"
)

ament_export_libraries(gazebo_ros_namespace)
ament_export_dependencies(gazebo_dev)



add_library(ConveyorBeltPlugin SHARED src/ConveyorBeltPlugin.cpp)

rosidl_generate_interfaces(${PROJECT_NAME}
  "interface/srv/ConveyorBeltControl.srv"
  "interface/msg/ConveyorBeltState.msg"
  DEPENDENCIES builtin_interfaces std_msgs
)

if("$ENV{ROS_DISTRO}" STREQUAL "foxy")

  rosidl_target_interfaces(ConveyorBeltPlugin
    ${PROJECT_NAME} "rosidl_typesupport_cpp"
  )

else()

  rosidl_get_typesupport_target(cpp_typesupport_target  ${PROJECT_NAME} "rosidl_typesupport_cpp")
  target_link_libraries(ConveyorBeltPlugin ${cpp_typesupport_target})

endif()

target_include_directories(ConveyorBeltPlugin  PUBLIC include)
ament_target_dependencies(ConveyorBeltPlugin
  "gazebo_ros"
  "gazebo_dev"
  "rclcpp"
  "std_msgs"
  "std_srvs"
)


ament_export_libraries(ConveyorBeltPlugin)

ament_export_dependencies(
  rosidl_default_runtime
)

ament_package()

install(
  PROGRAMS
    DESTINATION lib/${PROJECT_NAME}/
)

install(
  TARGETS
  gazebo_ros_namespace
  ConveyorBeltPlugin
  LIBRARY DESTINATION lib
  )
