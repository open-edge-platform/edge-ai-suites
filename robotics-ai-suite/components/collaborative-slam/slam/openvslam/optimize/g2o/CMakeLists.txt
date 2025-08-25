# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# Add sources
target_sources(${PROJECT_NAME}
               PRIVATE
               ${CMAKE_CURRENT_SOURCE_DIR}/landmark_vertex.h
               ${CMAKE_CURRENT_SOURCE_DIR}/landmark_vertex_container.h
               ${CMAKE_CURRENT_SOURCE_DIR}/landmark_vertex.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/landmark_vertex_container.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/vec3_vertex.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/so3_vertex.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/vec3_vertex_container.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/scale_vertex.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/imubias_vertex.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/imubias_vertex_container.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/camera_pose_vertex_container.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/camera_pose_vertex.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/perspective_reproj_edge2.cc
               )

# Install headers
file(GLOB HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/*.h")
install(FILES ${HEADERS}
        DESTINATION ${OPENVSLAM_INCLUDE_INSTALL_DIR}/optimize/g2o)

# Append subdirectory
add_subdirectory(se3)
add_subdirectory(sim3)
