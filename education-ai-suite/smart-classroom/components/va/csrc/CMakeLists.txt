cmake_minimum_required(VERSION 3.24)
project(GvaSmartClassroom VERSION 1.0.0)

include(FetchContent)

# Fetch DLStreamer as an archive
cmake_policy(SET CMP0169 OLD)
FetchContent_Declare(dlstreamer_headers
    URL "https://github.com/open-edge-platform/dlstreamer/archive/refs/tags/v2026.0.0.zip"
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_GetProperties(dlstreamer_headers)
if(NOT dlstreamer_headers_POPULATED)
    FetchContent_Populate(dlstreamer_headers)
    set(DLSTREAMER_ROOT "${dlstreamer_headers_SOURCE_DIR}")
    set(DLSTREAMER_INCLUDE_DIRS "${DLSTREAMER_ROOT}/include")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

if(WIN32)
    add_definitions(-DNOMINMAX)
    add_definitions(-DWIN32_LEAN_AND_MEAN)
    add_definitions(-D_USE_STD_VECTOR_ALGORITHMS=0)
endif()

# Find required packages
find_package(PkgConfig)
find_package(OpenCV REQUIRED)

pkg_check_modules(GSTREAMER REQUIRED gstreamer-1.0>=1.14)
pkg_check_modules(GSTREAMER_BASE REQUIRED gstreamer-base-1.0>=1.14)
pkg_check_modules(GSTREAMER_VIDEO REQUIRED gstreamer-video-1.0>=1.14)
pkg_check_modules(GSTREAMER_ANALYTICS REQUIRED gstreamer-analytics-1.0)

# Include directories
include_directories(${GSTREAMER_INCLUDE_DIRS})
include_directories(${GSTREAMER_BASE_INCLUDE_DIRS})
include_directories(${GSTREAMER_VIDEO_INCLUDE_DIRS})
include_directories(${GSTREAMER_ANALYTICS_INCLUDE_DIRS})
include_directories(${DLSTREAMER_INCLUDE_DIRS})

# Library directories
link_directories(${GSTREAMER_LIBRARY_DIRS})
link_directories(${GSTREAMER_BASE_LIBRARY_DIRS})
link_directories(${GSTREAMER_VIDEO_LIBRARY_DIRS})
link_directories(${GSTREAMER_ANALYTICS_LIBRARY_DIRS})

message(STATUS "DLStreamer root: ${DLSTREAMER_ROOT}")

if(MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /W3 -wd4005 -wd4200 -wd4267 -wd4244 -wd4996")
    set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od")
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -fPIC")
    set(CMAKE_CXX_FLAGS_DEBUG "-g -O0")
    set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG")
endif()

add_link_options(
    $<$<NOT:$<CONFIG:DEBUG>>:/INCREMENTAL:NO> # Disable incremental linking for non-Debug builds
)

# Create library
add_library(gvasmartclassroom SHARED
    gvasmartclassroom.cpp
    gvaposturedetect.cpp
    gvaroifilter.cpp
    gvareid.cpp
    ${DLSTREAMER_ROOT}/src/gst/metadata/gstanalyticskeypointsmtd.c
    ${DLSTREAMER_ROOT}/src/gst/metadata/gva_tensor_meta.c
)

# Link libraries
target_link_libraries(gvasmartclassroom
    ${GSTREAMER_LIBRARIES}
    ${GSTREAMER_BASE_LIBRARIES}
    ${GSTREAMER_VIDEO_LIBRARIES}
    ${GSTREAMER_ANALYTICS_LIBRARIES}
    ${OpenCV_LIBS}
)

if(WIN32)
    set_target_properties(gvasmartclassroom PROPERTIES
        PREFIX ""
        SUFFIX ".dll"
        VERSION ${PROJECT_VERSION}
    )
    set_target_properties(gvasmartclassroom PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
        LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib
    )
else()
    set_target_properties(gvasmartclassroom PROPERTIES
        PREFIX ""
        SUFFIX ".so"
        VERSION ${PROJECT_VERSION}
        SOVERSION 1
    )
endif()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "GStreamer version: ${GSTREAMER_VERSION}")
message(STATUS "GStreamer include dirs: ${GSTREAMER_INCLUDE_DIRS}")
message(STATUS "GStreamer libraries: ${GSTREAMER_LIBRARIES}")
