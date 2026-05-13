# INTEL CONFIDENTIAL
#
# Copyright (C) 2021-2022 Intel Corporation.
#
# This software and the related documents are Intel copyrighted materials, and your use of
# them is governed by the express license under which they were provided to you (License).
# Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
# disclose or transmit this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties,
# other than those that are expressly stated in the License.

cmake_minimum_required(VERSION 3.5)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
project(HCE_AI)

option(MINIMAL_PACKAGE "Build a minimal package of HCE AI Inference service" OFF)
option(USE_GRPC_API "Build with gRPC API of HCE AI Inference service" ON)
option(ENABLE_VAAPI "Parameter to enable VAAPI for image pre-processing" OFF)

set(CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake" ${CMAKE_MODULE_PATH})

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# set(MY_LIBRARY_VERSION_MAJOR 0 CACHE STRING "major version" FORCE)
# set(MY_LIBRARY_VERSION_MINOR 1 CACHE STRING "minor version" FORCE)
# set(MY_LIBRARY_VERSION ${MY_LIBRARY_VERSION_MAJOR}.${MY_LIBRARY_VERSION_MINOR} CACHE STRING "version" FORCE)

if (WIN32)
  set(HCE_AI_COMPILER_FLAGS "/GS")
	set(HCE_AI_SHARED_LINKER_FLAGS "/DYNAMICBASE /NXCOMPAT")
	set(HCE_AI_EXE_LINKER_FLAGS "/ALLOWISOLATION")
elseif (UNIX)
	set(HCE_AI_COMPILER_FLAGS "-Wformat -Wformat-security -Werror=format-security -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fstack-clash-protection -fno-strict-overflow -fwrapv -fno-delete-null-pointer-checks -fPIE -fPIC")
	set(HCE_AI_SHARED_LINKER_FLAGS "-z relro -z now -z noexecstack")
endif()
set(CMAKE_CXX_FLAGS  "${CMAKE_CXX_FLAGS} ${HCE_AI_COMPILER_FLAGS}")
set(CMAKE_C_FLAGS  "${CMAKE_C_FLAGS} ${HCE_AI_COMPILER_FLAGS}")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${HCE_AI_SHARED_LINKER_FLAGS} ${HCE_AI_EXE_LINKER_FLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${HCE_AI_SHARED_LINKER_FLAGS}")

if (NOT EXISTS ${CMAKE_BINARY_DIR}/CMakeCache.txt)
  if (NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE)
  endif()
endif()

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)

add_subdirectory(ai_inference)

# add_subdirectory(ai_structuring)