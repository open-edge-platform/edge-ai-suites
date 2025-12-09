# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.8)
project(
  univloc_tracker
  LANGUAGES CXX
  VERSION ${UNIVLOC_VERSION_STRING})

include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/univloc_setup.cmake)

# ----- Detect ROS distribution -----
if(NOT DEFINED ENV{ROS_DISTRO})
  # Try to detect from CMAKE_PREFIX_PATH or other means
  if(EXISTS "/opt/ros/jazzy")
    set(ROS_DISTRO "jazzy")
  elseif(EXISTS "/opt/ros/humble")
    set(ROS_DISTRO "humble")
  else()
    message(FATAL_ERROR "Could not detect ROS distribution. Please set ROS_DISTRO environment variable.")
  endif()
else()
  set(ROS_DISTRO "$ENV{ROS_DISTRO}")
endif()

message(STATUS "Building for ROS ${ROS_DISTRO}")

# Validate supported ROS distributions
if(NOT ROS_DISTRO STREQUAL "humble" AND NOT ROS_DISTRO STREQUAL "jazzy")
  message(WARNING "Unsupported ROS distribution: ${ROS_DISTRO}. Supported: humble, jazzy")
endif()

# Semantic SLAM using OpenVINO semantic segmentation
set(ENABLE_OPENVINO_SEGMENTATION OFF)
if(ENABLE_OPENVINO_SEGMENTATION)
  if(IE_NOT_FOUND_MESSAGE)
    find_package(InferenceEngine 2.0 QUIET)
    if(NOT (InferenceEngine_FOUND))
      message(FATAL_ERROR ${IE_NOT_FOUND_MESSAGE})
    endif()
  else()
    find_package(InferenceEngine 2.0 REQUIRED)
  endif()
  message(STATUS "Use InferenceEngine ${InferenceEngine_VERSION}")

  # Download model files for semantic slam
  set(MODEL_BIN_URL
      "https://download.01.org/opencv/2021/openvinotoolkit/2021.1/open_model_zoo/models_bin/2/semantic-segmentation-adas-0001/FP16/semantic-segmentation-adas-0001.bin"
  )
  set(MODEL_XML_URL
      "https://download.01.org/opencv/2021/openvinotoolkit/2021.1/open_model_zoo/models_bin/2/semantic-segmentation-adas-0001/FP16/semantic-segmentation-adas-0001.xml"
  )
  set(MODEL_BIN_PATH "../../src/univloc_tracker/inference_model/model.bin")
  set(MODEL_XML_PATH "../../src/univloc_tracker/inference_model/model.xml")

  function(download_file url filename)
    if(NOT EXISTS ${filename})
      file(DOWNLOAD ${url} ${filename} TIMEOUT 60) # seconds
    endif()
  endfunction(download_file)

  download_file(${MODEL_BIN_URL} ${MODEL_BIN_PATH})
  download_file(${MODEL_XML_URL} ${MODEL_XML_PATH})
endif()

# Use ros image-transport package and its plugin as optional
set(image_transport_pkgs image_transport compressed_image_transport
                         compressed_depth_image_transport)

foreach(pkg ${image_transport_pkgs})
  find_package(${pkg} QUIET)
endforeach()

set(avail_image_transport_pkgs "")
foreach(pkg ${image_transport_pkgs})
  set(pkg_found "${pkg}_FOUND")
  if(${pkg_found})
    list(APPEND avail_image_transport_pkgs "${pkg}")
  endif()
endforeach()

message(
  STATUS "available image-transport package: ${avail_image_transport_pkgs}")

