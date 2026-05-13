# INTEL CONFIDENTIAL
#
# Copyright (C) 2021-2022 Intel Corporation.
#
# This software and the related documents are Intel copyrighted materials, and your use of
# them is governed by the express license under which they were provided to you (License).
# Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
# disclose or transmit this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties,
# other than those that are expressly stated in the License.

function(get_linux_lsb_release_information)
    find_program(LSB_RELEASE_EXEC lsb_release)
    if(NOT LSB_RELEASE_EXEC)
        message(FATAL_ERROR "Could not detect lsb_release executable, can not gather required information")
    endif()

    execute_process(COMMAND "${LSB_RELEASE_EXEC}" --short --id OUTPUT_VARIABLE LSB_RELEASE_ID_SHORT OUTPUT_STRIP_TRAILING_WHITESPACE)
    execute_process(COMMAND "${LSB_RELEASE_EXEC}" --short --release OUTPUT_VARIABLE LSB_RELEASE_VERSION_SHORT OUTPUT_STRIP_TRAILING_WHITESPACE)
    execute_process(COMMAND "${LSB_RELEASE_EXEC}" --short --codename OUTPUT_VARIABLE LSB_RELEASE_CODENAME_SHORT OUTPUT_STRIP_TRAILING_WHITESPACE)

    set(LSB_RELEASE_ID_SHORT "${LSB_RELEASE_ID_SHORT}" PARENT_SCOPE)
    set(LSB_RELEASE_VERSION_SHORT "${LSB_RELEASE_VERSION_SHORT}" PARENT_SCOPE)
    set(LSB_RELEASE_CODENAME_SHORT "${LSB_RELEASE_CODENAME_SHORT}" PARENT_SCOPE)
endfunction()

if(CMAKE_SYSTEM_NAME MATCHES "Linux")
    get_linux_lsb_release_information()
    message(STATUS "Linux ${LSB_RELEASE_ID_SHORT} ${LSB_RELEASE_VERSION_SHORT} ${LSB_RELEASE_CODENAME_SHORT}")
endif()

#----------------Generate VPLDecoderNode.so file---------------------#
find_package(VPL REQUIRED)
message("VPL_DIR: ${VPL_DIR}")

add_library(VPLDecoderNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/VPLDecoderNode.cpp
                                       ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(VPLDecoderNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(VPLDecoderNode hva)
target_include_directories(VPLDecoderNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(VPLDecoderNode PUBLIC "$<BUILD_INTERFACE:${INFERENCE_BACKEND_INC_DIR}>")
target_include_directories(VPLDecoderNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(VPLDecoderNode ${Boost_LIBRARIES})
target_include_directories(VPLDecoderNode PUBLIC ${Boost_INCLUDE_DIRS})

target_include_directories(VPLDecoderNode PUBLIC "${GLIB_INCLUDE_DIRS}" "${BOOST_INC_DIR}")

target_link_libraries(VPLDecoderNode vpl va_api_wrapper logger)

if(${LSB_RELEASE_ID_SHORT} MATCHES "CentOS")
    message(SEND_ERROR "VPLDecoderNode is not supported on CentOS")
elseif((${LSB_RELEASE_ID_SHORT} MATCHES "Debian") OR (${LSB_RELEASE_ID_SHORT} MATCHES "Ubuntu"))
    message(STATUS "${LSB_RELEASE_ID_SHORT}: VPLDecoderNode include and link libav.")

    find_package(PkgConfig REQUIRED)
    # note: pkg-config version for libva is *API* version
    pkg_check_modules(PKG_LIBVA libva>=1.2 IMPORTED_TARGET GLOBAL)
    pkg_check_modules(PKG_LIBVA_DRM libva-drm>=1.2 IMPORTED_TARGET GLOBAL)
    # Set defaults for ENABLE_VA
    if(PKG_LIBVA_FOUND AND PKG_LIBVA_DRM_FOUND)
      set(VA_DEFAULT ON)
    else()
      set(VA_DEFAULT OFF)
    endif()

    set(ENABLE_VA
        ${VA_DEFAULT}
        CACHE BOOL "Enable VA support in tools.")

    if(NOT ENABLE_VA)
        message(STATUS "Building VPLDecoderNode without VA support")

    else()
        if(PKG_LIBVA_FOUND)
            target_compile_definitions(VPLDecoderNode PUBLIC -DENABLE_VAAPI)
            set(CMAKE_THREAD_PREFER_PTHREAD TRUE)
            set(THREADS_PREFER_PTHREAD_FLAG TRUE)
            find_package(Threads REQUIRED)
            target_link_libraries(VPLDecoderNode PkgConfig::PKG_LIBVA
                                    PkgConfig::PKG_LIBVA_DRM Threads::Threads)
            target_include_directories(VPLDecoderNode PUBLIC ${PKG_LIBVA_INCLUDE_DIRS})
        else()
            message(
                SEND_ERROR
                "libva not found: set ENABLE_VA=OFF to build tools with VA disabled")
        endif()
    endif()
endif()


#----------------Generate LidarSignalProcessingNode.so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")
find_package(MKL CONFIG REQUIRED)
# include_directories(${PROJECT_SOURCE_DIR/ai_nference/libradar/src})
add_library(LidarSignalProcessingNode SHARED LidarSignalProcessingNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/radar_config_parser.cpp)
target_compile_definitions(LidarSignalProcessingNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
link_directories(${PROJECT_SOURCE_DIR}/build/lib)
target_link_libraries(LidarSignalProcessingNode hva)
target_include_directories(LidarSignalProcessingNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>" )
target_include_directories(LidarSignalProcessingNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
target_include_directories(LidarSignalProcessingNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarSignalProcessingNode PUBLIC  $<TARGET_PROPERTY:MKL::MKL,INTERFACE_INCLUDE_DIRECTORIES>)
target_include_directories(LidarSignalProcessingNode PUBLIC ${JSON_INC_DIR})
include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarSignalProcessingNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarSignalProcessingNode ${Boost_LIBRARIES})
target_include_directories(LidarSignalProcessingNode PUBLIC ${Boost_INCLUDE_DIRS})
target_compile_options(LidarSignalProcessingNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_COMPILE_OPTIONS>)
# target_link_libraries(RadarPreProcessingNode media_storage utility)
target_link_libraries(LidarSignalProcessingNode $<LINK_ONLY:MKL::MKL>)
target_link_libraries(LidarSignalProcessingNode Threads::Threads dl ${PROJECT_SOURCE_DIR}/build/lib/liblidar.so)