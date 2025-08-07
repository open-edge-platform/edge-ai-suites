# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(
  univloc_server
  LANGUAGES CXX
  VERSION ${UNIVLOC_VERSION_STRING})

include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/univloc_setup.cmake)

# ----- Set compiler options -----
set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} -ffast-math")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -ffast-math")

# ----- Build the ROS application -----

find_package(ament_cmake REQUIRED)
find_package(ament_lint_auto REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(tf2 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(tf2_eigen REQUIRED)
find_package(message_filters REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(univloc_msgs REQUIRED)
ament_export_dependencies(rosidl_default_runtime)
ament_export_dependencies(univloc_msgs)
ament_export_dependencies(univloc_slam)
if(NOT USE_PREBUILT_DEPS)
  ament_export_dependencies(univloc_dependencies)
endif()

add_definitions(-DCONFIG_PATH="${PROJECT_SOURCE_DIR}/config/")
add_executable(
  ${PROJECT_NAME}
  src/ros_node.cpp
  src/server/client_handler.cc
  src/server/server.cc
  src/ServerSystem.cc
  src/server/camera_fusion_module.cc
  src/server/univloc_graph_optimizer.cc
  src/server/window_graph_optimizer.cc
  src/server/univloc_global_optimization_module.cc
  ${PROJECT_SOURCE_DIR}/../slam/fast_mapping/fast_mapping_helper.cpp)

# ----- Append subdirectory -----
set(OPENVSLAM_INCLUDE_INSTALL_DIR include) # CMakeLists in subdirectories
                                           # require this variable

target_include_directories(
  ${PROJECT_NAME}
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include
         ${CMAKE_CURRENT_SOURCE_DIR}/../slam/openvslam
         ${CMAKE_CURRENT_SOURCE_DIR}/../slam/fast_mapping src)
if(NOT USE_PREBUILT_DEPS)

  set(dependencies
      rclcpp
      sensor_msgs
      message_filters
      cv_bridge
      tf2
      tf2_ros
      tf2_geometry_msgs
      tf2_eigen
      nav_msgs
      visualization_msgs
      std_msgs
      univloc_msgs
      univloc_dependencies)

  target_link_libraries(${PROJECT_NAME}
                        univloc_dependencies::univloc_dependencies)

else()

  target_compile_definitions(${PROJECT_NAME} PUBLIC USE_DBOW2)
  # double confirm G2O_USE_VENDORED_CERES is defined to avoid compile error
  target_compile_definitions(${PROJECT_NAME} PUBLIC G2O_USE_VENDORED_CERES)

  set(dependencies
      rclcpp
      sensor_msgs
      message_filters
      cv_bridge
      tf2
      tf2_ros
      tf2_geometry_msgs
      tf2_eigen
      nav_msgs
      visualization_msgs
      std_msgs
      univloc_msgs
      DBoW2)

  target_link_libraries(${PROJECT_NAME} spdlog::spdlog g2o-intel::core
                        g2o-intel::types_slam3d g2o-intel::solver_csparse)

endif()

if("$ENV{ROS_DISTRO}" STRLESS "humble")
  target_compile_definitions(${PROJECT_NAME} PUBLIC PRE_ROS_HUMBLE)
endif()

ament_target_dependencies(${PROJECT_NAME} ${dependencies})

target_link_libraries(${PROJECT_NAME} ${OpenCV_LIBRARIES} ${LIBVA} ${LIBVA_DRM})

if(NOT USE_SLAM_SHAREDLIBS_PATH)
  find_package(univloc_slam REQUIRED)
  ament_target_dependencies(${PROJECT_NAME} univloc_slam)
else()
  find_library(USER_SLAM_LIBRARY univloc_slam PATHS ${USE_SLAM_SHAREDLIBS_PATH})
  message(STATUS "User linked against with :" ${USER_SLAM_LIBRARY})
  if(NOT USE_GPU_CM)
    if(USE_SSE_ORB)
      target_compile_definitions(${PROJECT_NAME} PRIVATE USE_SSE_ORB)
    endif()
  else()
    find_package(orblze REQUIRED)
    if(NOT orblze_LIBS)
      message(WARNING "GPU Level-Zero ORB library is not found.")
    endif()
    message(STATUS "GPU Level-Zero ORB library:" ${orblze_LIBS})
  endif()
  target_link_libraries(${PROJECT_NAME} ${USER_SLAM_LIBRARY} Threads::Threads
                        yaml-cpp ${orblze_LIBS})
  target_include_directories(${PROJECT_NAME}
                             PUBLIC "${CMAKE_INSTALL_PREFIX}/include/openvslam")
endif()

install(
  TARGETS ${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME}/)
install(DIRECTORY config DESTINATION share/${PROJECT_NAME}/)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest_executable(test_map_merge_exe tests/test_map_merge.cpp)
  ament_target_dependencies(test_map_merge_exe ${dependencies})

  ament_add_test(
    test_map_merge
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_map_merge.launch.py"
    TIMEOUT 150
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
  ament_lint_auto_find_test_dependencies()

  ament_add_gtest_executable(
    test_remapping_exe tests/test_remapping.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../slam/fast_mapping/fast_mapping_helper.cpp)
  # only adding -lfmt to LDFLAGS in the server rules file will still encounter build failure
  # for test_remapping_exe during link stage, so manually find and link fmt package here
  find_package(fmt)
  target_link_libraries(test_remapping_exe fmt::fmt)
  target_include_directories(
    test_remapping_exe
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../slam/fast_mapping
           ${CMAKE_CURRENT_SOURCE_DIR}/../include
           ${CMAKE_CURRENT_SOURCE_DIR}/../tracker/tests)
  ament_target_dependencies(test_remapping_exe ${dependencies})
  ament_add_test(
    test_remapping
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_remapping.launch.py" -p 800 -k 40 -o 2000 -r "[-1.0, -0.5, -1.0, 0.5, 5.0, 0.5, 5.0, -0.5]"
    TIMEOUT 300
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")

endif()
ament_package()
