cmake_minimum_required(VERSION 3.20)
project(V2XFusion LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_COMPILER icpx)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# set(CMAKE_BUILD_TYPE Debug)
set(CMAKE_BUILD_TYPE Release)

# BEVFusion unified ONNX requires a custom OpenVINO build with BevPoolV2,
# SparseConvolution, and SparseToDense ops.  Source the custom OV's
# setupvars.sh before running cmake so that find_package(OpenVINO) finds it:
#
#   source /path/to/custom_openvino/install/setupvars.sh
#   mkdir build && cd build && cmake .. && make -j$(nproc)
#
# If the found OpenVINO does not contain BevPoolV2, the bevfusion_unified
# target will compile but fail at runtime when loading the ONNX model.

find_package(OpenCV REQUIRED)
find_package(OpenVINO REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED CONFIG COMPONENTS system filesystem program_options)

# Common settings
set(SYCL_COMPAT_COMPILE_OPTIONS "")
if(CMAKE_CXX_COMPILER MATCHES "icpx|dpcpp" OR CMAKE_CXX_COMPILER_ID MATCHES "IntelLLVM|Clang")
    list(APPEND SYCL_COMPAT_COMPILE_OPTIONS -fno-sycl-id-queries-fit-in-int)
endif()

set(COMMON_COMPILE_OPTIONS -fsycl -fPIC ${SYCL_COMPAT_COMPILE_OPTIONS})
set(COMMON_LINK_OPTIONS -fsycl)
set(DEBUG_COMPILE_OPTIONS -g -O0)
set(RELEASE_COMPILE_OPTIONS -O3)

