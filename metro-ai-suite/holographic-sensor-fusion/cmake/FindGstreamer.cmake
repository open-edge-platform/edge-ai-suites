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

FIND_PACKAGE(PkgConfig)

# The minimum GStreamer version we support.
SET(GSTREAMER_MINIMUM_VERSION 1.7.90)

MACRO(FIND_GSTREAMER_COMPONENT _component_prefix _pkgconfig_name _header _library)
    # FIXME: The QUIET keyword can be used once we require CMake 2.8.2.
    PKG_CHECK_MODULES(PC_${_component_prefix} ${_pkgconfig_name})

    FIND_PATH(${_component_prefix}_INCLUDE_DIRS
        NAMES ${_header}
        HINTS ${PC_${_component_prefix}_INCLUDE_DIRS} ${PC_${_component_prefix}_INCLUDEDIR}
        PATH_SUFFIXES gstreamer-1.0
		)

    FIND_LIBRARY(${_component_prefix}_LIBRARIES
        NAMES ${_library}
        HINTS ${PC_${_component_prefix}_LIBRARY_DIRS} ${PC_${_component_prefix}_LIBDIR}
    )
ENDMACRO()

# ------------------------
# 1. Find GStreamer itself
# ------------------------

# 1.1. Find headers and libraries
FIND_GSTREAMER_COMPONENT(GSTREAMER gstreamer-1.0 gst/gst.h gstreamer-1.0)
#FIND_GSTREAMER_COMPONENT(GSTREAMER_GSTCONFIG gstreamer-1.0  gst/gstconfig.h gstreamer-1.0)
FIND_GSTREAMER_COMPONENT(GSTREAMER_BASE gstreamer-base-1.0 gst/gst.h gstbase-1.0)

find_path(GSTCONFIG_INCLUDE_DIR gst/gstconfig.h
    HINTS ${PC_GSTREAMER_INCLUDEDIR} ${PC_GSTREAMER_INCLUDE_DIRS})
message("PC_GSTREAMER_INCLUDE_DIRS: ${PC_GSTREAMER_INCLUDE_DIRS}")
message("PC_GSTREAMER_INCLUDEDIR: ${PC_GSTREAMER_INCLUDEDIR}")

# 1.2. Check GStreamer version
IF (GSTREAMER_INCLUDE_DIRS)
    IF (EXISTS "${GSTREAMER_INCLUDE_DIRS}/gst/gstversion.h")
        FILE (READ "${GSTREAMER_INCLUDE_DIRS}/gst/gstversion.h" GSTREAMER_VERSION_CONTENTS)

        STRING(REGEX MATCH "#define +GST_VERSION_MAJOR +\\(([0-9]+)\\)" _dummy "${GSTREAMER_VERSION_CONTENTS}")
        SET(GSTREAMER_VERSION_MAJOR "${CMAKE_MATCH_1}")

        STRING(REGEX MATCH "#define +GST_VERSION_MINOR +\\(([0-9]+)\\)" _dummy "${GSTREAMER_VERSION_CONTENTS}")
        SET(GSTREAMER_VERSION_MINOR "${CMAKE_MATCH_1}")

        STRING(REGEX MATCH "#define +GST_VERSION_MICRO +\\(([0-9]+)\\)" _dummy "${GSTREAMER_VERSION_CONTENTS}")
        SET(GSTREAMER_VERSION_MICRO "${CMAKE_MATCH_1}")

        SET(GSTREAMER_VERSION "${GSTREAMER_VERSION_MAJOR}.${GSTREAMER_VERSION_MINOR}.${GSTREAMER_VERSION_MICRO}")
    ENDIF ()
ENDIF ()

# FIXME: With CMake 2.8.3 we can just pass GSTREAMER_VERSION to FIND_PACKAGE_HANDLE_STARNDARD_ARGS as VERSION_VAR
#        and remove the version check here (GSTREAMER_MINIMUM_VERSION would be passed to FIND_PACKAGE).
SET(VERSION_OK TRUE)
IF ("${GSTREAMER_VERSION}" VERSION_LESS "${GSTREAMER_MINIMUM_VERSION}")
    SET(VERSION_OK FALSE)
ENDIF ()

# -------------------------
# 2. Find GStreamer plugins
# -------------------------

FIND_GSTREAMER_COMPONENT(GSTREAMER_APP gstreamer-app-1.0 gst/app/gstappsink.h gstapp-1.0)
#FIND_GSTREAMER_COMPONENT(GSTREAMER_AUDIO gstreamer-audio-1.0 gst/audio/audio.h gstaudio-1.0)
#FIND_GSTREAMER_COMPONENT(GSTREAMER_FFT gstreamer-fft-1.0 gst/fft/gstfft.h gstfft-1.0)
#FIND_GSTREAMER_COMPONENT(GSTREAMER_INTERFACES gstreamer-interfaces-1.0 gst/interfaces/mixer.h gstinterfaces-1.0)
#FIND_GSTREAMER_COMPONENT(GSTREAMER_PBUTILS gstreamer-pbutils-1.0 gst/pbutils/pbutils.h gstpbutils-1.0)
FIND_GSTREAMER_COMPONENT(GSTREAMER_VIDEO gstreamer-video-1.0 gst/video/video.h gstvideo-1.0)
FIND_GSTREAMER_COMPONENT(GSTREAMER_RTSPSERVER gstreamer-rtsp-1.0 gst/rtsp/rtsp.h gstrtspserver-1.0)
FIND_GSTREAMER_COMPONENT(GSTREAMER_ALLOCATORS gstreamer-allocators-1.0 gst/allocators/allocators.h gstallocators-1.0)
FIND_GSTREAMER_COMPONENT(GSTREAMER_CHECK gstreamer-check-1.0 gst/check/gstcheck.h gstcheck-1.0)

# ------------------------------------------------
# 3. Process the COMPONENTS passed to FIND_PACKAGE
# ------------------------------------------------
SET(_GSTREAMER_REQUIRED_VARS GSTREAMER_INCLUDE_DIRS GSTREAMER_LIBRARIES VERSION_OK GSTREAMER_BASE_INCLUDE_DIRS GSTREAMER_BASE_LIBRARIES )

FOREACH(_component ${GStreamer_FIND_COMPONENTS})
    SET(_gst_component "GSTREAMER_${_component}")
    STRING(TOUPPER ${_gst_component} _UPPER_NAME)

    LIST(APPEND _GSTREAMER_REQUIRED_VARS ${_UPPER_NAME}_INCLUDE_DIRS ${_UPPER_NAME}_LIBRARIES)
ENDFOREACH()

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GStreamer DEFAULT_MSG ${_GSTREAMER_REQUIRED_VARS})

set(GSTREAMER_INCLUDE_DIRS ${GSTREAMER_INCLUDE_DIRS} ${GSTCONFIG_INCLUDE_DIR})
