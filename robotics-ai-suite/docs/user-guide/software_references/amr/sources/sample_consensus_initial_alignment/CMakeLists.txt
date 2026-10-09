# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5 FATAL_ERROR)
set(target oneapi_scia)
set(CMAKE_CXX_COMPILER icpx)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS "-fsycl")
project(${target})

find_package(PCL 1.12 REQUIRED)

if (WIN32)
find_package(PCL-ONEAPI 1.12 REQUIRED)
include_directories(${PCL_INCLUDE_DIRS} ${PCL-ONEAPI_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS} ${PCL-ONEAPI_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS} ${PCL-ONEAPI_DEFINITIONS})
else()
include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})
endif()

add_executable (${target} oneapi_scia.cpp)
target_link_libraries (${target} pcl_oneapi_registration ${PCL_LIBRARIES})
