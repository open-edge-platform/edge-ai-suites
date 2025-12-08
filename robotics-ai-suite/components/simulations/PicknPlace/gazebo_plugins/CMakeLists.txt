# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(robot_config_plugins)

# Use C++17 for Gazebo Harmonic, C++14 minimum for Fortress
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic -Wno-inconsistent-missing-override")
endif()

if(WIN32)
  add_compile_definitions(
    _USE_MATH_DEFINES
    NOMINMAX
    WIN32_LEAN_AND_MEAN
  )
endif()

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_srvs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(ament_index_cpp REQUIRED)

# Set ROS distribution
if(DEFINED ENV{ROS_DISTRO})
  set(ROS_DISTRO $ENV{ROS_DISTRO})
else()
  set(ROS_DISTRO "humble")  # default
endif()

# Configure Gazebo based on ROS distribution
if(ROS_DISTRO STREQUAL "jazzy")
  # Jazzy: Gazebo Harmonic (8.x) with vendor packages
  message(STATUS "🔧 Configuring for ROS Jazzy (Ubuntu Noble + Gazebo Harmonic)")

  find_package(ros_gz REQUIRED) # Find ROS-Gazebo bridge
  find_package(gz_sim_vendor REQUIRED)  # This pulls in all other vendors
  find_package(sdformat_vendor REQUIRED)

   # Add include paths
  set(GZ_VENDOR_BASE "/opt/ros/jazzy/opt")
  include_directories(
    "${GZ_VENDOR_BASE}/gz_sim_vendor/include/gz/sim8"
    "${GZ_VENDOR_BASE}/gz_common_vendor/include/gz/common5"
    "${GZ_VENDOR_BASE}/gz_msgs_vendor/include/gz/msgs10"
    "${GZ_VENDOR_BASE}/gz_transport_vendor/include/gz/transport13"
    "${GZ_VENDOR_BASE}/gz_math_vendor/include/gz/math7"
    "${GZ_VENDOR_BASE}/gz_plugin_vendor/include/gz/plugin2"
    "${GZ_VENDOR_BASE}/gz_sensors_vendor/include/gz/sensors8"
    "${GZ_VENDOR_BASE}/gz_rendering_vendor/include/gz/rendering8"
    "${GZ_VENDOR_BASE}/gz_physics_vendor/include/gz/physics7"
    "${GZ_VENDOR_BASE}/gz_utils_vendor/include/gz/utils2"
    "${GZ_VENDOR_BASE}/sdformat_vendor/include/gz/sdformat14"
  )
  
  set(GAZEBO_DEPS "ros_gz" "gz_sim_vendor" "sdformat_vendor")
  
else()
  # Humble: Gazebo Fortress (6.x) with ignition packages
  message(STATUS "🔧 Configuring for ROS Humble (Ubuntu Jammy + Gazebo Fortress)")
  find_package(ros_gz REQUIRED)
  
  # Add include directories directly
  include_directories(
    /usr/include/gz/sim7
    /usr/include/gz/common5
    /usr/include/gz/msgs9
    /usr/include/gz/transport12
    /usr/include/gz/math7
    /usr/include/gz/plugin2
    /usr/include/gz/sensors7
    /usr/include/gz/rendering7
    /usr/include/gz/physics6
    /usr/include/gz/utils2          # For gz/utils/ImplPtr.hh
    /usr/include/gz/cmake3          # For gz/utilities/SuppressWarning.hh
    /usr/include/gz/fuel_tools8
    /usr/include/gz/gui7
    /usr/include/gz/tools2
    
    # Ignition compatibility paths (fallback)
    /usr/include/ignition/gazebo6
    /usr/include/ignition/common4
    /usr/include/ignition/msgs8
    /usr/include/ignition/transport11
    /usr/include/ignition/math6
    /usr/include/ignition/plugin1
    /usr/include/ignition/utils1
    /usr/include/ignition/cmake2
    
    # SDFormat
    /usr/include/gz/sdformat13
    /usr/include/ignition/sdformat12
    
    # System includes
    /usr/include
  )
  
   # Add library directories
  link_directories(/usr/lib/x86_64-linux-gnu)
  
  set(GAZEBO_DEPS "ros_gz")
  set(GAZEBO_LIBS 
    gz-sim7
    gz-common5
    gz-msgs9
    gz-transport12
    gz-math7
    gz-plugin2
    gz-utils2
    gz-sensors7
    gz-rendering7
    gz-physics6
    gz-cmake3
    gz-fuel_tools8
    gz-gui7
    gz-tools2
    sdformat13
  )
  
  message(STATUS "Using ros_gz meta-package for Humble (includes: bridge, sim, image, demos)")
endif()

# Generate ROS interfaces FIRST (before using them)
rosidl_generate_interfaces(${PROJECT_NAME}
  "interface/srv/ConveyorBeltControl.srv"
  "interface/msg/ConveyorBeltState.msg"
  DEPENDENCIES builtin_interfaces std_msgs
)

# VacuumToolPlugin - compatible with both Fortress (7.x) and Harmonic (8.x)
add_library(VacuumToolPlugin SHARED
  src/vacuum_tool_plugin.cpp
)

target_include_directories(VacuumToolPlugin PUBLIC
  include
)

ament_target_dependencies(VacuumToolPlugin
  "rclcpp"
  "std_srvs"
  "std_msgs"
  "ament_index_cpp"
  ${GAZEBO_DEPS}
)

# ConveyorBeltPlugin - compatible with both Fortress and Harmonic
add_library(ConveyorBeltPlugin SHARED 
  src/ConveyorBeltPlugin.cpp
)

target_include_directories(ConveyorBeltPlugin PUBLIC 
  include
)

ament_target_dependencies(ConveyorBeltPlugin
  ${GAZEBO_DEPS}
  "rclcpp"
  "std_msgs"
  "std_srvs"
)

# Link Ignition libraries for Humble
if(ROS_DISTRO STREQUAL "humble")
  target_link_libraries(VacuumToolPlugin ${IGNITION_LIBS})
  target_link_libraries(ConveyorBeltPlugin ${IGNITION_LIBS})
endif()

# Link generated interfaces to ConveyorBeltPlugin
rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(ConveyorBeltPlugin ${cpp_typesupport_target})

# Export libraries and dependencies
ament_export_libraries(ConveyorBeltPlugin VacuumToolPlugin)
ament_export_dependencies(${GAZEBO_DEPS})
ament_export_dependencies(rosidl_default_runtime)

# Install targets
install(
  TARGETS
  ConveyorBeltPlugin
  VacuumToolPlugin
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION bin
)

# Install headers (if needed by other packages)
install(
  DIRECTORY include/
  DESTINATION include
)

ament_package()
