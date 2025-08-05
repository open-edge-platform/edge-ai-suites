# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# Add sources
if (USE_GPU_CM)
    target_sources(${PROJECT_NAME}
               PRIVATE
               ${CMAKE_CURRENT_SOURCE_DIR}/orb_params.cc)
else()
    target_sources(${PROJECT_NAME}
               PRIVATE
               ${CMAKE_CURRENT_SOURCE_DIR}/orb_params.h
               ${CMAKE_CURRENT_SOURCE_DIR}/default/orb_extractor.h
               ${CMAKE_CURRENT_SOURCE_DIR}/default/orb_extractor_node.h
               ${CMAKE_CURRENT_SOURCE_DIR}/orb_params.cc
               ${CMAKE_CURRENT_SOURCE_DIR}/default/orb_extractor.cc)
    # Install headers
    file(GLOB HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/default/*.h")
    install(FILES ${HEADERS}
        DESTINATION ${OPENVSLAM_INCLUDE_INSTALL_DIR}/feature)
endif()
