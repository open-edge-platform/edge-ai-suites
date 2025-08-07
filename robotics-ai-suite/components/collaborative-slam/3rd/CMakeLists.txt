# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(univloc_dependencies LANGUAGES CXX)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE
      "Release"
      CACHE STRING "" FORCE)
endif()

add_library(${PROJECT_NAME} INTERFACE)

if("$ENV{ROS_VERSION}" EQUAL "1")
  find_package(catkin REQUIRED)
  set(COMMON_DESTINATION ${CATKIN_DEVEL_PREFIX})
  catkin_package()
elseif("$ENV{ROS_VERSION}" EQUAL "2")
  find_package(ament_cmake REQUIRED)
  set(COMMON_DESTINATION ${CMAKE_INSTALL_PREFIX})
endif()

install(
  TARGETS ${PROJECT_NAME}
  EXPORT ${PROJECT_NAME}
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION bin
  INCLUDES
  DESTINATION include)

include(ExternalProject)

set(DISABLE_WARNING_FLAGS
    "-Wno-uninitialized -Wno-unused-parameter -Wno-unused-but-set-variable -Wno-aggressive-loop-optimizations"
)
# g2o

if(NOT DEFINED BUILD_NATIVE)
  set(BUILD_NATIVE ON)
endif()

if(NOT DEFINED BUILD_TREMONT)
  set(BUILD_TREMONT OFF)
endif()

if(${BUILD_TREMONT})
  set(BUILD_NATIVE OFF)
endif()

if(${BUILD_NATIVE})
  set(OPTIMIZED_BUILD ON)
  message(STATUS "Native ON!")
else()
  set(OPTIMIZED_BUILD OFF)
  message(STATUS "Native OFF!")
endif()

ExternalProject_Add(
  g2o
  SOURCE_DIR ${PROJECT_SOURCE_DIR}/g2o
  CMAKE_ARGS -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
             -DCMAKE_INSTALL_PREFIX=${COMMON_DESTINATION}
             -DG2O_BUILD_EXAMPLES=OFF
             -DG2O_BUILD_APPS=OFF
             -DG2O_USE_CHOLMOD=OFF
             -DG2O_USE_CSPARSE=ON
             -DBUILD_LGPL_SHARED_LIBS=ON
             -DG2O_USE_OPENGL=OFF
             -DG2O_USE_OPENMP=OFF
             -DOpenGL_GL_PREFERENCE=LEGACY
             -DBUILD_WITH_MARCH_NATIVE=${OPTIMIZED_BUILD}
             -DCMAKE_C_FLAGS=${DISABLE_WARNING_FLAGS}
             -DCMAKE_CXX_FLAGS=${DISABLE_WARNING_FLAGS})
add_dependencies(${PROJECT_NAME} g2o)
# G2O_USE_VENDORED_CERES needs to be exposed, since slam will include header
# files of g2o that contain this definition, which will be undefined to cause
# compile error i.e., "base_unary_edge.h" (included by slam) includes
# "base_fixed_sized_edge.h"
target_compile_definitions(${PROJECT_NAME} INTERFACE G2O_USE_VENDORED_CERES)
target_compile_definitions(${PROJECT_NAME} INTERFACE G2O_LGPL_SHARED_LIBS)
target_compile_definitions(${PROJECT_NAME} INTERFACE G2O_SHARED_LIBS)
target_include_directories(
  ${PROJECT_NAME} INTERFACE $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/g2o>
                            $<INSTALL_INTERFACE:include>)
