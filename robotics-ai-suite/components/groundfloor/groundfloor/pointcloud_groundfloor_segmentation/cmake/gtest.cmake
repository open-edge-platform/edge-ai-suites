# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

if(NOT TARGET GTest::gtest)
  find_package(GTest QUIET CONFIG)
  if (NOT GTest_FOUND)
    #As Ubuntu never ships precompiled gtest libraries, build them on-the-fly from source
    #requires gtest-dev package to be intalled
    set(gtest_source_paths /usr/src/googletest/ /usr/src/gtest/ ${GTEST_SRC_PATH})
    foreach (src_path IN LISTS gtest_source_paths)
      if(EXISTS ${src_path}/CMakeLists.txt)
        set(gtest_src_path ${src_path})
        break()
      endif()
    endforeach()
    if(gtest_src_path)
      message(STATUS "Using gtest source build from: ${gtest_src_path}")
      set(BUILD_SHARED_LIBS_SAVED "${BUILD_SHARED_LIBS}")
      set(BUILD_SHARED_LIBS OFF)
      set(CMAKE_POSITION_INDEPENDENT_CODE ON)
      add_subdirectory(${gtest_src_path} gtest EXCLUDE_FROM_ALL)
      set(BUILD_SHARED_LIBS "${BUILD_SHARED_LIBS_SAVED}")
      add_library(GTest::gtest ALIAS gtest)
      add_library(GTest::gtest_main ALIAS gtest_main)
    else()
      message(ERROR "Neither installed gtest nor sources found.")
    endif()
  else()
    message(STATUS "Using installed gtest")
  endif()
endif()
