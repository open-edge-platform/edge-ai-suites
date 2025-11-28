# INTEL CONFIDENTIAL
#
# Copyright (C) 2021-2024 Intel Corporation.
#
# This software and the related documents are Intel copyrighted materials, and your use of
# them is governed by the express license under which they were provided to you (License).
# Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
# disclose or transmit this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties,
# other than those that are expressly stated in the License.

set(LevelZero_INCLUDE_DIRS "/opt/intel/level-zero/include/")
set(LevelZero_LIBRARIES "/opt/intel/level-zero/lib/libze_loader.so")

#-------Generate a testQueryPipeline executable file---------------

add_executable(testQueryPipeline testQueryPipeline.cpp ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                                        ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp)

target_include_directories(testQueryPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testQueryPipeline Threads::Threads dl)

target_include_directories(testQueryPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testQueryPipeline ${Boost_LIBRARIES})

#-------Generate a testStrucPipeline executable file---------------

add_executable(testStrucPipeline testStrucPipeline.cpp)

target_include_directories(testStrucPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testStrucPipeline Threads::Threads dl)

target_include_directories(testStrucPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testStrucPipeline ${Boost_LIBRARIES})


#-------Generate a testLocalPipeline executable file---------------

add_executable(testLocalPipeline testLocalPipeline.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp)

target_include_directories(testLocalPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testLocalPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testLocalPipeline PUBLIC Threads::Threads dl)

target_include_directories(testLocalPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testLocalPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testLocalPipeline PUBLIC hva)

