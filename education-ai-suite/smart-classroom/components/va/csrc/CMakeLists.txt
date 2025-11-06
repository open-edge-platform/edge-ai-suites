cmake_minimum_required(VERSION 3.24)
project(GvaSmartClassroom VERSION 1.0.0)

include(FetchContent)

# Fetch DLStreamer as an archive
FetchContent_Declare(dlstreamer_headers
    URL "https://github.com/open-edge-platform/edge-ai-libraries/archive/refs/tags/2025.2-20251007.zip"
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_GetProperties(dlstreamer_headers)
if(NOT dlstreamer_headers_POPULATED)
    message(STATUS "Downloading DLStreamer headers...")
    FetchContent_Populate(dlstreamer_headers)
    set(DLSTREAMER_ROOT "${dlstreamer_headers_SOURCE_DIR}/libraries/dl-streamer")
    set(DLSTREAMER_INCLUDE_DIRS 
        "${DLSTREAMER_ROOT}/include"
    )
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

if(WIN32)
    # Use local GStreamer installation
    if(DEFINED GSTREAMER_BASE)
        set(GSTREAMER_BASE_DIR ${GSTREAMER_BASE})
    else()
        set(GSTREAMER_BASE_DIR "C:/gstreamer/1.0/msvc_x86_64")
    endif()
    
    # Check if GStreamer exists at the specified location
    if(NOT EXISTS "${GSTREAMER_BASE_DIR}")
        message(FATAL_ERROR "GStreamer not found at ${GSTREAMER_BASE_DIR}")
    endif()
    
    # Set up GStreamer paths
    set(GSTREAMER_INCLUDE_DIRS 
        "${GSTREAMER_BASE_DIR}/include/gstreamer-1.0"
        "${GSTREAMER_BASE_DIR}/include/glib-2.0"
        "${GSTREAMER_BASE_DIR}/lib/glib-2.0/include"
    )
    set(GSTREAMER_LIBRARY_DIRS "${GSTREAMER_BASE_DIR}/lib")
    set(GSTREAMER_LIBRARIES 
        "${GSTREAMER_BASE_DIR}/lib/gstreamer-1.0.lib"
        "${GSTREAMER_BASE_DIR}/lib/gstbase-1.0.lib" 
        "${GSTREAMER_BASE_DIR}/lib/gstvideo-1.0.lib"
        "${GSTREAMER_BASE_DIR}/lib/gstanalytics-1.0.lib"
        "${GSTREAMER_BASE_DIR}/lib/glib-2.0.lib"
        "${GSTREAMER_BASE_DIR}/lib/gobject-2.0.lib"
    )
    
else()
    if(PKG_CONFIG_FOUND)
        pkg_check_modules(GSTREAMER REQUIRED gstreamer-1.0>=1.14)
        pkg_check_modules(GSTREAMER_BASE REQUIRED gstreamer-base-1.0>=1.14)
        pkg_check_modules(GSTREAMER_VIDEO REQUIRED gstreamer-video-1.0>=1.14)
    else()
        message(FATAL_ERROR "pkg-config not found")
    endif()
endif()

# Include directories
if(WIN32)
    include_directories(${GSTREAMER_INCLUDE_DIRS})
else()
    include_directories(${GSTREAMER_INCLUDE_DIRS})
    include_directories(${GSTREAMER_BASE_INCLUDE_DIRS})
    include_directories(${GSTREAMER_VIDEO_INCLUDE_DIRS})
endif()

include_directories(${DLSTREAMER_INCLUDE_DIRS})
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
)

# Link libraries
if(WIN32)
    target_link_libraries(gvasmartclassroom
        ${GSTREAMER_LIBRARIES}
        ${OpenCV_LIBS}
    )
else()
    target_link_libraries(gvasmartclassroom
        ${GSTREAMER_LIBRARIES}
        ${GSTREAMER_BASE_LIBRARIES}
        ${GSTREAMER_VIDEO_LIBRARIES}
        ${OpenCV_LIBS}
    )
endif()

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

# Show build instructions
message(STATUS "Build instructions:")
if(WIN32)
    message(STATUS "  cmake --build build --config Release")
else()
    message(STATUS "  mkdir build && cd build")
    message(STATUS "  cmake ..")
    message(STATUS "  make")
endif()
message(STATUS "")

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
if(WIN32)
    message(STATUS "GStreamer base: ${GSTREAMER_BASE_DIR}")
else()
    message(STATUS "GStreamer version: ${GSTREAMER_VERSION}")
endif()
message(STATUS "GStreamer include dirs: ${GSTREAMER_INCLUDE_DIRS}")
message(STATUS "GStreamer libraries: ${GSTREAMER_LIBRARIES}")

