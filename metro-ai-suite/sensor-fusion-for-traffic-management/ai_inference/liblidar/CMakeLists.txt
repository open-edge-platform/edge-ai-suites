cmake_minimum_required(VERSION 3.16)

project(liblidar VERSION 1.0.0 LANGUAGES CXX)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build options
option(BUILD_SHARED_LIBS "Build shared libraries" ON)
option(BUILD_EXAMPLES "Build example programs" OFF)
option(USE_STRICT_DEPENDENCIES "Require all dependencies to be found" ON)

# Compiler and dependency detection
find_program(ICPX_COMPILER icpx)
if(ICPX_COMPILER)
    set(CMAKE_CXX_COMPILER ${ICPX_COMPILER})
    set(USE_SYCL ON)
    message(STATUS "Found Intel DPC++ compiler: ${ICPX_COMPILER}")
else()
    set(USE_SYCL OFF)
    message(WARNING "Intel DPC++ compiler (icpx) not found, SYCL features disabled")
endif()

# Find dependencies with graceful fallback
macro(find_optional_dependency name)
    if(USE_STRICT_DEPENDENCIES)
        find_package(${ARGV} REQUIRED)
    else()
        find_package(${ARGV} QUIET)
        if(NOT ${name}_FOUND)
            message(WARNING "${name} not found - some features may be disabled")
        endif()
    endif()
endmacro()

# Find required packages
find_optional_dependency(PkgConfig)
find_optional_dependency(OpenCV COMPONENTS core highgui imgcodecs imgproc)
find_optional_dependency(Eigen3)
find_optional_dependency(Boost COMPONENTS system filesystem program_options)

# Find OpenVINO
set(OPENVINO_ROOT "/opt/intel/openvino_2025")
find_path(OPENVINO_INCLUDE_DIR 
    NAMES openvino/openvino.hpp
    PATHS ${OPENVINO_ROOT}/runtime/include
    NO_DEFAULT_PATH
)

find_library(OPENVINO_LIBRARY
    NAMES openvino
    PATHS ${OPENVINO_ROOT}/runtime/lib/intel64
    NO_DEFAULT_PATH
)

# 验证 OpenVINO 路径
if(NOT OPENVINO_INCLUDE_DIR)
    message(FATAL_ERROR "OpenVINO headers not found in ${OPENVINO_ROOT}/runtime/include")
endif()
if(NOT OPENVINO_LIBRARY)
    message(FATAL_ERROR "OpenVINO library not found in ${OPENVINO_ROOT}/runtime/lib/intel64")
endif()

message(STATUS "Using OpenVINO from: ${OPENVINO_ROOT}")
message(STATUS "OpenVINO include: ${OPENVINO_INCLUDE_DIR}")
message(STATUS "OpenVINO library: ${OPENVINO_LIBRARY}")

# Find OpenCL
find_path(OPENCL_INCLUDE_DIR
    NAMES CL/cl.h
    PATHS /opt/OpenCL/include
          /usr/include
)

find_library(OPENCL_LIBRARY
    NAMES OpenCL
    PATHS /opt/OpenCL/lib
          /usr/lib
          /usr/lib64
)

# Set Intel oneAPI paths if available
set(INTEL_ONEAPI_ROOT "/opt/intel/oneapi")
if(EXISTS "${INTEL_ONEAPI_ROOT}")
    set(DPC_INCLUDE_DIR "${INTEL_ONEAPI_ROOT}/dpl/latest/include")
    set(SYCL_INCLUDE_DIR "${INTEL_ONEAPI_ROOT}/compiler/latest/include")
    set(COMPILER_LIB_DIR "${INTEL_ONEAPI_ROOT}/compiler/latest/lib")
else()
    set(DPC_INCLUDE_DIR "")
    set(SYCL_INCLUDE_DIR "")
    set(COMPILER_LIB_DIR "")
endif()

# Include directories setup
set(LIBLIDAR_INCLUDE_DIRS)
file(GLOB ONEAPI_INCLUDE_CANDIDATES "/opt/intel/oneapi/202*.*/include")
list(APPEND LIBLIDAR_INCLUDE_DIRS ${ONEAPI_INCLUDE_CANDIDATES})
if(DPC_INCLUDE_DIR AND EXISTS "${DPC_INCLUDE_DIR}")
    list(APPEND LIBLIDAR_INCLUDE_DIRS ${DPC_INCLUDE_DIR})
endif()
if(USE_SYCL AND SYCL_INCLUDE_DIR AND EXISTS "${SYCL_INCLUDE_DIR}")
    list(APPEND LIBLIDAR_INCLUDE_DIRS ${SYCL_INCLUDE_DIR})
endif()
if(OPENVINO_INCLUDE_DIR)
    list(APPEND LIBLIDAR_INCLUDE_DIRS ${OPENVINO_INCLUDE_DIR})
endif()
if(OPENCL_INCLUDE_DIR)
    list(APPEND LIBLIDAR_INCLUDE_DIRS ${OPENCL_INCLUDE_DIR})
endif()
if(EXISTS "/usr/include/eigen3")
    list(APPEND LIBLIDAR_INCLUDE_DIRS "/usr/include/eigen3")
endif()

# Link libraries setup
set(LIBLIDAR_LINK_LIBS)
if(OpenCV_FOUND)
    list(APPEND LIBLIDAR_LINK_LIBS ${OpenCV_LIBS})
endif()
if(OPENVINO_LIBRARY)
    list(APPEND LIBLIDAR_LINK_LIBS ${OPENVINO_LIBRARY})
endif()
if(OPENCL_LIBRARY)
    list(APPEND LIBLIDAR_LINK_LIBS ${OPENCL_LIBRARY})
