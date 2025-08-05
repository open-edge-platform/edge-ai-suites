# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(trac_ik_kinematics_plugin)

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
  message("${PROJECT_NAME}: You did not request a specific build type: Choosing 'Release' for maximum performance")
  set(CMAKE_BUILD_TYPE Release)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(PkgConfig REQUIRED)
pkg_check_modules(pkg_nlopt REQUIRED nlopt)


set(THIS_PACKAGE_INCLUDE_DEPENDS
    ament_cmake
    ament_cmake_ros
    moveit_core
    pluginlib
    rclcpp
    tf2_eigen
    tf2_ros
    tf2_kdl
    tf2_geometry_msgs
    trac_ik_lib
    visualization_msgs
)

foreach(Dependency IN ITEMS ${THIS_PACKAGE_INCLUDE_DEPENDS})
  find_package(${Dependency} REQUIRED)
endforeach()


add_compile_options($<$<CONFIG:Release>:-O3>)
add_compile_options($<$<CONFIG:Release>:-ftree-vectorize>)
add_compile_options($<$<CONFIG:Release>:-ffast-math>)
include_directories(
  include
)

set(TRAC_IK_LIBRARY_NAME trac_ik_kinematics_plugin)

add_library(${TRAC_IK_LIBRARY_NAME} SHARED src/trac_ik_kinematics_plugin.cpp)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(${PROJECT_NAME}
  PUBLIC
    ${THIS_PACKAGE_INCLUDE_DEPENDS}
)

target_link_libraries(
  ${TRAC_IK_LIBRARY_NAME} 
  PRIVATE
   ${pkg_nlopt_LIBRARIES}
)

target_compile_features(${PROJECT_NAME} PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17

install(
  DIRECTORY include/
  DESTINATION include
)
install(
  TARGETS ${TRAC_IK_LIBRARY_NAME}
  EXPORT export_${PROJECT_NAME}
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION bin
  INCLUDES DESTINATION include
)


pluginlib_export_plugin_description_file(
  moveit_core
  trac_ik_kinematics_description.xml
)

install(FILES trac_ik_kinematics_description.xml
  DESTINATION share/${PROJECT_NAME}
)


#add_executable(testExe  src/trac_ik_kinematics_plugin.cpp)
#ament_target_dependencies(testExe ${THIS_PACKAGE_INCLUDE_DEPENDS})

ament_export_include_directories(
  include
)
ament_export_libraries(
  ${PROJECT_NAME}
)
ament_export_targets(
  export_${PROJECT_NAME}
)

ament_export_dependencies(${THIS_PACKAGE_INCLUDE_DEPENDS})

ament_package()
