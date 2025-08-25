# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
project(wandering_app)

# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  if(NOT FUZZTEST_FUZZING_MODE)
    add_compile_options(-Wall -Wextra -Wpedantic -Werror -fstack-protector-all -Wno-deprecated-declarations)
  endif()
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(nav2_util REQUIRED)
find_package(nav2_costmap_2d REQUIRED)

include_directories(
  include
  include/wandering_app
)

set(dependencies
  rclcpp
  std_msgs
  nav_msgs
  geometry_msgs
  nav2_msgs
  nav2_util
  nav2_costmap_2d
  rclcpp_components
)

add_executable(wandering src/main.cpp src/MapEngine.cpp src/WanderingMapper.cpp src/GoalCatcher.cpp src/utils.cpp)
ament_target_dependencies(wandering ${dependencies})

install(TARGETS
  wandering
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  behavior_trees
  DESTINATION share/${PROJECT_NAME}/
  USE_SOURCE_PERMISSIONS
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(launch_testing_ament_cmake)

  add_launch_test(tests/test_invalid_param.py)

  ament_add_gtest(test_mapengine tests/test_mapengine.cpp src/MapEngine.cpp src/utils.cpp TIMEOUT 10)
  ament_target_dependencies(test_mapengine ${dependencies})

  ament_add_gtest(test_goalcatcher tests/test_goalcatcher.cpp src/GoalCatcher.cpp TIMEOUT 15)
  ament_target_dependencies(test_goalcatcher ${dependencies})

  ament_add_gtest(test_inputs tests/test_inputs.cpp src/WanderingMapper.cpp src/GoalCatcher.cpp src/MapEngine.cpp src/utils.cpp TIMEOUT 20)
  ament_target_dependencies(test_inputs ${dependencies})

  ament_add_gtest_executable(test_mapper
    tests/test_wandering_mapper.cpp src/WanderingMapper.cpp src/GoalCatcher.cpp src/MapEngine.cpp src/utils.cpp)
  ament_target_dependencies(test_mapper ${dependencies})
  ament_add_test(test_mapper
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/tests/launch/test_mapper.launch.py"
    TIMEOUT 420
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    ENV
      TEST_EXECUTABLE=$<TARGET_FILE:test_mapper>
  )

  ament_lint_auto_find_test_dependencies()
endif()

if(FUZZTEST_FUZZING_MODE)
  # Fuzztest requires Clang
  if(NOT CXX MATCHES "clang")
    message(FATAL_ERROR "Please set the CXX option to your Clang installation (e.g. -DCXX=clang++)")
  endif()

  # Use a symlink from the compiled frameworks.industrial.edge-controls.actions.fuzzer version
  add_subdirectory(/fuzztest fuzztest)
  enable_testing()
  include(GoogleTest)

  # Enable fuzzing mode
  fuzztest_setup_fuzzing_flags()

  # Enable coverage: https://clang.llvm.org/docs/SourceBasedCodeCoverage.html
  # Enable sanitizers: https://llvm.org/docs/LibFuzzer.html#fuzzer-usage
  #  - Note: memory and address cannot be used at the same time!
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-instr-generate -fcoverage-mapping -fsanitize=address,signed-integer-overflow -g")

  add_library(wanderingLib src/MapEngine.cpp src/WanderingMapper.cpp src/GoalCatcher.cpp src/utils.cpp)
  ament_target_dependencies(wanderingLib ${dependencies})

  add_executable(
     fuzz_mapengine
     tests/fuzzing/fuzz_mapengine.cpp
  )

  target_link_libraries(
     fuzz_mapengine
     PRIVATE
     wanderingLib
  )
  link_fuzztest(fuzz_mapengine)
endif()

ament_package()