endif()
if(Boost_FOUND)
    list(APPEND LIBLIDAR_LINK_LIBS ${Boost_LIBRARIES})
endif()
list(APPEND LIBLIDAR_LINK_LIBS dl)

# Compiler definitions
set(LIBLIDAR_COMPILE_DEFS
    CL_TARGET_OPENCL_VERSION=220
    OV_THREAD=OV_THREAD_TBB
    _GLIBCXX_USE_CXX11_ABI=1
)

# Compiler flags
set(LIBLIDAR_COMPILE_FLAGS -fPIC)
if(USE_SYCL)
    list(APPEND LIBLIDAR_COMPILE_FLAGS -fsycl)
endif()
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    list(APPEND LIBLIDAR_COMPILE_FLAGS -g)
else()
    list(APPEND LIBLIDAR_COMPILE_FLAGS -O3)
endif()
# Source files for the main library
set(LIBLIDAR_SOURCES
    src/anchorgrid.cpp
    src/devicemanager.cpp
    src/nms.cpp
    src/pointpillars.cpp
    src/postprocess.cpp
    src/preprocess.cpp
    src/scan.cpp
    src/scatter.cpp
)

# Header files
set(LIBLIDAR_PUBLIC_HEADERS
    src/liblidar.hpp
)

set(LIBLIDAR_PRIVATE_HEADERS
    src/anchorgrid.hpp
    src/common.hpp
    src/nms.hpp
    src/postprocess.hpp
    src/preprocess.hpp
    src/scan.hpp
    src/scatter.hpp
)

# Create the main shared library
add_library(liblidar SHARED ${LIBLIDAR_SOURCES} ${LIBLIDAR_PUBLIC_HEADERS} ${LIBLIDAR_PRIVATE_HEADERS})

# Set library properties
set_target_properties(liblidar PROPERTIES
    OUTPUT_NAME "lidar"
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    POSITION_INDEPENDENT_CODE ON
)

# Include directories
target_include_directories(liblidar
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${LIBLIDAR_INCLUDE_DIRS}
)

# Compiler definitions
target_compile_definitions(liblidar PRIVATE ${LIBLIDAR_COMPILE_DEFS})

# Compiler flags
target_compile_options(liblidar PRIVATE ${LIBLIDAR_COMPILE_FLAGS})

# Link libraries
target_link_libraries(liblidar PRIVATE ${LIBLIDAR_LINK_LIBS})

# Link directories
target_link_directories(liblidar PRIVATE ${OPENVINO_ROOT}/runtime/lib/intel64)
if(COMPILER_LIB_DIR AND EXISTS "${COMPILER_LIB_DIR}")
    target_link_directories(liblidar PRIVATE ${COMPILER_LIB_DIR})
endif()

set_target_properties(liblidar PROPERTIES
    INSTALL_RPATH "${OPENVINO_ROOT}/runtime/lib/intel64;${OPENVINO_ROOT}/runtime/3rdparty/tbb/lib"
    BUILD_RPATH "${OPENVINO_ROOT}/runtime/lib/intel64;${OPENVINO_ROOT}/runtime/3rdparty/tbb/lib"
    INSTALL_RPATH_USE_LINK_PATH FALSE
)

# SYCL link flags
if(USE_SYCL)
    target_link_options(liblidar PRIVATE -fsycl)
endif()

# Build example programs if requested
if(BUILD_EXAMPLES)
    # Helper function to create examples
    function(add_example_target target_name source_file)
        add_executable(${target_name} ${source_file})
        
        # Include directories (use the same as library)
        target_include_directories(${target_name} PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/src
            ${LIBLIDAR_INCLUDE_DIRS}
        )
        
        # Compiler definitions (use the same as library)
        target_compile_definitions(${target_name} PRIVATE ${LIBLIDAR_COMPILE_DEFS})
        
        # Compiler flags (use the same as library)
        target_compile_options(${target_name} PRIVATE ${LIBLIDAR_COMPILE_FLAGS})
        
        # Link with the shared library and required dependencies
        target_link_libraries(${target_name} PRIVATE 
            liblidar
            ${LIBLIDAR_LINK_LIBS}
        )
        
        # Link directories
        if(COMPILER_LIB_DIR AND EXISTS "${COMPILER_LIB_DIR}")
            target_link_directories(${target_name} PRIVATE ${COMPILER_LIB_DIR})
        endif()
        
        # SYCL link flags
        if(USE_SYCL)
            target_link_options(${target_name} PRIVATE -fsycl)
        endif()
    endfunction()
    
    # Create example targets
    add_example_target(bench bench.cpp)
    add_example_target(demo demo.cpp)
    
    message(STATUS "Examples will be built: bench, demo")
else()
    message(STATUS "Examples will not be built (BUILD_EXAMPLES=OFF)")
endif()

# Print configuration summary
message(STATUS "liblidar Configuration Summary:")
message(STATUS "  Version: ${PROJECT_VERSION}")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  Shared libs: ${BUILD_SHARED_LIBS}")
message(STATUS "  Build examples: ${BUILD_EXAMPLES}")
message(STATUS "  C++ compiler: ${CMAKE_CXX_COMPILER}")
message(STATUS "  OpenVINO include: ${OPENVINO_INCLUDE_DIR}")
message(STATUS "  OpenVINO library: ${OPENVINO_LIBRARY}")
message(STATUS "  OpenCV version: ${OpenCV_VERSION}")
message(STATUS "  OpenCL include: ${OPENCL_INCLUDE_DIR}")
message(STATUS "  OpenCL library: ${OPENCL_LIBRARY}")