target_link_libraries(
  ${PROJECT_NAME}
  INTERFACE optimized
            ${COMMON_DESTINATION}/lib/libg2o_core.so
            optimized
            ${COMMON_DESTINATION}/lib/libg2o_stuff.so
            optimized
            ${COMMON_DESTINATION}/lib/libg2o_types_sba.so
            optimized
            ${COMMON_DESTINATION}/lib/libg2o_solver_csparse.so
            optimized
            ${COMMON_DESTINATION}/lib/libg2o_types_slam3d.so
            optimized
            ${COMMON_DESTINATION}/lib/libg2o_csparse_extension.so
            debug
            ${COMMON_DESTINATION}/lib/libg2o_core_d.so
            debug
            ${COMMON_DESTINATION}/lib/libg2o_stuff_d.so
            debug
            ${COMMON_DESTINATION}/lib/libg2o_types_sba_d.so
            debug
            ${COMMON_DESTINATION}/lib/libg2o_solver_csparse_d.so
            debug
            ${COMMON_DESTINATION}/lib/libg2o_types_slam3d_d.so
            debug
            ${COMMON_DESTINATION}/lib/libg2o_csparse_extension_d.so)

# spdlog
if("$ENV{ROS_VERSION}" EQUAL "1")
  ExternalProject_Add(
    spdlog
    SOURCE_DIR ${PROJECT_SOURCE_DIR}/spdlog
    CMAKE_ARGS -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
               -DCMAKE_INSTALL_PREFIX=${COMMON_DESTINATION}
               -DSPDLOG_BUILD_EXAMPLE=OFF -DSPDLOG_BUILD_SHARED=ON)
  add_dependencies(${PROJECT_NAME} spdlog)
  target_compile_definitions(${PROJECT_NAME} INTERFACE SPDLOG_COMPILED_LIB)
  target_include_directories(
    ${PROJECT_NAME}
    INTERFACE $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/spdlog/include>
              $<INSTALL_INTERFACE:include>)
  target_link_libraries(
    ${PROJECT_NAME} INTERFACE optimized ${COMMON_DESTINATION}/lib/libspdlog.so
                              debug ${COMMON_DESTINATION}/lib/libspdlogd.so)
elseif("$ENV{ROS_VERSION}" EQUAL "2")
  find_package(spdlog REQUIRED)
  target_link_libraries(${PROJECT_NAME} INTERFACE spdlog::spdlog)
endif()

# DBoW2
ExternalProject_Add(
  DBoW2
  SOURCE_DIR ${PROJECT_SOURCE_DIR}/DBoW2
  CMAKE_ARGS -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
             -DCMAKE_INSTALL_PREFIX=${COMMON_DESTINATION})
add_dependencies(${PROJECT_NAME} DBoW2)
target_compile_definitions(${PROJECT_NAME} INTERFACE USE_DBOW2)
target_include_directories(
  ${PROJECT_NAME}
  INTERFACE $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/DBoW2/include>
            $<INSTALL_INTERFACE:include>)
target_link_libraries(${PROJECT_NAME}
                      INTERFACE ${COMMON_DESTINATION}/lib/libdbow2.so)

# json
target_include_directories(
  ${PROJECT_NAME}
  INTERFACE $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/json/include>
            $<INSTALL_INTERFACE:include>)
file(COPY ${PROJECT_SOURCE_DIR}/json/include/
     DESTINATION ${COMMON_DESTINATION}/include)

if("$ENV{ROS_VERSION}" EQUAL "2")
  ament_export_targets(${PROJECT_NAME} HAS_LIBRARY_TARGET)
  ament_package()
endif()

# C for Metal based Orb Extractor gpu
option(USE_GPU_CM "Use C-for-Metal GPU acceleration" OFF)
if(USE_GPU_CM)
  if(NOT CM_GPU_INSTALL_DIR)
    message(
      FATAL_ERROR
        "C for Metal Orb Extactor installation dir (CM_GPU_INSTALL_DIR) must be specified if USE_GPU_CM enabled"
    )
  endif()

  target_include_directories(
    ${PROJECT_NAME} INTERFACE $<BUILD_INTERFACE:${CM_GPU_INSTALL_DIR}/include>
                              $<INSTALL_INTERFACE:include>)

  target_compile_definitions(
    ${PROJECT_NAME} INTERFACE GPU_KERNEL_PATH="${CM_GPU_INSTALL_DIR}/lib/")
  target_link_libraries(${PROJECT_NAME}
                        INTERFACE ${CM_GPU_INSTALL_DIR}/lib/libgpu_orb.so)
endif()
