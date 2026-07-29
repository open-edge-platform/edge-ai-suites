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

if (NOT MINIMAL_PACKAGE)
  set(BUILD_SHARED_LIBS ON CACHE STRING "Link to shared libraries requested by aws")
  find_package(AWSSDK REQUIRED COMPONENTS s3 core)

  add_library(media_storage SHARED IMPORTED)
  add_library(utility SHARED IMPORTED)

  message("AWSSDK_LINK_LIBRARIES: ${AWSSDK_LINK_LIBRARIES}")

  set_target_properties(media_storage PROPERTIES
      IMPORTED_LOCATION "${PROJECT_SOURCE_DIR}/ai_inference/3rdParty/media_storage/lib/libmedia_storage.so"
      INTERFACE_INCLUDE_DIRECTORIES "${PROJECT_SOURCE_DIR}/../storage_sdk/images_client_sdk/cpp/include/"
      INTERFACE_LINK_LIBRARIES "${AWSSDK_LINK_LIBRARIES}"
  )
  set_target_properties(utility PROPERTIES
      IMPORTED_LOCATION "${PROJECT_SOURCE_DIR}/ai_inference/3rdParty/media_storage/lib/libutility.so"
      INTERFACE_INCLUDE_DIRECTORIES "${PROJECT_SOURCE_DIR}/../storage_sdk/images_client_sdk/cpp/include/"
      INTERFACE_LINK_LIBRARIES "${AWSSDK_LINK_LIBRARIES}"
  )

  #----------------Generate StorageVideoInputNode.so file---------------------#
  add_library(StorageVideoInputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/StorageVideoInputNode.cpp
  ${BASE_NODE_DIR}/baseMediaInputNode.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
  
  target_compile_definitions(StorageVideoInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
  target_link_libraries(StorageVideoInputNode hva)
  target_include_directories(StorageVideoInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
  target_include_directories(StorageVideoInputNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
  
  target_link_libraries(StorageVideoInputNode ${Boost_LIBRARIES})
  target_include_directories(StorageVideoInputNode PUBLIC ${Boost_INCLUDE_DIRS})
  
  target_link_libraries(StorageVideoInputNode media_storage utility)
  
  target_link_libraries(StorageVideoInputNode Threads::Threads dl)

  #----------------Generate StorageImageInputNode.so file---------------------#
  add_library(StorageImageInputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/StorageImageInputNode.cpp
  ${BASE_NODE_DIR}/baseMediaInputNode.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

  target_compile_definitions(StorageImageInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
  target_link_libraries(StorageImageInputNode hva)
  target_include_directories(StorageImageInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
  target_include_directories(StorageImageInputNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

  target_link_libraries(StorageImageInputNode ${Boost_LIBRARIES})
  target_include_directories(StorageImageInputNode PUBLIC ${Boost_INCLUDE_DIRS})

  target_link_libraries(StorageImageInputNode media_storage utility)

  target_link_libraries(StorageImageInputNode Threads::Threads dl)

  #----------------Generate LLResultSinkNode .so file---------------------#
  add_library(LLResultSinkNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/LLResultSinkNode.cpp
  ${BASE_NODE_DIR}/baseResponseNode.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp)

  target_compile_definitions(LLResultSinkNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
  target_link_libraries(LLResultSinkNode hva)
  target_include_directories(LLResultSinkNode PUBLIC ${HVA_INC_DIR})
  target_include_directories(LLResultSinkNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

  target_link_libraries(LLResultSinkNode ${Boost_LIBRARIES})
  target_include_directories(LLResultSinkNode PUBLIC ${Boost_INCLUDE_DIRS})

  add_library(featureStorage SHARED IMPORTED)
  set_target_properties(featureStorage PROPERTIES
      IMPORTED_LOCATION "${PROJECT_SOURCE_DIR}/ai_inference/3rdParty/feature_storage/lib/libfeature_storage.so"
      INTERFACE_INCLUDE_DIRECTORIES ${PROJECT_SOURCE_DIR}/../
      IMPORTED_NO_SONAME true # because this libfeature_storage.so has no so_name field in .dynamic section
  )

  target_link_libraries(LLResultSinkNode featureStorage)

  #----------------Generate StorageImageUploadNode.so file---------------------#
  find_package(OpenCV REQUIRED)
  message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
  message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

  add_library(StorageImageUploadNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/StorageImageUploadNode.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
  ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

  target_compile_definitions(StorageImageUploadNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
  target_link_libraries(StorageImageUploadNode hva)
  target_include_directories(StorageImageUploadNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
  target_include_directories(StorageImageUploadNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

  target_include_directories(StorageImageUploadNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
  target_link_libraries(StorageImageUploadNode "${OpenCV_LIBRARIES}")

  target_link_libraries(StorageImageUploadNode ${Boost_LIBRARIES})
  target_include_directories(StorageImageUploadNode PUBLIC ${Boost_INCLUDE_DIRS})

  target_link_libraries(StorageImageUploadNode media_storage utility)

  target_link_libraries(StorageImageUploadNode Threads::Threads dl)

endif()

#----------------Generate RawImageInputNode .so file---------------------#
add_library(RawImageInputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/RawImageInputNode.cpp
${BASE_NODE_DIR}/baseMediaInputNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(RawImageInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RawImageInputNode hva)
target_include_directories(RawImageInputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(RawImageInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate LocalMediaInputNode.so file---------------------#
add_library(LocalMediaInputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/LocalMediaInputNode.cpp
${BASE_NODE_DIR}/baseMediaInputNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(LocalMediaInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LocalMediaInputNode hva)
target_include_directories(LocalMediaInputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LocalMediaInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

target_link_libraries(LocalMediaInputNode ${Boost_LIBRARIES})
target_include_directories(LocalMediaInputNode PUBLIC ${Boost_INCLUDE_DIRS})

target_link_libraries(LocalMediaInputNode Threads::Threads dl)

#----------------Generate LLOutputNode .so file---------------------#
add_library(LLOutputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/LLOutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(LLOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LLOutputNode hva)
target_include_directories(LLOutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LLOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate FakeSinkNode .so file---------------------#
add_library(FakeSinkNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/FakeSinkNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(FakeSinkNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(FakeSinkNode hva)
target_include_directories(FakeSinkNode PUBLIC ${HVA_INC_DIR})
target_include_directories(FakeSinkNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate LLResultSinkFileNode .so file---------------------#

find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LLResultSinkFileNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/LLResultSinkFileNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/tools/dumper/buffer_dumper.cpp)

target_compile_definitions(LLResultSinkFileNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LLResultSinkFileNode hva)
target_include_directories(LLResultSinkFileNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LLResultSinkFileNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

target_include_directories(LLResultSinkFileNode PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LLResultSinkFileNode "${OpenCV_LIBRARIES}")

if(ENABLE_VAAPI)
    target_link_libraries(LLResultSinkFileNode vpl)
endif(ENABLE_VAAPI)


#----------------Generate CPUJpegDecoderNode .so file---------------------#
add_library(CPUJpegDecoderNode SHARED JpegDecoderNode.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(CPUJpegDecoderNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(CPUJpegDecoderNode hva)
target_include_directories(CPUJpegDecoderNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(CPUJpegDecoderNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(CPUJpegDecoderNode ${Boost_LIBRARIES})
target_include_directories(CPUJpegDecoderNode PUBLIC ${Boost_INCLUDE_DIRS})

target_include_directories(CPUJpegDecoderNode PUBLIC "${GLIB_INCLUDE_DIRS}" "${BOOST_INC_DIR}")
target_link_libraries(CPUJpegDecoderNode Threads::Threads dl)

if(${LSB_RELEASE_ID_SHORT} MATCHES "CentOS")
    message(STATUS "${LSB_RELEASE_ID_SHORT}: CPUJpegDecoderNode include and link libav.")
    target_include_directories(CPUJpegDecoderNode PUBLIC
        /usr/include/ffmpeg/libavcodec
        /usr/include/ffmpeg/libavformat
        /usr/include/ffmpeg/libswscale
        /usr/include/ffmpeg
    )
    target_link_libraries(CPUJpegDecoderNode
        /usr/lib64/libavcodec.so
        /usr/lib64/libavformat.so
        /usr/lib64/libswscale.so
        /usr/lib64/libavutil.so
    )
elseif((${LSB_RELEASE_ID_SHORT} MATCHES "Debian") OR (${LSB_RELEASE_ID_SHORT} MATCHES "Ubuntu"))
    message(STATUS "${LSB_RELEASE_ID_SHORT}: CPUJpegDecoderNode include and link libav.")
    target_include_directories(CPUJpegDecoderNode PUBLIC
        /usr/include/x86_64-linux-gnu/libavcodec
        /usr/include/x86_64-linux-gnu/libavformat
        /usr/include/x86_64-linux-gnu/libswscale
    )

    target_link_libraries(CPUJpegDecoderNode
        /usr/lib/x86_64-linux-gnu/libavcodec.so
        /usr/lib/x86_64-linux-gnu/libavformat.so
        /usr/lib/x86_64-linux-gnu/libswscale.so
        /usr/lib/x86_64-linux-gnu/libavutil.so
    )
endif()

#----------------Generate VideoDecoderNode.so file---------------------#
add_library(VideoDecoderNode SHARED VideoDecoderNode.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(VideoDecoderNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(VideoDecoderNode hva)
target_include_directories(VideoDecoderNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(VideoDecoderNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(VideoDecoderNode ${Boost_LIBRARIES})
target_include_directories(VideoDecoderNode PUBLIC ${Boost_INCLUDE_DIRS})

target_include_directories(VideoDecoderNode PUBLIC "${GLIB_INCLUDE_DIRS}" "${BOOST_INC_DIR}")
target_link_libraries(VideoDecoderNode Threads::Threads dl)

if(${LSB_RELEASE_ID_SHORT} MATCHES "CentOS")
    message(STATUS "${LSB_RELEASE_ID_SHORT}: VideoDecoderNode include and link libav.")
    target_include_directories(VideoDecoderNode PUBLIC
        /usr/include/ffmpeg/libavcodec
        /usr/include/ffmpeg/libavformat
        /usr/include/ffmpeg/libswscale
        /usr/include/ffmpeg
    )
    target_link_libraries(VideoDecoderNode
        /usr/lib64/libavcodec.so
        /usr/lib64/libavformat.so
        /usr/lib64/libswscale.so
        /usr/lib64/libavutil.so
    )
elseif((${LSB_RELEASE_ID_SHORT} MATCHES "Debian") OR (${LSB_RELEASE_ID_SHORT} MATCHES "Ubuntu"))
    message(STATUS "${LSB_RELEASE_ID_SHORT}: VideoDecoderNode include and link libav.")
    target_include_directories(VideoDecoderNode PUBLIC
        /usr/include/x86_64-linux-gnu/libavcodec
        /usr/include/x86_64-linux-gnu/libavformat
        /usr/include/x86_64-linux-gnu/libswscale
    )

    target_link_libraries(VideoDecoderNode
        /usr/lib/x86_64-linux-gnu/libavcodec.so
        /usr/lib/x86_64-linux-gnu/libavformat.so
        /usr/lib/x86_64-linux-gnu/libswscale.so
        /usr/lib/x86_64-linux-gnu/libavutil.so
    )
endif()


#----------------Generate SimpleJpegDecOpenCV .so file---------------------#

find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(SimpleJpegDecOpenCV SHARED SimpleJpegDecOpenCV.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(SimpleJpegDecOpenCV PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(SimpleJpegDecOpenCV hva)
target_include_directories(SimpleJpegDecOpenCV PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(SimpleJpegDecOpenCV PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(SimpleJpegDecOpenCV ${Boost_LIBRARIES})
target_include_directories(SimpleJpegDecOpenCV PUBLIC ${Boost_INCLUDE_DIRS})

target_include_directories(SimpleJpegDecOpenCV PUBLIC "${OpenCV_INCLUDE_DIRS}")
target_link_libraries(SimpleJpegDecOpenCV "${OpenCV_LIBRARIES}")

target_link_libraries(SimpleJpegDecOpenCV Threads::Threads dl)

#----------------Generate TrackerNode_CPU .so file---------------------#
file(GLOB TRACKER_UTILS_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/vas/components/ot/*.cpp"
                             "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/vas/components/ot/mtt/*.cpp"
                             "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/vas/components/ot/kalman_filter/*.cpp"
                             "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/vas/components/ot/container/*.cpp")
message("TRACKER_UTILS_SRCS: ${TRACKER_UTILS_SRCS}")

find_package(OpenCV REQUIRED)
message("OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message("OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(TrackerNode_CPU SHARED TrackerNode_CPU.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
                                                       ${PROJECT_SOURCE_DIR}/ai_inference/source/modules/tracklet_wrap.cpp
                                                       ${PROJECT_SOURCE_DIR}/ai_inference/source/modules/tracker.cpp
                                                       ${TRACKER_UTILS_SRCS})
target_compile_definitions(TrackerNode_CPU PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(TrackerNode_CPU hva)
target_include_directories(TrackerNode_CPU PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(TrackerNode_CPU PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(TrackerNode_CPU ${Boost_LIBRARIES})
target_include_directories(TrackerNode_CPU PUBLIC ${Boost_INCLUDE_DIRS})

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(TrackerNode_CPU "${OpenCV_LIBRARIES}")

target_link_libraries(TrackerNode_CPU Threads::Threads dl)

if(ENABLE_VAAPI)
    target_link_libraries(TrackerNode_CPU vpl)
endif(ENABLE_VAAPI)

#----------------Generate ObjectSelectNode.so file---------------------#

add_library(ObjectSelectNode SHARED ObjectSelectNode.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(ObjectSelectNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(ObjectSelectNode hva)
target_include_directories(ObjectSelectNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(ObjectSelectNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(ObjectSelectNode ${Boost_LIBRARIES})
target_include_directories(ObjectSelectNode PUBLIC ${Boost_INCLUDE_DIRS})

target_link_libraries(ObjectSelectNode Threads::Threads dl)

#----------------Generate MediaOutputNode .so file---------------------#
add_library(MediaOutputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/MediaOutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(MediaOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(MediaOutputNode hva)
target_include_directories(MediaOutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(MediaOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate Media2COutputNode .so file---------------------#
add_library(Media2COutputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/Media2COutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(Media2COutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Media2COutputNode hva)
target_include_directories(Media2COutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(Media2COutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate Media3COutputNode .so file---------------------#
add_library(Media3COutputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/Media3COutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(Media3COutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Media3COutputNode hva)
target_include_directories(Media3COutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(Media3COutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate Media4COutputNode .so file---------------------#
add_library(Media4COutputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/Media4COutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(Media4COutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Media4COutputNode hva)
target_include_directories(Media4COutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(Media4COutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate Media6COutputNode .so file---------------------#
add_library(Media6COutputNode SHARED ${CMAKE_CURRENT_SOURCE_DIR}/Media6COutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(Media6COutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Media6COutputNode hva)
target_include_directories(Media6COutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(Media6COutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate CoordinateTransformationNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(CoordinateTransformationNode SHARED CoordinateTransformationNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(CoordinateTransformationNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(CoordinateTransformationNode hva)
target_include_directories(CoordinateTransformationNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(CoordinateTransformationNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(CoordinateTransformationNode "${OpenCV_LIBRARIES}")

target_link_libraries(CoordinateTransformationNode Threads::Threads dl)


#----------------Generate LidarCamCoordinateTransformationNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LidarCamCoordinateTransformationNode SHARED LidarCamCoordinateTransformationNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper_lidar.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(LidarCamCoordinateTransformationNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCamCoordinateTransformationNode hva)
target_include_directories(LidarCamCoordinateTransformationNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCamCoordinateTransformationNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCamCoordinateTransformationNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCamCoordinateTransformationNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCamCoordinateTransformationNode Threads::Threads dl)

#----------------Generate Camera2CFusionNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(Camera2CFusionNode SHARED Camera2CFusionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(Camera2CFusionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Camera2CFusionNode hva)
target_include_directories(Camera2CFusionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(Camera2CFusionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(Camera2CFusionNode "${OpenCV_LIBRARIES}")

target_link_libraries(Camera2CFusionNode Threads::Threads dl)


#----------------Generate LidarCam2CFusionNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LidarCam2CFusionNode SHARED LidarCam2CFusionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper_lidar.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(LidarCam2CFusionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCam2CFusionNode hva)
target_include_directories(LidarCam2CFusionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCam2CFusionNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCam2CFusionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCam2CFusionNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCam2CFusionNode Threads::Threads dl)


#----------------Generate LidarCam3CFusionNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LidarCam3CFusionNode SHARED LidarCam3CFusionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper_lidar.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(LidarCam3CFusionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCam3CFusionNode hva)
target_include_directories(LidarCam3CFusionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCam3CFusionNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCam3CFusionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCam3CFusionNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCam3CFusionNode Threads::Threads dl)


#----------------Generate LidarCam4CFusionNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LidarCam4CFusionNode SHARED LidarCam4CFusionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper_lidar.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(LidarCam4CFusionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCam4CFusionNode hva)
target_include_directories(LidarCam4CFusionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCam4CFusionNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCam4CFusionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCam4CFusionNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCam4CFusionNode Threads::Threads dl)

#----------------Generate LidarCam6CFusionNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LidarCam6CFusionNode SHARED LidarCam6CFusionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper_lidar.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(LidarCam6CFusionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCam6CFusionNode hva)
target_include_directories(LidarCam6CFusionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCam6CFusionNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCam6CFusionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCam6CFusionNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCam6CFusionNode Threads::Threads dl)


#----------------Generate Camera4CFusionNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(Camera4CFusionNode SHARED Camera4CFusionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(Camera4CFusionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Camera4CFusionNode hva)
target_include_directories(Camera4CFusionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(Camera4CFusionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(Camera4CFusionNode "${OpenCV_LIBRARIES}")

target_link_libraries(Camera4CFusionNode Threads::Threads dl)

#----------------Generate Track2TrackAssociationNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(Track2TrackAssociationNode SHARED Track2TrackAssociationNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/vas/components/ot/mtt/hungarian_wrap.cpp)
target_compile_definitions(Track2TrackAssociationNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(Track2TrackAssociationNode hva)
target_include_directories(Track2TrackAssociationNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(Track2TrackAssociationNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(Track2TrackAssociationNode "${OpenCV_LIBRARIES}")

target_link_libraries(Track2TrackAssociationNode Threads::Threads dl)


#----------------Generate LidarCamTrack2TrackAssociationNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")

add_library(LidarCamTrack2TrackAssociationNode SHARED LidarCamTrack2TrackAssociationNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/fusion/data_fusion_helper_lidar.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/vas/components/ot/mtt/hungarian_wrap.cpp)
target_compile_definitions(LidarCamTrack2TrackAssociationNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCamTrack2TrackAssociationNode hva)
target_include_directories(LidarCamTrack2TrackAssociationNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCamTrack2TrackAssociationNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCamTrack2TrackAssociationNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCamTrack2TrackAssociationNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCamTrack2TrackAssociationNode Threads::Threads dl)

#----------------Generate PostFusionOutputNode .so file---------------------#
add_library(PostFusionOutputNode SHARED PostFusionOutputNode.cpp 
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(PostFusionOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(PostFusionOutputNode hva)
target_include_directories(PostFusionOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(PostFusionOutputNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(PostFusionOutputNode ${Boost_LIBRARIES})
target_include_directories(PostFusionOutputNode PUBLIC ${Boost_INCLUDE_DIRS})

#----------------Generate LidarCamFusionOutputNode .so file---------------------#
find_package(OpenCV REQUIRED)
message(DEBUG "OpenCV_INCLUDE_DIRS: ${OpenCV_INCLUDE_DIRS}")
message(DEBUG "OpenCV_LIBRARIES: ${OpenCV_LIBRARIES}")
add_library(LidarCamFusionOutputNode SHARED LidarCamFusionOutputNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(LidarCamFusionOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCamFusionOutputNode hva)
target_include_directories(LidarCamFusionOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarCamFusionOutputNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCamFusionOutputNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
include_directories("${OpenCV_INCLUDE_DIRS}")
target_link_libraries(LidarCamFusionOutputNode "${OpenCV_LIBRARIES}")

target_link_libraries(LidarCamFusionOutputNode ${Boost_LIBRARIES})
target_include_directories(LidarCamFusionOutputNode PUBLIC ${Boost_INCLUDE_DIRS})

#----------------Generate RadarPreProcessingNode.so file---------------------#
find_package(MKL CONFIG REQUIRED)
# if(MKL_ENV)
#   set_tests_properties(mytest PROPERTIES ENVIRONMENT "${MKL_ENV}")
# endif()

# file(GLOB MODEL_PROC_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/model_proc/json_reader.cpp")
# message(DEBUG "MODEL_PROC_SRCS: ${MODEL_PROC_SRCS}")

add_library(RadarPreProcessingNode SHARED RadarPreProcessingNode.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp ${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/radar_config_parser.cpp)
target_compile_definitions(RadarPreProcessingNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarPreProcessingNode hva)
target_include_directories(RadarPreProcessingNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>" )
target_include_directories(RadarPreProcessingNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
target_include_directories(RadarPreProcessingNode PUBLIC  $<TARGET_PROPERTY:MKL::MKL,INTERFACE_INCLUDE_DIRECTORIES>)
target_include_directories(RadarPreProcessingNode PUBLIC ${JSON_INC_DIR})

target_link_libraries(RadarPreProcessingNode ${Boost_LIBRARIES})
target_include_directories(RadarPreProcessingNode PUBLIC ${Boost_INCLUDE_DIRS})
target_compile_options(RadarPreProcessingNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_COMPILE_OPTIONS>)
# target_link_libraries(RadarPreProcessingNode media_storage utility)
target_link_libraries(RadarPreProcessingNode $<LINK_ONLY:MKL::MKL>)
target_link_libraries(RadarPreProcessingNode Threads::Threads dl)

#----------------Generate RadarDetectionNode.so file---------------------#
find_package(MKL CONFIG REQUIRED)
# if(MKL_ENV)
#   set_tests_properties(mytest PROPERTIES ENVIRONMENT "${MKL_ENV}")
# endif()

# file(GLOB MODEL_PROC_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/model_proc/json_reader.cpp")
# message(DEBUG "MODEL_PROC_SRCS: ${MODEL_PROC_SRCS}")

add_library(RadarDetectionNode SHARED RadarDetectionNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/radar_detection_helper.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)
target_compile_definitions(RadarDetectionNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarDetectionNode hva)
target_include_directories(RadarDetectionNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>" )
target_include_directories(RadarDetectionNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
target_include_directories(RadarDetectionNode PUBLIC  $<TARGET_PROPERTY:MKL::MKL,INTERFACE_INCLUDE_DIRECTORIES>)

target_link_libraries(RadarDetectionNode ${Boost_LIBRARIES})
target_include_directories(RadarDetectionNode PUBLIC ${Boost_INCLUDE_DIRS})
target_compile_options(RadarDetectionNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_COMPILE_OPTIONS>)
# target_link_libraries(RadarPreProcessingNode media_storage utility)
target_link_libraries(RadarDetectionNode $<LINK_ONLY:MKL::MKL>)
target_link_libraries(RadarDetectionNode Threads::Threads dl)

#----------------Generate RadarClusteringNode.so file---------------------#
add_library(RadarClusteringNode SHARED RadarClusteringNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(RadarClusteringNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarClusteringNode hva)
target_include_directories(RadarClusteringNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(RadarClusteringNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(RadarClusteringNode Threads::Threads dl)

#----------------Generate RadarTrackingNode.so file---------------------#
find_package(Eigen3 REQUIRED)
include_directories(/usr/include/eigen3)
add_library(RadarTrackingNode SHARED RadarTrackingNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/radar_tracking_helper.cpp)

target_compile_definitions(RadarTrackingNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarTrackingNode hva)
target_include_directories(RadarTrackingNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(RadarTrackingNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")

target_link_libraries(RadarTrackingNode Threads::Threads dl)

#----------------Generate RadarDetectionOutputNode .so file---------------------#
add_library(RadarDetectionOutputNode SHARED RadarDetectionOutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(RadarDetectionOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarDetectionOutputNode hva)
target_include_directories(RadarDetectionOutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(RadarDetectionOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate RadarPCLSinkFileNode .so file---------------------#

add_library(RadarPCLSinkFileNode SHARED RadarPCLSinkFileNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)


target_compile_definitions(RadarPCLSinkFileNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarPCLSinkFileNode hva)
target_include_directories(RadarPCLSinkFileNode PUBLIC ${HVA_INC_DIR})
target_include_directories(RadarPCLSinkFileNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate RadarClusteringSinkFileNode .so file---------------------#

add_library(RadarClusteringSinkFileNode SHARED RadarClusteringSinkFileNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)


target_compile_definitions(RadarClusteringSinkFileNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarClusteringSinkFileNode hva)
target_include_directories(RadarClusteringSinkFileNode PUBLIC ${HVA_INC_DIR})
target_include_directories(RadarClusteringSinkFileNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate RadarResultSinkFileNode .so file---------------------#

add_library(RadarResultSinkFileNode SHARED RadarResultSinkFileNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)


target_compile_definitions(RadarResultSinkFileNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarResultSinkFileNode hva)
target_include_directories(RadarResultSinkFileNode PUBLIC ${HVA_INC_DIR})
target_include_directories(RadarResultSinkFileNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")


#----------------Generate RadarOutputNode .so file---------------------#
add_library(RadarOutputNode SHARED RadarOutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(RadarOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarOutputNode hva)
target_include_directories(RadarOutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(RadarOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

#----------------Generate LocalMultiSensorInputNode.so file---------------------#

add_library(LocalMultiSensorInputNode SHARED LocalMultiSensorInputNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(LocalMultiSensorInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LocalMultiSensorInputNode hva)
target_include_directories(LocalMultiSensorInputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LocalMultiSensorInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

target_link_libraries(LocalMultiSensorInputNode Threads::Threads dl)

#----------------Generate LidarCamFusionInputNode.so file---------------------#

add_library(LidarCamFusionInputNode SHARED LidarCamFusionInputNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/include/nodes/lidarDatabaseMeta.hpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/lidar/kitti_loader.cpp)

target_compile_definitions(LidarCamFusionInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarCamFusionInputNode hva)
target_include_directories(LidarCamFusionInputNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")
target_include_directories(LidarCamFusionInputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LidarCamFusionInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

target_link_libraries(LidarCamFusionInputNode Threads::Threads dl)

#----------------Generate LocalMediaSensorInputNode.so file---------------------#

add_library(LocalMediaSensorInputNode SHARED LocalMediaSensorInputNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(LocalMediaSensorInputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LocalMediaSensorInputNode hva)
target_include_directories(LocalMediaSensorInputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LocalMediaSensorInputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")

target_link_libraries(LocalMediaSensorInputNode Threads::Threads dl)
#----------------Generate MediaRadarOutputNode .so file---------------------#
add_library(MediaRadarOutputNode SHARED MediaRadarOutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(MediaRadarOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(MediaRadarOutputNode hva)
target_include_directories(MediaRadarOutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(MediaRadarOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")


#----------------Generate RadarResultReadFileNode.so file---------------------#
find_package(MKL CONFIG REQUIRED)
# if(MKL_ENV)
#   set_tests_properties(mytest PROPERTIES ENVIRONMENT "${MKL_ENV}")
# endif()

# file(GLOB MODEL_PROC_SRCS "${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/model_proc/json_reader.cpp")
# message(DEBUG "MODEL_PROC_SRCS: ${MODEL_PROC_SRCS}")

add_library(RadarResultReadFileNode SHARED RadarResultReadFileNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/radar_config_parser.cpp)
target_compile_definitions(RadarResultReadFileNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(RadarResultReadFileNode hva)
target_include_directories(RadarResultReadFileNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>" )
target_include_directories(RadarResultReadFileNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
target_include_directories(RadarResultReadFileNode PUBLIC  $<TARGET_PROPERTY:MKL::MKL,INTERFACE_INCLUDE_DIRECTORIES>)
target_include_directories(RadarResultReadFileNode PUBLIC ${JSON_INC_DIR})

target_link_libraries(RadarResultReadFileNode ${Boost_LIBRARIES})
target_include_directories(RadarResultReadFileNode PUBLIC ${Boost_INCLUDE_DIRS})
target_compile_options(RadarResultReadFileNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_COMPILE_OPTIONS>)
# target_link_libraries(RadarResultReadFileNode media_storage utility)
target_link_libraries(RadarResultReadFileNode $<LINK_ONLY:MKL::MKL>)
target_link_libraries(RadarResultReadFileNode Threads::Threads dl)


#----------------Generate RadarSignalProcessingNode.so file---------------------#
find_package(MKL CONFIG REQUIRED)
# include_directories(${PROJECT_SOURCE_DIR/ai_nference/libradar/src})
add_library(RadarSignalProcessingNode SHARED RadarSignalProcessingNode.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/base64.cpp 
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/radar_config_parser.cpp
${PROJECT_SOURCE_DIR}/ai_inference/source/modules/inference_util/radar/libradar_helper.cpp)
target_compile_definitions(RadarSignalProcessingNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
link_directories(${PROJECT_SOURCE_DIR}/build/lib)
target_link_libraries(RadarSignalProcessingNode hva)
target_include_directories(RadarSignalProcessingNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>" )
target_include_directories(RadarSignalProcessingNode PUBLIC "$<BUILD_INTERFACE:${HVA_INC_DIR}>")
target_include_directories(RadarSignalProcessingNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/libradar/src")
target_include_directories(RadarSignalProcessingNode PUBLIC  $<TARGET_PROPERTY:MKL::MKL,INTERFACE_INCLUDE_DIRECTORIES>)
target_include_directories(RadarSignalProcessingNode PUBLIC ${JSON_INC_DIR})


target_link_libraries(RadarSignalProcessingNode ${Boost_LIBRARIES})
target_include_directories(RadarSignalProcessingNode PUBLIC ${Boost_INCLUDE_DIRS})
target_compile_options(RadarSignalProcessingNode PUBLIC $<TARGET_PROPERTY:MKL::MKL,INTERFACE_COMPILE_OPTIONS>)
# target_link_libraries(RadarPreProcessingNode media_storage utility)
target_link_libraries(RadarSignalProcessingNode $<LINK_ONLY:MKL::MKL>)
target_link_libraries(RadarSignalProcessingNode Threads::Threads dl radar)

#----------------Generate LidarOutputNode .so file---------------------#
add_library(LidarOutputNode SHARED LidarOutputNode.cpp
${BASE_NODE_DIR}/baseResponseNode.cpp
${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src/liblidar.hpp
${PROJECT_SOURCE_DIR}/ai_inference/source/common/common.cpp)

target_compile_definitions(LidarOutputNode PRIVATE HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY)
target_link_libraries(LidarOutputNode hva)
target_include_directories(LidarOutputNode PUBLIC ${HVA_INC_DIR})
target_include_directories(LidarOutputNode PUBLIC "$<BUILD_INTERFACE:${AI_INF_SERVER_NODES_INC_DIR}>")
target_include_directories(LidarOutputNode PUBLIC "${PROJECT_SOURCE_DIR}/ai_inference/liblidar/src")