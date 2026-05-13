# INTEL CONFIDENTIAL
#
# Copyright (C) 2021-2023 Intel Corporation.
#
# This software and the related documents are Intel copyrighted materials, and your use of
# them is governed by the express license under which they were provided to you (License).
# Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
# disclose or transmit this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties,
# other than those that are expressly stated in the License.

find_package(Boost REQUIRED COMPONENTS filesystem program_options)

add_library(hva SHARED IMPORTED)
set_target_properties(hva PROPERTIES
    IMPORTED_LOCATION "${CMAKE_CURRENT_SOURCE_DIR}/3rdParty/hva/lib/libhva.so"
)
set(HVA_INC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/3rdParty/hva)
set(JSON_INC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/3rdParty/json)
# set(LIBRADAR_INC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/libradar/src)
# set(DLSTREAMER_INC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/3rdParty/dlstreamer)

find_package(OpenVINO REQUIRED COMPONENTS Runtime)
set(OpenVINO_DIR "/opt/intel/openvino_2025")
message("OpenVINO_INCLUDE_DIRS: ${OpenVINO_INCLUDE_DIRS}")
include_directories(${OpenVINO_INCLUDE_DIRS})
set(INFERENCE_BACKEND_INC_DIR ${PROJECT_SOURCE_DIR}/ai_inference/inference_backend/include)
set(AI_INF_SERVER_NODES_INC_DIR ${PROJECT_SOURCE_DIR}/ai_inference/include)

find_package(Eigen3 REQUIRED)
include_directories(${EIGEN3_INCLUDE_DIR})

# Helper macros and functions

function (set_compile_flags TARGET)
    target_compile_options(${TARGET} PRIVATE $<$<COMPILE_LANGUAGE:C>:${C_FLAGS}> $<$<COMPILE_LANGUAGE:CXX>:${CXX_FLAGS}>)
    if (CMAKE_CXX_COMPILER STREQUAL "icpx")
        target_compile_options(${TARGET} PRIVATE -Wno-tautological-constant-compare)

        if (CMAKE_BUILD_TYPE STREQUAL "Debug")
            target_compile_options(${TARGET} PRIVATE -Wno-debug-disables-optimization -Rno-debug-disables-optimization -Wno-unknown-warning-option)
        endif()

        string(REPLACE "-fno-strict-overflow" "" CXX_TMP_FLAGS "${CMAKE_CXX_FLAGS}")
        set(CMAKE_CXX_FLAGS ${CXX_TMP_FLAGS} PARENT_SCOPE)
    endif()
endfunction(set_compile_flags)

if (USE_GRPC_API)
    add_compile_definitions(USE_GRPC_API)

    # GRPC and Protocol Buffers libraries location
    list(APPEND CMAKE_PREFIX_PATH "/opt/grpc")

    set(protobuf_MODULE_COMPATIBLE TRUE)
    find_package(Protobuf CONFIG REQUIRED)
    message(STATUS "Using protobuf ${Protobuf_VERSION}")

    set(_PROTOBUF_LIBPROTOBUF protobuf::libprotobuf)
    set(_REFLECTION gRPC::grpc++_reflection)
    if(CMAKE_CROSSCOMPILING)
        find_program(_PROTOBUF_PROTOC protoc)
    else()
        set(_PROTOBUF_PROTOC $<TARGET_FILE:protobuf::protoc>)
    endif()

    # Find gRPC installation
    # Looks for gRPCConfig.cmake file installed by gRPC's cmake installation.
    find_package(gRPC CONFIG REQUIRED)
    message(STATUS "Using gRPC ${gRPC_VERSION}")

    set(_GRPC_GRPCPP gRPC::grpc++)
    if(CMAKE_CROSSCOMPILING)
        find_program(_GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin)
    else()
        set(_GRPC_CPP_PLUGIN_EXECUTABLE $<TARGET_FILE:gRPC::grpc_cpp_plugin>)
    endif()

    # Proto file
    get_filename_component(ai_inf_proto "${CMAKE_CURRENT_SOURCE_DIR}/source/low_latency_server/grpc_server/proto/ai_v1.proto" ABSOLUTE)
    get_filename_component(ai_inf_proto_path "${ai_inf_proto}" PATH)

    set(PROTO_SRC_DIR ${CMAKE_BINARY_DIR}/proto-src)
    file(MAKE_DIRECTORY ${PROTO_SRC_DIR})

    # Set path for generated sources
    set(PROTO_SRCS "${PROTO_SRC_DIR}/ai_v1.pb.cc")
    set(PROTO_HDRS "${PROTO_SRC_DIR}/ai_v1.pb.h")
    set(GRPC_SRCS "${PROTO_SRC_DIR}/ai_v1.grpc.pb.cc")
    set(GRPC_HDRS "${PROTO_SRC_DIR}/ai_v1.grpc.pb.h")

endif()

if(ENABLE_VAAPI)
    add_compile_definitions(ENABLE_VAAPI)
endif(ENABLE_VAAPI)

add_subdirectory(utils)
add_subdirectory(inference_backend)
add_subdirectory(source/low_latency_server)
add_subdirectory(test)
add_subdirectory(source/nodes)
add_subdirectory(source/inference_nodes)
