# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(oriented_grasp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  if(NOT FUZZTEST_FUZZING_MODE)
    add_compile_options(-Wall -Wextra -Wpedantic -Wunused-parameter)
  endif()
endif()


set(THIS_PACKAGE_INCLUDE_DEPENDS
  rvc_grasp_interface
  ament_cmake
  ament_cmake_gtest
  pluginlib
  rclcpp
  rvc_messages
  std_msgs
  tf2_ros
  tf2_geometry_msgs
  tf2_eigen
  tf2
  visualization_msgs
)


# find dependencies
foreach(Dependency IN ITEMS ${THIS_PACKAGE_INCLUDE_DEPENDS})
  find_package(${Dependency} REQUIRED)
endforeach()

add_library(${PROJECT_NAME} SHARED src/oriented_grasp.cpp)

ament_target_dependencies( ${PROJECT_NAME}
    ${THIS_PACKAGE_INCLUDE_DEPENDS}
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(${PROJECT_NAME} PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17

# Causes the visibility macros to use dllexport rather than dllimport,
# which is appropriate when building the dll but not consuming it.
target_compile_definitions(${PROJECT_NAME} PRIVATE "GRASP_PLUGINS_BUILDING_LIBRARY")

# prevent pluginlib from using boost
target_compile_definitions(${PROJECT_NAME} PUBLIC "PLUGINLIB__DISABLE_BOOST_FUNCTIONS")
pluginlib_export_plugin_description_file(rvc_grasp_interface oriented_grasp_plugin.xml)


install(
  TARGETS ${PROJECT_NAME}
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(FILES oriented_grasp_plugin.xml
  DESTINATION share/${PROJECT_NAME}
)



if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  # Unit Tests
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(oriented_grasp_test tests/test_rotatedPose.cpp)
  target_link_libraries(oriented_grasp_test ${PROJECT_NAME})

  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
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

  # Enable sanitizers and coverage
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-instr-generate -fcoverage-mapping -fsanitize=address,signed-integer-overflow -g")

  include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)
  add_library(orientedgraspLib src/oriented_grasp.cpp )
  ament_target_dependencies(orientedgraspLib ${THIS_PACKAGE_INCLUDE_DEPENDS})

  get_target_property(MY_INCLUDES orientedgraspLib INCLUDE_DIRECTORIES)

  add_executable(
     fuzz_orientedgrasp
     tests/fuzzing/fuzz_orientedgrasp.cpp
  )

  target_link_libraries(
     fuzz_orientedgrasp
     PRIVATE
     orientedgraspLib
  )
  link_fuzztest(fuzz_orientedgrasp)
endif()

ament_package()
