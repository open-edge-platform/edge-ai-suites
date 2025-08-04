# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.12)
project(trac_ik_lib)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Wshadow -Werror)
endif()

find_package(ament_cmake REQUIRED)
find_package(eigen3_cmake_module REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(kdl_parser REQUIRED)
#find_package(NLopt REQUIRED)
find_package(rclcpp REQUIRED)
find_package(urdf REQUIRED)

add_library(${PROJECT_NAME} SHARED
  src/kdl_tl.cpp
  src/nlopt_ik.cpp
  src/trac_ik.cpp)

# C++20 standard guarantees `std::chrono::system_clock` measures Unix Time
# i.e. `std::chrono::{duration, time_point}` can then replace
# `boost::posix_time::{time_duration, ptime}`

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${NLOPT_INCLUDE_DIRS}
)

target_compile_definitions(${PROJECT_NAME} PRIVATE "TRAC_IK_BUILDING_LIBRARY")

# Needed since NLopt is not an ament package
target_link_libraries(${PROJECT_NAME}
	#${NLOPT_LIBRARIES}
	-lnlopt_cxx
	-lnlopt
)

ament_target_dependencies(${PROJECT_NAME}
  ament_cmake
  Eigen3
  kdl_parser
  rclcpp
  urdf
)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)

ament_export_dependencies(
  ament_cmake
  kdl_parser
  #  NLopt
  rclcpp
  urdf
)

install(DIRECTORY include/
  DESTINATION include
)

install(TARGETS ${PROJECT_NAME}
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
    find_package(ament_lint_auto REQUIRED)
    list(APPEND AMENT_LINT_AUTO_EXCLUDE
      ament_cmake_cppcheck
      ament_cmake_uncrustify
    )

    ament_lint_auto_find_test_dependencies()

    # Else there are erroneous results for `.h` headers
    ament_cppcheck(LANGUAGE "c++")
    ament_uncrustify(LANGUAGE "C++")
endif()

ament_package()