#-------Generate gRPC related test apps---------------
if (USE_GRPC_API)

    find_package(OpenCV REQUIRED)
    message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
    message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

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
    message("PROTO_SRCS: ${PROTO_SRCS}")
    message("GRPC_SRCS: ${GRPC_SRCS}")

    #-------Generate a testGRPCLocalPipeline executable file---------------

    add_executable(testGRPCLocalPipeline testGRPCLocalPipeline.cpp
                                # ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                # ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                # ${PROTO_SRCS} ${GRPC_SRCS})
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                ${PROTO_SRCS} ${GRPC_SRCS})

    target_include_directories(testGRPCLocalPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
    target_include_directories(testGRPCLocalPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

    set(THREADS_PREFER_PTHREAD_FLAG ON)
    find_package(Threads REQUIRED)
    target_link_libraries(testGRPCLocalPipeline PUBLIC Threads::Threads dl)

    target_include_directories(testGRPCLocalPipeline PUBLIC ${Boost_INCLUDE_DIR})
    target_link_libraries(testGRPCLocalPipeline PUBLIC ${Boost_LIBRARIES})

    target_link_libraries(testGRPCLocalPipeline PUBLIC hva)

    target_link_libraries(testGRPCLocalPipeline PUBLIC
        gRPC::grpc++_reflection
        protobuf::libprotobuf
    )
    target_include_directories(testGRPCLocalPipeline PUBLIC "${OpenCV_INCLUDE_DIRS}")
    target_link_libraries(testGRPCLocalPipeline PUBLIC "${OpenCV_LIBRARIES}")
    target_include_directories(testGRPCLocalPipeline PUBLIC "${LevelZero_INCLUDE_DIRS}")
    target_link_libraries(testGRPCLocalPipeline PUBLIC "${LevelZero_LIBRARIES}")


    #-------Generate a testGRPCLocalPipeline_pred executable file---------------
    add_executable(testGRPCLocalPipeline_pred testGRPCLocalPipeline_pred.cpp
                                # ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                # ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                # ${PROTO_SRCS} ${GRPC_SRCS})
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                ${PROTO_SRCS} ${GRPC_SRCS})

    target_include_directories(testGRPCLocalPipeline_pred PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
    target_include_directories(testGRPCLocalPipeline_pred PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

    set(THREADS_PREFER_PTHREAD_FLAG ON)
    find_package(Threads REQUIRED)
    target_link_libraries(testGRPCLocalPipeline_pred PUBLIC Threads::Threads dl)

    target_include_directories(testGRPCLocalPipeline_pred PUBLIC ${Boost_INCLUDE_DIR})
    target_link_libraries(testGRPCLocalPipeline_pred PUBLIC ${Boost_LIBRARIES})

    target_link_libraries(testGRPCLocalPipeline_pred PUBLIC hva)

    target_link_libraries(testGRPCLocalPipeline_pred PUBLIC
        gRPC::grpc++_reflection
        protobuf::libprotobuf
    )
    target_include_directories(testGRPCLocalPipeline_pred PUBLIC "${OpenCV_INCLUDE_DIRS}")
    target_link_libraries(testGRPCLocalPipeline_pred PUBLIC "${OpenCV_LIBRARIES}")
    target_include_directories(testGRPCLocalPipeline_pred PUBLIC "${LevelZero_INCLUDE_DIRS}")
    target_link_libraries(testGRPCLocalPipeline_pred PUBLIC "${LevelZero_LIBRARIES}")

    #-------Generate a CRSensorFusionDisplay executable file---------------
    add_executable(CRSensorFusionDisplay CRSensorFusionDisplay.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                         ${PROTO_SRCS} ${GRPC_SRCS})

    target_include_directories(CRSensorFusionDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
    target_include_directories(CRSensorFusionDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
    set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

    set(THREADS_PREFER_PTHREAD_FLAG ON)
    find_package(Threads REQUIRED)
    target_link_libraries(CRSensorFusionDisplay PUBLIC Threads::Threads dl)

    target_include_directories(CRSensorFusionDisplay PUBLIC ${Boost_INCLUDE_DIR})
    target_link_libraries(CRSensorFusionDisplay PUBLIC ${Boost_LIBRARIES})

    target_link_libraries(CRSensorFusionDisplay PUBLIC hva)

    target_link_libraries(CRSensorFusionDisplay PUBLIC
                          gRPC::grpc++_reflection
                          protobuf::libprotobuf
                          )
    target_include_directories(CRSensorFusionDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
    target_link_libraries(CRSensorFusionDisplay PUBLIC "${OpenCV_LIBRARIES}")

    target_include_directories(CRSensorFusionDisplay PUBLIC "${LevelZero_INCLUDE_DIRS}")
    target_link_libraries(CRSensorFusionDisplay PUBLIC "${LevelZero_LIBRARIES}")


    #-------Generate a CRSensorFusionRadarDisplay executable file---------------

    add_executable(CRSensorFusionRadarDisplay CRSensorFusionRadarDisplay.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                         ${PROTO_SRCS} ${GRPC_SRCS})

    target_include_directories(CRSensorFusionRadarDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
    target_include_directories(CRSensorFusionRadarDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
    set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

    set(THREADS_PREFER_PTHREAD_FLAG ON)
    find_package(Threads REQUIRED)
    target_link_libraries(CRSensorFusionRadarDisplay PUBLIC Threads::Threads dl)

    target_include_directories(CRSensorFusionRadarDisplay PUBLIC ${Boost_INCLUDE_DIR})
    target_link_libraries(CRSensorFusionRadarDisplay PUBLIC ${Boost_LIBRARIES})

    target_link_libraries(CRSensorFusionRadarDisplay PUBLIC hva)

    target_link_libraries(CRSensorFusionRadarDisplay PUBLIC
                          gRPC::grpc++_reflection
                          protobuf::libprotobuf
                          )
    target_include_directories(CRSensorFusionRadarDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
    target_link_libraries(CRSensorFusionRadarDisplay PUBLIC "${OpenCV_LIBRARIES}")

    target_include_directories(CRSensorFusionRadarDisplay PUBLIC "${LevelZero_INCLUDE_DIRS}")
    target_link_libraries(CRSensorFusionRadarDisplay PUBLIC "${LevelZero_LIBRARIES}")

    #-------Generate a MediaDisplay executable file---------------

    add_executable(MediaDisplay MediaDisplay.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                         ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                         ${PROTO_SRCS} ${GRPC_SRCS})

    target_include_directories(MediaDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
    target_include_directories(MediaDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
    set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

    set(THREADS_PREFER_PTHREAD_FLAG ON)
    find_package(Threads REQUIRED)
    target_link_libraries(MediaDisplay PUBLIC Threads::Threads dl)

    target_include_directories(MediaDisplay PUBLIC ${Boost_INCLUDE_DIR})
    target_link_libraries(MediaDisplay PUBLIC ${Boost_LIBRARIES})

    target_link_libraries(MediaDisplay PUBLIC hva)

    target_link_libraries(MediaDisplay PUBLIC
                          gRPC::grpc++_reflection
                          protobuf::libprotobuf
                          )
    target_include_directories(MediaDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
    target_link_libraries(MediaDisplay PUBLIC "${OpenCV_LIBRARIES}")

    target_include_directories(MediaDisplay PUBLIC "${LevelZero_INCLUDE_DIRS}")
    target_link_libraries(MediaDisplay PUBLIC "${LevelZero_LIBRARIES}")

    
endif()

#-------Generate a testMultiStreamAiPipeline executable file---------------

add_executable(testMultiStreamAiPipeline testMultiStreamAiPipeline.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/nodes/base/baseResponseNode.cpp)

target_include_directories(testMultiStreamAiPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testMultiStreamAiPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testMultiStreamAiPipeline PUBLIC Threads::Threads dl)

target_include_directories(testMultiStreamAiPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testMultiStreamAiPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testMultiStreamAiPipeline PUBLIC hva)

#-------Generate a testMultiStreamFusionPipeline executable file---------------

add_executable(testMultiStreamFusionPipeline testMultiStreamFusionPipeline.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/nodes/base/baseResponseNode.cpp)

target_include_directories(testMultiStreamFusionPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testMultiStreamFusionPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testMultiStreamFusionPipeline PUBLIC Threads::Threads dl)

target_include_directories(testMultiStreamFusionPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testMultiStreamFusionPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testMultiStreamFusionPipeline PUBLIC hva)

#-------Generate a gtestPipeline executable file---------------

# unit test environment
# {BUILD_UNIT_TEST} default as OFF
# can be reset through environment-var or cmake-param
set(BUILD_UNIT_TEST OFF)
if(DEFINED ENV{BUILD_UNIT_TEST})
    if($ENV{BUILD_UNIT_TEST} STREQUAL "ON")
        set(BUILD_UNIT_TEST ON)
    endif()
endif()

if(BUILD_UNIT_TEST)
    find_package(OpenCV REQUIRED)
    message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
    message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")
    
    add_executable(gtestPipeline gtestPipeline.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                ${CMAKE_CURRENT_SOURCE_DIR}/../source/nodes/base/baseResponseNode.cpp)

    target_include_directories(gtestPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
    target_include_directories(gtestPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

    target_include_directories(gtestPipeline PUBLIC "${OpenCV_INCLUDE_DIRS}")
    target_link_libraries(gtestPipeline PUBLIC "${OpenCV_LIBRARIES}")

    set(THREADS_PREFER_PTHREAD_FLAG ON)
    find_package(Threads REQUIRED)
    target_link_libraries(gtestPipeline PUBLIC Threads::Threads dl)

    target_include_directories(gtestPipeline PUBLIC ${Boost_INCLUDE_DIR})
    target_link_libraries(gtestPipeline PUBLIC ${Boost_LIBRARIES})

    target_link_libraries(gtestPipeline PUBLIC hva)
    find_package(GTest REQUIRED)
    enable_testing()
    target_include_directories(gtestPipeline PUBLIC ${GTEST_INCLUDE_DIRS})
    target_link_libraries(gtestPipeline PUBLIC ${GTEST_LIBRARIES})
    message("GTEST_INCLUDE_DIRS: ${GTEST_INCLUDE_DIRS}")
    message("GTEST_LIBRARIES: ${GTEST_LIBRARIES}")
endif()

#-------Generate a testAiNode executable file---------------

find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_executable(testAiNode testAiNode.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp)

target_include_directories(testAiNode PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testAiNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_include_directories(testAiNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testAiNode PUBLIC "${OpenCV_LIBRARIES}")

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testAiNode PUBLIC Threads::Threads dl)

target_include_directories(testAiNode PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testAiNode PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testAiNode PUBLIC hva)

#-------Generate a testRadarPerformance executable file---------------
find_package(OpenCV REQUIRED)

message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_executable(testRadarPerformance testRadarPerformance.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/nodes/base/baseResponseNode.cpp)

target_include_directories(testRadarPerformance PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testRadarPerformance PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testRadarPerformance PUBLIC Threads::Threads dl)

target_include_directories(testRadarPerformance PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testRadarPerformance PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testRadarPerformance PUBLIC hva)

# -------Generate a testRadarClusteringTrackingNode executable file---------------
find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")
add_executable(testRadarClusteringTrackingNode testRadarClusteringTrackingNode.cpp 
                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp)

target_include_directories(testRadarClusteringTrackingNode PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testRadarClusteringTrackingNode PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../3rdParty/json)
target_include_directories(testRadarClusteringTrackingNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testRadarClusteringTrackingNode PUBLIC Threads::Threads dl)

target_include_directories(testRadarClusteringTrackingNode PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testRadarClusteringTrackingNode PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testRadarClusteringTrackingNode PUBLIC hva)

#-------Generate a testFusionPipeline executable file---------------
find_package(OpenCV REQUIRED)

message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_executable(testFusionPipeline testFusionPipeline.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp)

target_include_directories(testFusionPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testFusionPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_include_directories(testFusionPipeline PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testFusionPipeline PUBLIC "${OpenCV_LIBRARIES}")
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testFusionPipeline PUBLIC Threads::Threads dl)

target_include_directories(testFusionPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testFusionPipeline PUBLIC ${Boost_LIBRARIES})
target_link_libraries(testFusionPipeline PUBLIC hva)


#-------Generate a testFusionPerformance executable file---------------
find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_executable(testFusionPerformance testFusionPerformance.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                              ${CMAKE_CURRENT_SOURCE_DIR}/../source/nodes/base/baseResponseNode.cpp)

target_include_directories(testFusionPerformance PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testFusionPerformance PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_include_directories(testFusionPerformance PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testFusionPerformance PUBLIC "${OpenCV_LIBRARIES}")
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testFusionPerformance PUBLIC Threads::Threads dl)

target_include_directories(testFusionPerformance PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testFusionPerformance PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testFusionPerformance PUBLIC hva)

#-------Generate a CRSensorFusion4C4RDisplay executable file---------------

add_executable(CRSensorFusion4C4RDisplay CRSensorFusion4C4RDisplay.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(CRSensorFusion4C4RDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(CRSensorFusion4C4RDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(CRSensorFusion4C4RDisplay PUBLIC Threads::Threads dl)

target_include_directories(CRSensorFusion4C4RDisplay PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(CRSensorFusion4C4RDisplay PUBLIC ${Boost_LIBRARIES})

target_link_libraries(CRSensorFusion4C4RDisplay PUBLIC hva)

target_link_libraries(CRSensorFusion4C4RDisplay PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(CRSensorFusion4C4RDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion4C4RDisplay PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(CRSensorFusion4C4RDisplay PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion4C4RDisplay PUBLIC "${LevelZero_LIBRARIES}")

#-------Generate a CRSensorFusion4C4RDisplayCrossStream executable file---------------

add_executable(CRSensorFusion4C4RDisplayCrossStream CRSensorFusion4C4RDisplayCrossStream.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(CRSensorFusion4C4RDisplayCrossStream PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(CRSensorFusion4C4RDisplayCrossStream PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(CRSensorFusion4C4RDisplayCrossStream PUBLIC Threads::Threads dl)

target_include_directories(CRSensorFusion4C4RDisplayCrossStream PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(CRSensorFusion4C4RDisplayCrossStream PUBLIC ${Boost_LIBRARIES})

target_link_libraries(CRSensorFusion4C4RDisplayCrossStream PUBLIC hva)

target_link_libraries(CRSensorFusion4C4RDisplayCrossStream PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(CRSensorFusion4C4RDisplayCrossStream PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion4C4RDisplayCrossStream PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(CRSensorFusion4C4RDisplayCrossStream PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion4C4RDisplayCrossStream PUBLIC "${LevelZero_LIBRARIES}")


#-------Generate a testGRPC4C4RPipeline executable file---------------

add_executable(testGRPC4C4RPipeline testGRPC4C4RPipeline.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(testGRPC4C4RPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testGRPC4C4RPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testGRPC4C4RPipeline PUBLIC Threads::Threads dl)

target_include_directories(testGRPC4C4RPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testGRPC4C4RPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testGRPC4C4RPipeline PUBLIC hva)

target_link_libraries(testGRPC4C4RPipeline PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(testGRPC4C4RPipeline PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testGRPC4C4RPipeline PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(testGRPC4C4RPipeline PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(testGRPC4C4RPipeline PUBLIC "${LevelZero_LIBRARIES}")

#-------Generate a testGRPC4C4RPipelineCrossStream executable file---------------

add_executable(testGRPC4C4RPipelineCrossStream testGRPC4C4RPipelineCrossStream.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(testGRPC4C4RPipelineCrossStream PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testGRPC4C4RPipelineCrossStream PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testGRPC4C4RPipelineCrossStream PUBLIC Threads::Threads dl)

target_include_directories(testGRPC4C4RPipelineCrossStream PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testGRPC4C4RPipelineCrossStream PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testGRPC4C4RPipelineCrossStream PUBLIC hva)

target_link_libraries(testGRPC4C4RPipelineCrossStream PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(testGRPC4C4RPipelineCrossStream PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testGRPC4C4RPipelineCrossStream PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(testGRPC4C4RPipelineCrossStream PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(testGRPC4C4RPipelineCrossStream PUBLIC "${LevelZero_LIBRARIES}")

#-------Generate a testGRPC2C1RPipeline executable file---------------

add_executable(testGRPC2C1RPipeline testGRPC2C1RPipeline.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(testGRPC2C1RPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testGRPC2C1RPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testGRPC2C1RPipeline PUBLIC Threads::Threads dl)

target_include_directories(testGRPC2C1RPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testGRPC2C1RPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testGRPC2C1RPipeline PUBLIC hva)

target_link_libraries(testGRPC2C1RPipeline PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(testGRPC2C1RPipeline PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testGRPC2C1RPipeline PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(testGRPC2C1RPipeline PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(testGRPC2C1RPipeline PUBLIC "${LevelZero_LIBRARIES}")

# -------Generate a CRSensorFusion2C1RDisplay executable file---------------
add_executable(CRSensorFusion2C1RDisplay CRSensorFusion2C1RDisplay.cpp
                                        ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                        ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                        ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                        ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                        ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                        ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                        ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(CRSensorFusion2C1RDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(CRSensorFusion2C1RDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(CRSensorFusion2C1RDisplay PUBLIC Threads::Threads dl)

target_include_directories(CRSensorFusion2C1RDisplay PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(CRSensorFusion2C1RDisplay PUBLIC ${Boost_LIBRARIES})

target_link_libraries(CRSensorFusion2C1RDisplay PUBLIC hva)

target_link_libraries(CRSensorFusion2C1RDisplay PUBLIC
                        gRPC::grpc++_reflection
                        protobuf::libprotobuf
                        )
target_include_directories(CRSensorFusion2C1RDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion2C1RDisplay PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(CRSensorFusion2C1RDisplay PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion2C1RDisplay PUBLIC "${LevelZero_LIBRARIES}")

#-------Generate a testGRPC16C4RPipeline executable file---------------

add_executable(testGRPC16C4RPipeline testGRPC16C4RPipeline.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(testGRPC16C4RPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testGRPC16C4RPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testGRPC16C4RPipeline PUBLIC Threads::Threads dl)

target_include_directories(testGRPC16C4RPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testGRPC16C4RPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testGRPC16C4RPipeline PUBLIC hva)

target_link_libraries(testGRPC16C4RPipeline PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(testGRPC16C4RPipeline PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(testGRPC16C4RPipeline PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(testGRPC16C4RPipeline PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(testGRPC16C4RPipeline PUBLIC "${LevelZero_LIBRARIES}")

#-------Generate a CRSensorFusion16C4RDisplay executable file---------------

add_executable(CRSensorFusion16C4RDisplay CRSensorFusion16C4RDisplay.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gather_gpu_metrics_from_one_api.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                     ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                     ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                     ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(CRSensorFusion16C4RDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(CRSensorFusion16C4RDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(CRSensorFusion16C4RDisplay PUBLIC Threads::Threads dl)

target_include_directories(CRSensorFusion16C4RDisplay PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(CRSensorFusion16C4RDisplay PUBLIC ${Boost_LIBRARIES})

target_link_libraries(CRSensorFusion16C4RDisplay PUBLIC hva)

target_link_libraries(CRSensorFusion16C4RDisplay PUBLIC
                      gRPC::grpc++_reflection
                      protobuf::libprotobuf
                      )
target_include_directories(CRSensorFusion16C4RDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion16C4RDisplay PUBLIC "${OpenCV_LIBRARIES}")

target_include_directories(CRSensorFusion16C4RDisplay PUBLIC "${LevelZero_INCLUDE_DIRS}")
target_link_libraries(CRSensorFusion16C4RDisplay PUBLIC "${LevelZero_LIBRARIES}")


#-------Generate a testGRPCCPlusLPipeline executable file---------------
add_executable(testGRPCCPlusLPipeline testGRPCCPlusLPipeline.cpp
                            ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                            ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                            ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                            ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                            ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                            ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(testGRPCCPlusLPipeline PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(testGRPCCPlusLPipeline PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(testGRPCCPlusLPipeline PUBLIC Threads::Threads dl)

target_include_directories(testGRPCCPlusLPipeline PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(testGRPCCPlusLPipeline PUBLIC ${Boost_LIBRARIES})

target_link_libraries(testGRPCCPlusLPipeline PUBLIC hva)

target_link_libraries(testGRPCCPlusLPipeline PUBLIC
    gRPC::grpc++_reflection
    protobuf::libprotobuf
)

#-------Generate a CLSensorFusionDisplay executable file---------------
add_executable(CLSensorFusionDisplay CLSensorFusionDisplay.cpp
                                    ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/base64.cpp
                                    ${CMAKE_CURRENT_SOURCE_DIR}/../source/common/common.cpp
                                    ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/cpu-top.c
                                    ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gmg_common_util.c
                                    ${CMAKE_CURRENT_SOURCE_DIR}/utils/sys_metrics/gpu_monitor.cpp
                                    ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/FusionDisplay.cpp
                                    ${CMAKE_CURRENT_SOURCE_DIR}/../source/modules/visualization/Plot.cpp
                                    ${PROTO_SRCS} ${GRPC_SRCS})

target_include_directories(CLSensorFusionDisplay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../include)
target_include_directories(CLSensorFusionDisplay PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
set(CMAKE_THREAD_PREFER_PTHREAD TRUE)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(CLSensorFusionDisplay PUBLIC Threads::Threads dl)

target_include_directories(CLSensorFusionDisplay PUBLIC ${Boost_INCLUDE_DIR})
target_link_libraries(CLSensorFusionDisplay PUBLIC ${Boost_LIBRARIES})

target_link_libraries(CLSensorFusionDisplay PUBLIC hva)

target_link_libraries(CLSensorFusionDisplay PUBLIC
                        gRPC::grpc++_reflection
                        protobuf::libprotobuf
                        )
target_include_directories(CLSensorFusionDisplay PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(CLSensorFusionDisplay PUBLIC "${OpenCV_LIBRARIES}")
