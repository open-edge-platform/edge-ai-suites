# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(yolo)

set(yolo_MAJOR_VERSION 1)
set(yolo_MINOR_VERSION 0)
set(yolo_PATCH_VERSION 0)
set(yolo_VERSION
  ${yolo_MAJOR_VERSION}.${yolo_MINOR_VERSION}.${yolo_PATCH_VERSION})

# if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
#   add_compile_options(-Wall -Wextra -Wpedantic)
# endif()


set( CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE ON )

set( CMAKE_EXPORT_COMPILE_COMMANDS ON )

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/03597a01ee50ed33e9dfd640b249b4be3799d395.zip
)
# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# -Wall -Wno-sign-compare
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}  -fPIC  -O1 -mavx -mavx2 -pthread -g  ")

option(USE_PLOT "Draw plots using MATPLOT++" OFF)


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

set(OpenCV_INCLUDE_DIRS
  /usr/local/include
  /usr/local/include/opencv2
)

set(OpenCV_LIB_DIR
  /usr/local/lib
)

add_executable(yolo src/YoloMain.cpp)
add_executable(benchmarkYolo src/YoloBenchmark.cpp)

if(USE_PLOT)
  add_subdirectory(matplotplusplus)
  target_link_libraries(yolo PRIVATE matplot)
  target_link_libraries(benchmarkYolo PRIVATE matplot)
  target_compile_definitions(
    benchmarkYolo PRIVATE PLOT)
  target_compile_definitions(
    yolo PRIVATE PLOT)
endif()



target_link_libraries( yolo
    PRIVATE
        ${std_msgs_LIBRARIES}
        ${sensor_msgs_LIBRARIES}
        ${rclcpp_LIBRARIES}
        ${tf2_LIBRARIES}
        ${tf2_ros_LIBRARIES}
        ${tf2_msgs_LIBRARIES}
        openvino::runtime
        ${OpenCV_LIBS}
        ${OpenVINO_LIBRARIES}
        ${yolo_msgs_LIBRARIES}
        ${visualization_msgs_LIBRARIES}
        ${geometry_msgs_LIBRARIES}        
        Python::Python
)

target_include_directories(yolo
                            PUBLIC 
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
                            src)



target_link_libraries( benchmarkYolo
    PRIVATE
    ${std_msgs_LIBRARIES}
    ${sensor_msgs_LIBRARIES}
    ${rclcpp_LIBRARIES}
    ${tf2_LIBRARIES}
    ${tf2_ros_LIBRARIES}
    ${tf2_msgs_LIBRARIES}
    openvino::runtime
    ${OpenCV_LIBS}
    ${OpenVINO_LIBRARIES}
    ${yolo_msgs_LIBRARIES}
    ${visualization_msgs_LIBRARIES}
    ${geometry_msgs_LIBRARIES}
    Python::Python
)


target_include_directories(benchmarkYolo
                            PUBLIC 
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
                            src)





enable_testing()

add_executable(
  tests
  src/tests.cpp
)

target_link_libraries(
  tests
  PRIVATE
  GTest::gtest_main
  ${std_msgs_LIBRARIES}
  ${sensor_msgs_LIBRARIES}
  ${rclcpp_LIBRARIES}
  ${tf2_LIBRARIES}
  ${tf2_ros_LIBRARIES}
  ${tf2_msgs_LIBRARIES}
  openvino::runtime
  ${OpenCV_LIBS}
  ${OpenVINO_LIBRARIES}
  ${yolo_msgs_LIBRARIES}
  ${visualization_msgs_LIBRARIES}
  ${geometry_msgs_LIBRARIES}
  Python::Python
)
target_include_directories(tests PUBLIC
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

include(GoogleTest)
gtest_discover_tests(tests)

ament_target_dependencies(yolo)
install(
  TARGETS yolo
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()