# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# Add sources
target_sources(${PROJECT_NAME}
                PRIVATE
                ${CMAKE_CURRENT_SOURCE_DIR}/relocalizer.h
                ${CMAKE_CURRENT_SOURCE_DIR}/loop_detector.h
                ${CMAKE_CURRENT_SOURCE_DIR}/loop_bundle_adjuster.h
                ${CMAKE_CURRENT_SOURCE_DIR}/relocalizer.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/loop_detector.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/loop_bundle_adjuster.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/initializer.h
                ${CMAKE_CURRENT_SOURCE_DIR}/frame_tracker.h
                ${CMAKE_CURRENT_SOURCE_DIR}/keyframe_inserter.h
                ${CMAKE_CURRENT_SOURCE_DIR}/two_view_triangulator.h
                ${CMAKE_CURRENT_SOURCE_DIR}/local_map_cleaner.h
                ${CMAKE_CURRENT_SOURCE_DIR}/initializer.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/frame_tracker.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/keyframe_inserter.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/two_view_triangulator.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/local_map_cleaner.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/tracker/tracker_loop_detector.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/tracker/tracker_loop_bundle_adjuster.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/server/server_loop_detector.cc
                ${CMAKE_CURRENT_SOURCE_DIR}/server/server_loop_bundle_adjuster.cc)
# Install headers
file(GLOB HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/*.h")
install(FILES ${HEADERS}
        DESTINATION ${OPENVSLAM_INCLUDE_INSTALL_DIR}/module)
