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

find_package(uv)

# file(GLOB_RECURSE AI_INF_LL_SERVER_SRC ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp )
set(AI_INF_LL_SERVER_COMMON_SRC ${CMAKE_CURRENT_SOURCE_DIR}/../common/common.cpp ${CMAKE_CURRENT_SOURCE_DIR}/../common/logger.cpp)

set(AI_INF_LL_SERVER_INC_DIR ${PROJECT_SOURCE_DIR}/ai_inference/include)

if (USE_GRPC_API)

    # Generated sources
    add_custom_command(
      OUTPUT "${PROTO_SRCS}" "${PROTO_HDRS}" "${GRPC_SRCS}" "${GRPC_HDRS}"
      COMMAND "${_PROTOBUF_PROTOC}"
      ARGS --grpc_out "${PROTO_SRC_DIR}"
        --cpp_out "${PROTO_SRC_DIR}"
        -I "${ai_inf_proto_path}"
        --plugin=protoc-gen-grpc="${_GRPC_CPP_PLUGIN_EXECUTABLE}"
        --experimental_allow_proto3_optional
        "${ai_inf_proto}"
      DEPENDS "${ai_inf_proto}")

    # Include generated *.pb.h files
    include_directories("${PROTO_SRC_DIR}")

    set(AI_INF_LL_SERVER_SRC ${PROTO_SRCS} ${GRPC_SRCS}
                             ${CMAKE_CURRENT_SOURCE_DIR}/grpc_server/grpcPipelineManager.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/grpc_server/grpcServer.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/pipelineManager.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/http_server/httpPipelineManager.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/http_server/lowLatencyServer.cpp)

    add_executable(HceAILLInfServer ${AI_INF_LL_SERVER_SRC} ${AI_INF_LL_SERVER_COMMON_SRC}
                                    ${PROJECT_SOURCE_DIR}/ai_inference/source/nodes/base/baseResponseNode.cpp)

    target_link_libraries(HceAILLInfServer
        gRPC::grpc++_reflection
        protobuf::libprotobuf
    )
else()
    set(AI_INF_LL_SERVER_SRC ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/pipelineManager.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/http_server/httpPipelineManager.cpp
                             ${CMAKE_CURRENT_SOURCE_DIR}/http_server/lowLatencyServer.cpp)

    add_executable(HceAILLInfServer ${AI_INF_LL_SERVER_SRC} ${AI_INF_LL_SERVER_COMMON_SRC}
                                    ${PROJECT_SOURCE_DIR}/ai_inference/source/nodes/base/baseResponseNode.cpp)
endif()

target_include_directories(HceAILLInfServer PUBLIC "$<BUILD_INTERFACE:${AI_INF_LL_SERVER_INC_DIR}>")
target_include_directories(HceAILLInfServer PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(HceAILLInfServer ${Boost_LIBRARIES})
target_include_directories(HceAILLInfServer PUBLIC ${Boost_INCLUDE_DIRS})

target_link_libraries(HceAILLInfServer ${UV_LDFLAGS})

target_link_libraries(HceAILLInfServer Threads::Threads dl)

target_link_libraries(HceAILLInfServer hva)

