# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(send_localization)

set(CMAKE_CXX_STANDARD 17)
set(GCC_COVERAGE_COMPILE_FLAGS "-fno-strict-overflow -fno-delete-null-pointer-checks")

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(nav2_core REQUIRED)
find_package(its_planner REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav2_amcl REQUIRED)
find_package(std_srvs REQUIRED)

set(library_name send_localization_core)
set(executable_name send_localization)

set(dependencies
  rclcpp
  nav2_msgs
  nav2_core
  its_planner
  nav2_costmap_2d
  geometry_msgs
  nav2_amcl
  std_srvs
)

# Library
add_library(${library_name} SHARED
  src/send_localization.cpp
)

ament_target_dependencies(${library_name}
  ${dependencies}
)

# Executable
add_executable(${executable_name}
  src/main.cpp
)

target_link_libraries(${executable_name} ${library_name})

ament_target_dependencies(${executable_name}
  ${dependencies}
)

# rclcpp_components_register_nodes(${library_name} "SendLocalization")

install(TARGETS ${library_name}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(TARGETS
  ${executable_name}
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  add_subdirectory(test)
endif()

ament_export_dependencies(${dependencies})
ament_package()
