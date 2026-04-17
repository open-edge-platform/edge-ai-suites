# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.8)
project(yolo)

set(yolo_MAJOR_VERSION 1)
set(yolo_MINOR_VERSION 0)
set(yolo_PATCH_VERSION 0)
set(yolo_VERSION
  ${yolo_MAJOR_VERSION}.${yolo_MINOR_VERSION}.${yolo_PATCH_VERSION})

set(CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE OFF)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# CI/Build Performance Optimizations
if(CMAKE_BUILD_TYPE STREQUAL "Release" OR CMAKE_BUILD_TYPE STREQUAL "RelWithDebInfo")
    # Detect available linkers
    find_program(LLD_FOUND lld)
    find_program(GOLD_FOUND ld.gold)

    if(LLD_FOUND)
        message(STATUS "Using LLD linker for faster linking")
        set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fuse-ld=lld -Wl,--threads")
        set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -fuse-ld=lld -Wl,--threads")
    elseif(GOLD_FOUND)
        message(STATUS "Using Gold linker for faster linking")
        set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fuse-ld=gold -Wl,--threads -Wl,--reduce-memory-overheads -Wl,--no-keep-memory")
        set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -fuse-ld=gold -Wl,--threads -Wl,--reduce-memory-overheads -Wl,--no-keep-memory")
    else()
        message(STATUS "Using default system linker")
        set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--threads -Wl,--reduce-memory-overheads -Wl,--no-keep-memory")
        set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--threads -Wl,--reduce-memory-overheads -Wl,--no-keep-memory")
    endif()
endif()

# Enable ccache if available
find_program(CCACHE_FOUND ccache)
if(CCACHE_FOUND)
    set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE ccache)
    set_property(GLOBAL PROPERTY RULE_LAUNCH_LINK ccache)
    message(STATUS "Using ccache for faster compilation")
endif()

# Optimize compiler flags for CI builds
if(DEFINED ENV{CI} OR CMAKE_BUILD_TYPE STREQUAL "Release")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC -O2 -mavx -mavx2 -pthread -g1")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC -O1 -mavx -mavx2 -pthread -g")
endif()

include(FetchContent)
FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG v1.17.0
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

option(USE_PLOT "Draw plots using MATPLOT++" OFF)

find_package(GTest REQUIRED)
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(Python REQUIRED COMPONENTS Interpreter Development)
find_package(yolo_msgs REQUIRED)
find_package(OpenVINO REQUIRED)
find_package(OpenCV REQUIRED)

set(OpenCV_INCLUDE_DIRS /usr/local/include /usr/local/include/opencv2)
set(OpenCV_LIB_DIR /usr/local/lib)

# ---------------------- EXECUTABLES ----------------------
add_executable(yolo src/YoloMain.cpp)
add_executable(benchmarkYolo src/YoloBenchmark.cpp)

if(USE_PLOT)
  add_subdirectory(matplotplusplus)
  target_link_libraries(yolo PRIVATE matplot)
  target_link_libraries(benchmarkYolo PRIVATE matplot)
  target_compile_definitions(benchmarkYolo PRIVATE PLOT)
  target_compile_definitions(yolo PRIVATE PLOT)
endif()

function(configure_target target)
  target_link_libraries(${target} PRIVATE
    ${std_msgs_LIBRARIES}
    ${sensor_msgs_LIBRARIES}
    ${rclcpp_LIBRARIES}
    ${tf2_LIBRARIES}
    ${tf2_ros_LIBRARIES}
    ${tf2_msgs_LIBRARIES}
    openvino::runtime
    ${OpenCV_LIBS}
    ${yolo_msgs_LIBRARIES}
    ${visualization_msgs_LIBRARIES}
    ${geometry_msgs_LIBRARIES}
    Python::Python
  )

  target_include_directories(${target} PUBLIC
    ${rclcpp_INCLUDE_DIRS}
    ${std_msgs_INCLUDE_DIRS}
    ${sensor_msgs_INCLUDE_DIRS}
    ${OpenVINO_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
    ${tf2_INCLUDE_DIRS}
    ${tf2_ros_INCLUDE_DIRS}
    ${tf2_msgs_INCLUDE_DIRS}
    ${PYTHON_INCLUDE_DIRS}
    ${yolo_msgs_INCLUDE_DIRS}
    ${geometry_msgs_INCLUDE_DIRS}
    src
  )
endfunction()

configure_target(yolo)
configure_target(benchmarkYolo)

# ---------------------- TESTS ----------------------
enable_testing()
add_executable(tests src/tests.cpp)
configure_target(tests)
target_link_libraries(tests PRIVATE GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(tests)

# ---------------------- INSTALL ----------------------
ament_target_dependencies(yolo)
install(TARGETS yolo DESTINATION lib/${PROJECT_NAME})

ament_package()