find_package(ament_cmake REQUIRED)
find_package(ament_lint_auto REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(tf2 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(message_filters REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(image_transport REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(univloc_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

# ROS Jazzy specific packages
if(ROS_DISTRO STREQUAL "jazzy")
  find_package(ament_index_cpp REQUIRED)
endif()

ament_export_dependencies(rosidl_default_runtime)
if(NOT USE_PREBUILT_DEPS)
  ament_export_dependencies(univloc_dependencies)
endif()
ament_export_dependencies(univloc_msgs)
ament_export_dependencies(univloc_slam)

# ----- Build the library -----

add_library(${PROJECT_NAME})

target_compile_definitions(${PROJECT_NAME} PRIVATE)

add_definitions(-DCONFIG_PATH="${PROJECT_SOURCE_DIR}/config/")
if(ENABLE_OPENVINO_SEGMENTATION)
  add_compile_definitions(ENABLE_SEMANTIC_SLAM)
  add_compile_definitions(DISPLAY_SEGMENTATION)
endif()

target_include_directories(
  ${PROJECT_NAME}
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../slam/fast_mapping include
         ${EIGEN3_INCLUDE_DIR}
  PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} src)

# GPU CM handling with ROS distribution specific ORB libraries
if(USE_GPU_CM)
  message(STATUS "USE_GPU_CM enabled")
  if(USE_PREBUILT_DEPS)
    # Initialize ORB library variable
    set(ORB_LIBRARIES "")
    
    find_package(orblze REQUIRED)
    set(ORB_LIBRARIES ${orblze_LIBS})
    
    # Only define GPU_KERNEL_PATH  (orblze)
    if(NOT CM_GPU_INSTALL_DIR)
      message(STATUS "Level Zero ORB extractor library found at ${ORBLZE_KERNEL_DIR}")
      target_compile_definitions(${PROJECT_NAME} PRIVATE GPU_KERNEL_PATH="${ORBLZE_KERNEL_DIR}/")
    else()
      message(STATUS "Level Zero ORB extractor library found at ${CM_GPU_INSTALL_DIR}")
      target_compile_definitions(${PROJECT_NAME} PRIVATE GPU_KERNEL_PATH="${CM_GPU_INSTALL_DIR}/")
    endif()

    target_link_libraries(
      ${PROJECT_NAME}
      ${OpenCV_LIBRARIES}
      Threads::Threads
      ${ORB_LIBRARIES}
      ${LAPACK_LIBRARIES}
      ${LIBVA}
      ${LIBVA_DRM}
      spdlog::spdlog)
  else()
    # Non-prebuilt deps path
    target_include_directories(${PROJECT_NAME}
                               PRIVATE ${CM_GPU_INSTALL_DIR}/include)
    target_link_libraries(
      ${PROJECT_NAME}
      ${OpenCV_LIBRARIES}
      Threads::Threads
      ${LAPACK_LIBRARIES}
      ${LIBVA}
      ${LIBVA_DRM}
      ${CM_LIBRARIES}
      spdlog::spdlog)
  endif()
else()
  # Non-GPU CM path
  target_link_libraries(
    ${PROJECT_NAME}
    ${OpenCV_LIBRARIES}
    Threads::Threads
    ${LAPACK_LIBRARIES}
    ${LIBVA}
    ${LIBVA_DRM}
    spdlog::spdlog)
endif()

if(NOT USE_PREBUILT_DEPS)
  # Set dependencies based on ROS distribution
  if(ROS_DISTRO STREQUAL "jazzy")
    set(dependencies
        rclcpp
        sensor_msgs
        cv_bridge
        message_filters
        tf2
        tf2_ros
        tf2_geometry_msgs
        geometry_msgs
        visualization_msgs
        nav_msgs
        std_msgs
        univloc_msgs
        ament_index_cpp
        univloc_dependencies
        ${avail_image_transport_pkgs})
  else()
    # ROS Humble
    set(dependencies
        rclcpp
        sensor_msgs
        cv_bridge
        message_filters
        tf2
        tf2_ros
        tf2_geometry_msgs
        geometry_msgs
        visualization_msgs
        nav_msgs
        std_msgs
        univloc_msgs
        univloc_dependencies
        ${avail_image_transport_pkgs})
  endif()
else()
  target_compile_definitions(${PROJECT_NAME} PUBLIC USE_DBOW2)
  target_compile_definitions(${PROJECT_NAME} PUBLIC G2O_USE_VENDORED_CERES)

  # Set dependencies based on ROS distribution
  if(ROS_DISTRO STREQUAL "jazzy")
    set(dependencies
        rclcpp
        sensor_msgs
        cv_bridge
        message_filters
        tf2
        tf2_ros
        tf2_geometry_msgs
        geometry_msgs
        visualization_msgs
        nav_msgs
        std_msgs
        univloc_msgs
        ament_index_cpp
        ${avail_image_transport_pkgs}
        DBoW2)
    # Use standard g2o for Jazzy
    find_package(g2o REQUIRED)
    target_link_libraries(${PROJECT_NAME} 
                          g2o::core
                          g2o::types_slam3d 
                          g2o::solver_csparse)
  else()
    # ROS Humble
    set(dependencies
        rclcpp
        sensor_msgs
        cv_bridge
        message_filters
        tf2
        tf2_ros
        tf2_geometry_msgs
        geometry_msgs
        visualization_msgs
        nav_msgs
        std_msgs
        univloc_msgs
        ${avail_image_transport_pkgs}
        DBoW2)
    # Use g2o-intel for Humble
    target_link_libraries(${PROJECT_NAME} 
                          g2o-intel::core
                          g2o-intel::types_slam3d 
                          g2o-intel::solver_csparse)
  endif()
endif()

if(ROS_DISTRO STREQUAL "humble")
  target_compile_definitions(${PROJECT_NAME} PUBLIC PRE_ROS_HUMBLE)
endif()

ament_target_dependencies(${PROJECT_NAME} ${dependencies})

if(ENABLE_OPENVINO_SEGMENTATION)
  target_link_libraries(${PROJECT_NAME} PUBLIC ${InferenceEngine_LIBRARIES})
endif()

# ----- Append subdirectory -----
set(OPENVSLAM_INCLUDE_INSTALL_DIR include) # CMakeLists in subdirectories
                                           # require this variable
add_subdirectory(src/tracker)

# ----- Build the ROS application -----

add_executable(
  ${PROJECT_NAME}_ros
  ${PROJECT_SOURCE_DIR}/../slam/fast_mapping/fast_mapping_helper.cpp
  ${PROJECT_SOURCE_DIR}/ros/TrackerNode.cpp ${PROJECT_SOURCE_DIR}/ros/main.cpp)
add_dependencies(${PROJECT_NAME}_ros ${PROJECT_NAME})

target_include_directories(
  ${PROJECT_NAME} PUBLIC include ${CMAKE_CURRENT_SOURCE_DIR}/../include
                         ${CMAKE_CURRENT_SOURCE_DIR}/../slam/openvslam)
target_include_directories(
  ${PROJECT_NAME}_ros
  PUBLIC include ${CMAKE_CURRENT_SOURCE_DIR}/../slam/fast_mapping
         ${CMAKE_CURRENT_SOURCE_DIR}/../include)

# Set default value to OFF since in most cases the image imputs are not
# compressed
option(ENABLE_IMAGE_TRANSPORT "Enable image transport option" ON)
if((NOT "${avail_image_transport_pkgs}" EQUAL "") AND (ENABLE_IMAGE_TRANSPORT))
  message(STATUS "Enable image-transport feature")
  set_target_properties(${PROJECT_NAME}_ros PROPERTIES COMPILE_FLAGS
                                                       -DUSE_IMAGE_TRANSPORT)
endif()

ament_target_dependencies(${PROJECT_NAME}_ros ${dependencies})

# Define flags for ROS application target
if(ROS_DISTRO STREQUAL "humble")
  target_compile_definitions(${PROJECT_NAME}_ros PUBLIC PRE_ROS_HUMBLE)
endif()
target_compile_definitions(${PROJECT_NAME}_ros PRIVATE)

target_link_libraries(${PROJECT_NAME}_ros ${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)

# gpu
if(NOT USE_GPU_CM)
  target_include_directories(
    ${PROJECT_NAME}
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../slam/openvslam/feature/default)
else()
  if(NOT USE_PREBUILT_DEPS)
    target_include_directories(${PROJECT_NAME}
                               PRIVATE ${CM_GPU_INSTALL_DIR}/include)
  endif()
endif()

if(NOT USE_SLAM_SHAREDLIBS_PATH)
  find_package(univloc_slam REQUIRED)
  ament_target_dependencies(${PROJECT_NAME} univloc_slam)
else()
  find_library(USER_SLAM_LIBRARY univloc_slam PATHS ${USE_SLAM_SHAREDLIBS_PATH})
  message(STATUS "User linked against with :" ${USER_SLAM_LIBRARY})
  if(DEFINED orblze_LIBS)
    target_link_libraries(${PROJECT_NAME} ${USER_SLAM_LIBRARY} Threads::Threads
                          yaml-cpp ${orblze_LIBS})
  else()
    target_link_libraries(${PROJECT_NAME} ${USER_SLAM_LIBRARY} Threads::Threads
                          yaml-cpp)
  endif()

  target_include_directories(${PROJECT_NAME}
                             PUBLIC "${CMAKE_INSTALL_PREFIX}/include/openvslam")
endif()

install(
  TARGETS ${PROJECT_NAME} ${PROJECT_NAME}_ros
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME}/)
install(DIRECTORY config DESTINATION share/${PROJECT_NAME}/)

ament_python_install_package(python_utils)

if(BUILD_TESTING)
  # Build gtest for tracker input check
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest)
  ament_add_gtest(test_tracker_input tests/test_tracker_inputs.cpp
                  ${PROJECT_SOURCE_DIR}/ros/TrackerNode.cpp TIMEOUT 60)
  ament_target_dependencies(test_tracker_input ${dependencies})
  target_include_directories(test_tracker_input
                             PUBLIC ros ${CMAKE_CURRENT_SOURCE_DIR}/../include)
  target_link_libraries(test_tracker_input ${PROJECT_NAME})
  
  # Define flags for test targets
  if(ROS_DISTRO STREQUAL "humble")
    target_compile_definitions(test_tracker_input PUBLIC PRE_ROS_HUMBLE)
  endif()
  
  ament_lint_auto_find_test_dependencies()

  # Build ctest for tracker image-transport feature
  if((NOT "${avail_image_transport_pkgs}" EQUAL "") AND (ENABLE_IMAGE_TRANSPORT
                                                        ))
    add_executable(test_image_transport tests/test_image_transport.cpp)
    ament_target_dependencies(test_image_transport ${dependencies})
    ament_add_test(
      test_image_transport
      GENERATE_RESULT_FOR_RETURN_CODE_ZERO
      COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_image_transport.py -r false -t 550
      TIMEOUT 300
      WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
  endif()

  # Build ctest to test functionality of IMU system
  ament_add_gtest_executable(test_imu_system tests/test_imu_system.cpp)
  ament_target_dependencies(test_imu_system ${dependencies})
  ament_add_test(
    test_imu_system
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_imu_system.py -t 10
    TIMEOUT 600
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})

  # Build ctest for lidar support
  ament_add_gtest_executable(test_lidar_system tests/test_lidar_system.cpp)
  ament_target_dependencies(test_lidar_system ${dependencies})
  ament_add_test(
    test_lidar_system
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_lidar_system.py -tp 15 -tf 150
    TIMEOUT 600
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})

endif()
ament_package()
