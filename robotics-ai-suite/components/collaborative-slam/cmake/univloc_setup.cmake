# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE
      "Release"
      CACHE STRING "" FORCE)
endif()
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")

set(UNIVLOC_VERSION_MAJOR 2023)
set(UNIVLOC_VERSION_MINOR 1)
set(UNIVLOC_VERSION_PATCH 1)
set(UNIVLOC_VERSION_STRING
    "${UNIVLOC_VERSION_MAJOR}.${UNIVLOC_VERSION_MINOR}.${UNIVLOC_VERSION_PATCH}"
)

# NOTE: In order to use Valgrind, we cannot build with native It turns out that
# some gcc builds (depends on the distro) set _FORTIFY_SOURCE internally
# https://github.com/neovim/neovim/issues/2557
add_compile_options(-Wno-pedantic -Werror)
add_compile_options(-Wall -Wextra -fstack-protector-all -U_FORTIFY_SOURCE
                    -D_FORTIFY_SOURCE=1)
if(CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 10)
  add_compile_options(-Wno-aggressive-loop-optimizations)
endif()

option(USE_PREBUILT_DEPS "Use prebuilt 3rd party dependencies" OFF)
option(USE_SLAM_SHAREDLIBS_PATH "Use prebuilt library" OFF)

if(NOT DEFINED BUILD_NATIVE)
  set(BUILD_NATIVE ON)
endif()

if(NOT DEFINED BUILD_TREMONT)
  set(BUILD_TREMONT OFF)
endif()

if(${BUILD_TREMONT})
  set(BUILD_NATIVE OFF)
endif()

if(${BUILD_NATIVE} AND CMAKE_BUILD_TYPE MATCHES Release)
  add_compile_options(-march=native)
  message(STATUS "Building native!")
elseif(${BUILD_TREMONT} AND CMAKE_BUILD_TYPE MATCHES Release)
  add_compile_options(-march=tremont -mtune=generic)
  message(STATUS "Building tremont arch!")
else()
  message(STATUS "Native/tremont build disabled!")
endif()

if(CMAKE_BUILD_TYPE MATCHES Debug)
  add_compile_options(-ggdb3)
  message(STATUS "Building in debug mode!")
endif()

set(USE_SSE_ORB
    OFF
    CACHE BOOL "Enable SSE3 instruction for ORB extraction (-msse3)")
if(USE_SSE_ORB)
  set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -msse3")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -msse3")
  message(STATUS "SSE3 for ORB extraction (-msse3): ENABLED")
else()
  message(STATUS "SSE3 for ORB extraction (-msse3): DISABLED")
endif()

set(USE_SSE_FP_MATH
    OFF
    CACHE BOOL
          "Enable SSE instruction for floating-point operation (-mfpmath=sse)")
if(USE_SSE_FP_MATH)
  set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -mfpmath=sse")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mfpmath=sse")
  message(STATUS "SSE for floating-point operation (-mfpmath=sse): ENABLED")
else()
  message(STATUS "SSE for floating-point operation (-mfpmath=sse): DISABLED")
endif()

# ----- Set options for debugging -----

option(USE_CCACHE "Use ccache to accelerate build" OFF)
find_program(CCACHE_EXE ccache)
if(USE_CCACHE AND CCACHE_EXE)
  set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE "${CCACHE_EXE}")
  set_property(GLOBAL PROPERTY RULE_LAUNCH_LINK "${CCACHE_EXE}")
  message(STATUS "ccache: Enabled")
else()
  set(USE_CCACHE OFF)
  message(STATUS "ccache: Disabled")
endif()

option(
  USE_SANITIZER
  "Enable Address/Memory sanitizer (set env as ASAN_OPTIONS=detect_leaks=1)"
  OFF)
if(USE_SANITIZER)
  set(CMAKE_C_FLAGS
      "${CMAKE_C_FLAGS} -fno-omit-frame-pointer -fsanitize=address")
  set(CMAKE_CXX_FLAGS
      "${CMAKE_CXX_FLAGS} -fno-omit-frame-pointer -fsanitize=address")
  set(CMAKE_EXE_LINKER_FLAGS
      "${CMAKE_EXE_LINKER_FLAGS} -fno-omit-frame-pointer -fsanitize=address")
  set(CMAKE_SHARED_LINKER_FLAGS
      "${CMAKE_SHARED_LINKER_FLAGS} -fno-omit-frame-pointer -fsanitize=address")
  message(STATUS "Address/Memory sanitizer: ENABLED")
else()
  message(STATUS "Address/Memory sanitizer: DISABLED")
endif()

option(USE_GOOGLE_PERFTOOLS "Enable profiler of google-perftools" OFF)
if(USE_GOOGLE_PERFTOOLS)
  message(STATUS "Google Perftools: ENABLED")
  # Gperftools
  find_package(Gperftools REQUIRED)
  include_directories(${GPERFTOOLS_INCLUDE_DIRS})
else()
  message(STATUS "Google Perftools: DISABLED")
endif()

option(USE_OPENMP "Use OpenMP" OFF)
if(USE_OPENMP)
  find_package(OpenMP)
  message(FATAL_ERROR "OMP")
  if(OpenMP_FOUND)
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${OpenMP_C_FLAGS}")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
    add_definitions(-DUSE_OPENMP)
    message(STATUS "OpenMP: ENABLED")
  else()
    message(STATUS "OpenMP: DISABLED")
  endif()
else()
  message(STATUS "OpenMP: DISABLED")

endif()

find_package(Threads REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(spdlog REQUIRED)

if(NOT USE_PREBUILT_DEPS)

  find_package(univloc_dependencies REQUIRED)

else()

  find_package(DBoW2 REQUIRED)
  # for find_package(g2o REQUIRED), FindOpenGL module will be called and if
  # OpenGL_GL_PREFERENCE variable is not set, it will produce cmake warning
  # check https://cmake.org/cmake/help/latest/policy/CMP0072.html here we will
  # set as GLVND to align with the default value inside g2o cmake file
  set(OpenGL_GL_PREFERENCE "GLVND")
  find_package(g2o-intel REQUIRED)
  find_package(nlohmann_json REQUIRED)
  find_package(Boost REQUIRED)

endif()

find_package(OpenCV REQUIRED COMPONENTS core imgcodecs videoio features2d
                                        calib3d highgui)