set(COMMON_INCLUDE_DIRS
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cam_bev
    ${CMAKE_CURRENT_SOURCE_DIR}/src/fusion
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    /opt/intel/oneapi/dpl/latest/include
    ${OpenCV_INCLUDE_DIRS}
    ${OpenVINO_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
)

# V2XFusion requires a custom OpenVINO build with BevPoolV2/SparseConv3d ops.
set(COMMON_LIBS
    sycl
    OpenCL
    ${OpenCV_LIBS}
    openvino::runtime
    Boost::program_options
    Boost::filesystem
    Boost::system
)

set(CAM_CORE
    src/cam_bev/camera-geometry.cpp
    src/cam_bev/bev.cc
    src/cam_bev/bev_sycl.cc
    src/cam_bev/bev_nms3diou.cc
    src/cam_bev/bev_utils.cpp
    src/cam_bev/bev_cam.cpp
)

set(BEV_POOL_CORE
    src/cam_bev/camera-geometry.cpp
    src/cam_bev/bev.cc
    src/cam_bev/bev_sycl.cc
    src/cam_bev/bev_nms3diou.cc
    src/cam_bev/bev_utils.cpp
)

set(POST_CORE
    src/fusion/postprocess_sycl.cpp
    src/fusion/postprocess_cpu.cpp
)
set(FUSER_CORE src/fusion/bev_fuser.cpp)
set(HEAD_CORE src/fusion/bev_head.cpp)
set(UNIFIED_CORE
    src/bevfusion_unified/voxelizer_sycl.cpp
)
set(COMMON_CORE src/common.cpp)
set(VIS_CORE src/visualization.cpp)
set(KITTI_CORE src/kitti_loader.cpp)
set(UTIL_CORE src/utilization_monitor.cpp)
set(SUPPORT_CORE
    ${COMMON_CORE}
    ${VIS_CORE}
    ${KITTI_CORE}
    ${UTIL_CORE}
)
set(TEST_SUPPORT_CORE test/test_utils.cpp)

function(configure_bev_target target_name include_scope link_scope)
    target_compile_options(${target_name} PRIVATE ${COMMON_COMPILE_OPTIONS})
    target_link_options(${target_name} PRIVATE ${COMMON_LINK_OPTIONS})
    target_include_directories(${target_name} ${include_scope} ${COMMON_INCLUDE_DIRS})
    target_link_libraries(${target_name} ${link_scope} ${COMMON_LIBS})
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        target_compile_options(${target_name} PRIVATE ${DEBUG_COMPILE_OPTIONS})
    else()
        target_compile_options(${target_name} PRIVATE ${RELEASE_COMPILE_OPTIONS})
    endif()
endfunction()

function(add_bev_library target_name)
    add_library(${target_name} STATIC ${ARGN})
    configure_bev_target(${target_name} PUBLIC PUBLIC)
endfunction()

function(add_bev_target target_name)
    add_executable(${target_name} ${ARGN})
    configure_bev_target(${target_name} PRIVATE PRIVATE)
endfunction()

add_bev_library(bevfusion_support
    ${SUPPORT_CORE}
)

add_bev_library(bevfusion_test_support
    ${TEST_SUPPORT_CORE}
)
target_link_libraries(bevfusion_test_support PUBLIC bevfusion_support)

add_bev_library(bevfusion_camera
    ${CAM_CORE}
)

# === PointPillars: decoupled voxelizer + 3-tensor PFE ONNX ===
add_bev_library(bevfusion_pointpillars
    src/pointpillars/voxelizer.cpp
    src/pointpillars/scatter.cpp
    src/pointpillars/pointpillars.cpp
)
target_link_libraries(bevfusion_pointpillars PUBLIC bevfusion_support)

add_bev_library(bevfusion_fusion
    ${FUSER_CORE}
    ${HEAD_CORE}
    ${POST_CORE}
)
target_link_libraries(bevfusion_fusion PUBLIC bevfusion_support)

add_bev_library(bevfusion_dataset_presets
    src/pipeline/dataset_preset.cpp
)

add_bev_library(bevfusion_pipeline_config
    src/pipeline/split_pipeline_config.cpp
)
target_link_libraries(bevfusion_pipeline_config PUBLIC bevfusion_dataset_presets bevfusion_support)

add_bev_library(bevfusion_unified_core
    ${UNIFIED_CORE}
)

add_bev_target(test_camera_geometry
    test/test_camera_geometry.cpp
)
target_link_libraries(test_camera_geometry PRIVATE bevfusion_camera bevfusion_test_support)

add_bev_target(test_bev_pool
    test/test_bev_pool.cpp
)
target_link_libraries(test_bev_pool PRIVATE bevfusion_camera bevfusion_test_support)

add_bev_target(test_viewtransform
    test/test_viewtransform.cpp
)
target_link_libraries(test_viewtransform PRIVATE bevfusion_camera bevfusion_test_support)
target_compile_options(test_viewtransform PRIVATE
    -std=gnu++17
    -D_GLIBCXX_USE_CXX11_ABI=1
    -DCL_TARGET_OPENCL_VERSION=300
    -Rno-debug-disables-optimization
)

add_bev_target(test_fuser
    test/test_fuser.cpp
)
target_link_libraries(test_fuser PRIVATE bevfusion_fusion bevfusion_test_support)
target_link_libraries(test_fuser PRIVATE bevfusion_pipeline_config)

add_bev_target(test_head
    test/test_head_inference.cpp
)
target_link_libraries(test_head PRIVATE bevfusion_fusion bevfusion_test_support)

add_bev_target(test_fusion_pipeline
    test/test_fusion_pipeline.cpp
)
target_link_libraries(test_fusion_pipeline PRIVATE bevfusion_fusion bevfusion_test_support)
target_link_libraries(test_fusion_pipeline PRIVATE bevfusion_pipeline_config)

add_bev_target(test_camera_bev_pipeline
    test/test_camera_bev_pipeline.cpp
)
target_link_libraries(test_camera_bev_pipeline PRIVATE bevfusion_camera bevfusion_support bevfusion_test_support)

add_bev_target(test_pointpillars_voxelizer
    test/test_pointpillars_voxelizer.cpp
)
target_link_libraries(test_pointpillars_voxelizer PRIVATE bevfusion_pointpillars bevfusion_test_support)

add_bev_target(test_lidar_pipeline
    test/test_lidar_pipeline.cpp
)
target_link_libraries(test_lidar_pipeline PRIVATE bevfusion_pointpillars bevfusion_support bevfusion_test_support)

add_bev_target(test_pointpillars
    test/test_pointpillars.cpp
)
target_link_libraries(test_pointpillars PRIVATE bevfusion_pointpillars bevfusion_test_support)

add_bev_target(test_bevfusion_pipeline
    test/test_bevfusion_pipeline.cpp
)
target_link_libraries(test_bevfusion_pipeline PRIVATE
    bevfusion_pipeline_config
    bevfusion_camera
    bevfusion_pointpillars
    bevfusion_fusion
    bevfusion_support
    bevfusion_test_support
)

add_bev_target(bevfusion
    test/bevfusion.cpp
)
target_link_libraries(bevfusion PRIVATE
    bevfusion_pipeline_config
    bevfusion_camera
    bevfusion_pointpillars
    bevfusion_fusion
    bevfusion_support
    bevfusion_test_support
)

add_bev_target(bevfusion_unified
    test/bevfusion_unified.cpp
)
target_link_libraries(bevfusion_unified PRIVATE
    bevfusion_dataset_presets
    bevfusion_unified_core
    bevfusion_camera
    bevfusion_fusion
    bevfusion_support
    bevfusion_test_support
)
