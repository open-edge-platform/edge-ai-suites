# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5 FATAL_ERROR)
set(CMAKE_CXX_COMPILER icpx)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS "-fsycl")

project(greedy_projection)

find_package(PCL 1.2 REQUIRED)

include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

add_executable (greedy_projection greedy_projection.cpp)
target_link_libraries (greedy_projection ${PCL_LIBRARIES})

# The URL of the file
set (pcd_url
  "https://raw.githubusercontent.com/PointCloudLibrary/pcl/master/test/bun0.pcd")

foreach(item ${pcd_url})
  get_filename_component(filename ${item} NAME)
  message(STATUS "Downloading files ${filename}")
  if (NOT EXISTS "${filename}")
    execute_process(
      COMMAND wget "${item}"
    )
  endif()
endforeach()
