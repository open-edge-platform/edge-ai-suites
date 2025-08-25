# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
#if(POLICY CMP0012)
#  cmake_policy(SET CMP0012 NEW)
#endif()

project(fast_mapping_lib)

if (NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release")
endif()
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Werror -Wno-missing-field-initializers -Wno-deprecated-copy -std=c++17")
if (CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 8.0)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-error=class-memaccess")
endif()

find_package(OpenCV REQUIRED)
find_package(Eigen3 REQUIRED)

# Includes
include_directories(
  include
  ${EIGEN3_INCLUDE_DIRS}
)

add_definitions(-DSE_FIELD_TYPE=OFusion -Wno-unknown-pragmas)

# Fastmapping common code dependencies
set(${PROJECT_NAME}_deps
  ${OpenCV_LIBS}
  ${EIGEN3_LIBS}
)

add_library(${PROJECT_NAME} STATIC
  logger.cpp
  OctoMap.cpp
)

# External libraries needed for building fast_mapping
target_link_libraries(${PROJECT_NAME} ${fast_mapping_lib_deps})
