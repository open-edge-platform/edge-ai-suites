# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# Add sources
target_sources(${PROJECT_NAME}
               PRIVATE
               ${CMAKE_CURRENT_SOURCE_DIR}/../../../slam/fast_mapping/fast_mapping_helper.cpp
               ${CMAKE_CURRENT_SOURCE_DIR}/../../../slam/openvslam/tracking_module.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/../../../slam/openvslam/mapping_module.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/Client.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/TrackerImpl.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/Tracker.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/fast_mapping_module.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/feature_extraction_module.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/univloc_mapping_module.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/univloc_tracking_module.cc
)

# Install headers
file(GLOB HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/*.h")
install(FILES ${HEADERS}
        DESTINATION ${OPENVSLAM_INCLUDE_INSTALL_DIR}/tracker)
