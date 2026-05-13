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

find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
# message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

# find_package(InferenceEngine REQUIRED)
find_package(OpenVINO REQUIRED COMPONENTS Runtime)
find_package(fmt REQUIRED)
set(OpenVINO_DIR "/opt/intel/openvino_2025")
message("InferenceEngine_INCLUDE_DIRS: ${InferenceEngine_INCLUDE_DIRS}")
message("InferenceEngine_LIBRARIES: ${InferenceEngine_LIBRARIES}")

message("OpenVINO_INCLUDE_DIRS: ${OpenVINO_INCLUDE_DIRS}")
include_directories(${OpenVINO_INCLUDE_DIRS})

message("JSON_INC_DIR: ${JSON_INC_DIR}")

file(GLOB MODEL_PROC_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/model_proc/*.cpp")
message("MODEL_PROC_SRCS: ${MODEL_PROC_SRCS}")

file(GLOB PRE_PROC_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/pre_processor/*.cpp")
message("PRE_PROC_SRCS: ${PRE_PROC_SRCS}")

file(GLOB BASE_INFERENCE_NODE_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/inference_nodes/base/*.cpp")
message("BASE_INFERENCE_NODE_SRCS: ${BASE_INFERENCE_NODE_SRCS}")


#----------------Generate ClassificationNode .so file---------------------#

add_library(ClassificationNode SHARED ClassificationNode.cpp 
                                      ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
                                      ${BASE_INFERENCE_NODE_SRCS} ${MODEL_PROC_SRCS} ${PRE_PROC_SRCS} ${INFERENCE_BACKEND_SRCS})
target_compile_definitions(ClassificationNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(ClassificationNode hva)
target_link_libraries(ClassificationNode inference_backend image_inference image_inference_openvino pre_proc logger)
target_include_directories(ClassificationNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(ClassificationNode PUBLIC "$<BUILD_INTERFACE:${INFERENCE_BACKEND_INC_DIR}>")
target_include_directories(ClassificationNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
# target_include_directories(ClassificationNode PUBLIC "$<BUILD_INTERFACE:${DLSTREAMER_INC_DIR}>")
target_include_directories(ClassificationNode PUBLIC ${JSON_INC_DIR})


target_include_directories(ClassificationNode PUBLIC ${Boost_INCLUDE_DIRS})
target_link_libraries(ClassificationNode ${Boost_LIBRARIES})

# target_include_directories(ClassificationNode PUBLIC "${InferenceEngine_INCLUDE_DIRS}")
# target_link_libraries(ClassificationNode "${InferenceEngine_LIBRARIES}")
target_include_directories(ClassificationNode PUBLIC /opt/intel/openvino_2025/runtime/include)
target_include_directories(ClassificationNode PUBLIC "${OpenVINO_INCLUDE_DIRS}")
target_link_libraries(ClassificationNode openvino::runtime)

target_include_directories(ClassificationNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(ClassificationNode "${OpenCV_LIBRARIES}")

target_link_libraries(ClassificationNode Threads::Threads dl fmt::fmt)

if(ENABLE_VAAPI)
    target_link_libraries(ClassificationNode image_inference_async)
endif(ENABLE_VAAPI)

#----------------Generate DetectionNode .so file---------------------#
file(GLOB DET_MODEL_PROC_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/detection/*.cpp")
message("DET_MODEL_PROC_SRCS: ${DET_MODEL_PROC_SRCS}")

add_library(DetectionNode SHARED DetectionNode.cpp 
            ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
            ${BASE_INFERENCE_NODE_SRCS} ${MODEL_PROC_SRCS} ${DET_MODEL_PROC_SRCS}
            ${PRE_PROC_SRCS} ${INFERENCE_BACKEND_SRCS})
target_compile_definitions(DetectionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(DetectionNode hva)
target_link_libraries(DetectionNode inference_backend image_inference image_inference_openvino pre_proc logger)
target_include_directories(DetectionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(DetectionNode PUBLIC "$<BUILD_INTERFACE:${INFERENCE_BACKEND_INC_DIR}>")
target_include_directories(DetectionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
# target_include_directories(DetectionNode PUBLIC "$<BUILD_INTERFACE:${DLSTREAMER_INC_DIR}>")
target_include_directories(DetectionNode PUBLIC ${JSON_INC_DIR})


target_include_directories(DetectionNode PUBLIC ${Boost_INCLUDE_DIRS})
target_link_libraries(DetectionNode ${Boost_LIBRARIES})

# target_include_directories(DetectionNode PUBLIC "${InferenceEngine_INCLUDE_DIRS}")
# target_link_libraries(DetectionNode "${InferenceEngine_LIBRARIES}")
target_include_directories(DetectionNode PUBLIC /opt/intel/openvino_2025/runtime/include)
target_include_directories(DetectionNode PUBLIC "${OpenVINO_INCLUDE_DIRS}")
target_link_libraries(DetectionNode openvino::runtime)

target_include_directories(DetectionNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(DetectionNode "${OpenCV_LIBRARIES}")

target_link_libraries(DetectionNode Threads::Threads dl fmt::fmt)

if(ENABLE_VAAPI)
    target_link_libraries(DetectionNode image_inference_async)
endif(ENABLE_VAAPI)


#----------------Generate FeatureExtractionNode .so file---------------------#

# feature quantization using intel mkl lib
# find_package(MKL REQUIRED)
# message(STATUS "${MKL_IMPORTED_TARGETS}")

add_library(FeatureExtractionNode SHARED FeatureExtractionNode.cpp
            ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
            ${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
            ${BASE_INFERENCE_NODE_SRCS} ${MODEL_PROC_SRCS} ${PRE_PROC_SRCS} ${INFERENCE_BACKEND_SRCS})
target_compile_definitions(FeatureExtractionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(FeatureExtractionNode hva)
target_link_libraries(FeatureExtractionNode inference_backend image_inference image_inference_openvino pre_proc logger)
target_include_directories(FeatureExtractionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(FeatureExtractionNode PUBLIC "$<BUILD_INTERFACE:${INFERENCE_BACKEND_INC_DIR}>")
target_include_directories(FeatureExtractionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
# target_include_directories(FeatureExtractionNode PUBLIC "$<BUILD_INTERFACE:${DLSTREAMER_INC_DIR}>")
target_include_directories(FeatureExtractionNode PUBLIC ${JSON_INC_DIR})


target_include_directories(FeatureExtractionNode PUBLIC ${Boost_INCLUDE_DIRS})
target_link_libraries(FeatureExtractionNode ${Boost_LIBRARIES})

# target_include_directories(FeatureExtractionNode PUBLIC "${InferenceEngine_INCLUDE_DIRS}")
# target_link_libraries(FeatureExtractionNode "${InferenceEngine_LIBRARIES}")
target_include_directories(FeatureExtractionNode PUBLIC /opt/intel/openvino_2025/runtime/include)
target_include_directories(FeatureExtractionNode PUBLIC "${OpenVINO_INCLUDE_DIRS}")
target_link_libraries(FeatureExtractionNode openvino::runtime)

target_include_directories(FeatureExtractionNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(FeatureExtractionNode "${OpenCV_LIBRARIES}")

target_compile_options(FeatureExtractionNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_COMPILE_OPTIONS>)
target_include_directories(FeatureExtractionNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_INCLUDE_DIRECTORIES>)
target_link_libraries(FeatureExtractionNode $<LINK_ONLY:MKL::MKL>)

target_link_libraries(FeatureExtractionNode Threads::Threads dl fmt::fmt)

if(ENABLE_VAAPI)
    target_link_libraries(FeatureExtractionNode image_inference_async)
endif(ENABLE_VAAPI)


#----------------Generate ObjectQualityNode.so file---------------------#
add_library(ObjectQualityNode SHARED ObjectQualityNode.cpp 
            ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
            ${PROJECT_SOURCE_DIR}/ai_inference/source/modules/quality.cpp
            ${BASE_INFERENCE_NODE_SRCS} ${MODEL_PROC_SRCS} ${PRE_PROC_SRCS} ${INFERENCE_BACKEND_SRCS})
target_compile_definitions(ObjectQualityNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(ObjectQualityNode hva)
target_link_libraries(ObjectQualityNode inference_backend image_inference image_inference_openvino pre_proc logger)
target_include_directories(ObjectQualityNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(ObjectQualityNode PUBLIC "$<BUILD_INTERFACE:${INFERENCE_BACKEND_INC_DIR}>")
target_include_directories(ObjectQualityNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
# target_include_directories(ObjectQualityNode PUBLIC "$<BUILD_INTERFACE:${DLSTREAMER_INC_DIR}>")
target_include_directories(ObjectQualityNode PUBLIC ${JSON_INC_DIR})


target_link_libraries(ObjectQualityNode ${Boost_LIBRARIES})
target_include_directories(ObjectQualityNode PUBLIC ${Boost_INCLUDE_DIRS})

# target_include_directories(ObjectQualityNode PUBLIC "${InferenceEngine_INCLUDE_DIRS}")
# target_link_libraries(ObjectQualityNode "${InferenceEngine_LIBRARIES}")

# target_include_directories(ObjectQualityNode PUBLIC /opt/intel/openvino_2025/runtime/include)
target_include_directories(ObjectQualityNode PUBLIC "${OpenVINO_INCLUDE_DIRS}")
target_link_libraries(ObjectQualityNode openvino::runtime)

target_include_directories(ObjectQualityNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(ObjectQualityNode "${OpenCV_LIBRARIES}")

target_link_libraries(ObjectQualityNode Threads::Threads dl fmt::fmt)

if(ENABLE_VAAPI)
    target_link_libraries(ObjectQualityNode image_inference_async)
    target_link_libraries(ObjectQualityNode vpl)
endif(ENABLE_VAAPI)
