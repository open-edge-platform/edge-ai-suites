# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

set(EXEC_NAME pointcloud-groundfloor-segmentation-tests)

IF(BUILD_COVERAGE AND CMAKE_COMPILER_IS_GNUCXX)
  set(CMAKE_BUILD_TYPE "Debug")
  include(${CMAKE_SOURCE_DIR}/cmake/CodeCoverage.cmake)
  append_coverage_compiler_flags()
  setup_target_for_coverage_lcov(NAME coverage EXECUTABLE pointcloud-groundfloor-segmentation-tests EXCLUDE test/*)
endif()

set(CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)

if(FUZZTEST_FUZZING_MODE)
  set(TEST_SOURCES
    FuzzTest.cpp
  )
else()
  set(TEST_SOURCES
    main.cpp
    HeightConfidenceTest.cpp
    MonitorTest.cpp
  )
endif()

set(SOURCES
  ../src/Monitor.cpp
)

configure_file(data/depth_matrix.txt data/depth_matrix.txt COPYONLY)
configure_file(data/height_matrix.txt data/height_matrix.txt COPYONLY)
configure_file(data/index_matrix.txt data/index_matrix.txt COPYONLY)
configure_file(data/point_cloud.txt data/point_cloud.txt COPYONLY)
configure_file(data/height_image.yml data/height_image.yml COPYONLY)
configure_file(data/depth_image.yml data/depth_image.yml COPYONLY)
configure_file(data/rosbag.tar.gz data/rosbag.tar.gz COPYONLY)
configure_file(data/rosbag_lidar.tar.gz data/rosbag_lidar.tar.gz COPYONLY)
configure_file(test_realsense.sh test_realsense.sh COPYONLY)
configure_file(test_lidar.sh test_lidar.sh COPYONLY)

set(INSTALL_DATA_PATH ${CMAKE_CURRENT_BINARY_DIR}/../data)

execute_process(COMMAND cmake -E create_symlink
  ${CMAKE_CURRENT_BINARY_DIR}/data
  ${INSTALL_DATA_PATH}
)

find_package(OpenCV REQUIRED)

enable_testing()

include(GoogleTest)

add_executable(${EXEC_NAME} ${SOURCES} ${TEST_SOURCES})

if(FUZZTEST_FUZZING_MODE)
  # Fuzztest requires Clang
  if(NOT CXX MATCHES "clang")
    message(FATAL_ERROR "Please set the CXX option to your Clang installation (e.g. -DCXX=clang++)")
  endif()

  # Use a symlink from the compiled frameworks.industrial.edge-controls.actions.fuzzer version
  if(FUZZTEST_LOCAL)
    add_subdirectory(${CMAKE_SOURCE_DIR}/../fuzztest ${CMAKE_CURRENT_BINARY_DIR}/fuzztest)
  else()
    add_subdirectory(/fuzztest fuzztest)
  endif()

  link_fuzztest(${EXEC_NAME})
  gtest_discover_tests(${EXEC_NAME})

  fuzztest_setup_fuzzing_flags()

  # Enable coverage: https://clang.llvm.org/docs/SourceBasedCodeCoverage.html
  # Enable sanitizers: https://llvm.org/docs/LibFuzzer.html#fuzzer-usage
  #  - Note: memory and address cannot be used at the same time!
  # NOTE: fuzztest_setup_fuzzing_flags() already adds -fsanitize=address, so we only add the extra flags
  # For jazzy fuzzing, we need to remove -fsanitize=address to avoid conflicts with TBB
  if(FUZZTEST_FUZZING_MODE AND DEFINED ENV{ROS_DISTRO} AND "$ENV{ROS_DISTRO}" STREQUAL "jazzy")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-instr-generate -fcoverage-mapping -fsanitize=signed-integer-overflow -g")
  else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-instr-generate -fcoverage-mapping -fsanitize=address,signed-integer-overflow -g")
  endif()
endif()

target_compile_options(${EXEC_NAME} PRIVATE -fno-access-control)

target_include_directories(${EXEC_NAME}
  PRIVATE
  ${CMAKE_SOURCE_DIR}/include
  ${CMAKE_SOURCE_DIR}/../include
  ${OpenCV_INCLUDE_DIR}
)

target_link_libraries(${EXEC_NAME}
  PRIVATE
  ${OpenCV_LIBS}
  GTest::gtest_main
)

add_test(NAME ${EXEC_NAME} COMMAND ${EXEC_NAME})