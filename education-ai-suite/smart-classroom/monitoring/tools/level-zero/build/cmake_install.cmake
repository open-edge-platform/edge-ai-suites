# Install script for directory: C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "C:/Program Files (x86)/level-zero")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/build/source/cmake_install.cmake")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/build/samples/cmake_install.cmake")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "level-zero-devel" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "C:/Program Files (x86)/level-zero/include/level_zero/ze_api.h;C:/Program Files (x86)/level-zero/include/level_zero/ze_ddi.h;C:/Program Files (x86)/level-zero/include/level_zero/zes_api.h;C:/Program Files (x86)/level-zero/include/level_zero/zes_ddi.h;C:/Program Files (x86)/level-zero/include/level_zero/zet_api.h;C:/Program Files (x86)/level-zero/include/level_zero/zet_ddi.h")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  file(INSTALL DESTINATION "C:/Program Files (x86)/level-zero/include/level_zero" TYPE FILE FILES
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/ze_api.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/ze_ddi.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/zes_api.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/zes_ddi.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/zet_api.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/zet_ddi.h"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "level-zero-devel" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "C:/Program Files (x86)/level-zero/include/level_zero/layers/zel_tracing_api.h;C:/Program Files (x86)/level-zero/include/level_zero/layers/zel_tracing_ddi.h;C:/Program Files (x86)/level-zero/include/level_zero/layers/zel_tracing_register_cb.h")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  file(INSTALL DESTINATION "C:/Program Files (x86)/level-zero/include/level_zero/layers" TYPE FILE FILES
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/layers/zel_tracing_api.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/layers/zel_tracing_ddi.h"
    "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/layers/zel_tracing_register_cb.h"
    )
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "level-zero-devel" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "C:/Program Files (x86)/level-zero/include/level_zero/loader/ze_loader.h")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  file(INSTALL DESTINATION "C:/Program Files (x86)/level-zero/include/level_zero/loader" TYPE FILE FILES "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/include/loader/ze_loader.h")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "Unspecified" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include" TYPE DIRECTORY FILES "C:/Program Files (x86)/level-zero/include/")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/build/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
if(CMAKE_INSTALL_COMPONENT)
  if(CMAKE_INSTALL_COMPONENT MATCHES "^[a-zA-Z0-9_.+-]+$")
    set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
  else()
    string(MD5 CMAKE_INST_COMP_HASH "${CMAKE_INSTALL_COMPONENT}")
    set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INST_COMP_HASH}.txt")
    unset(CMAKE_INST_COMP_HASH)
  endif()
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "C:/Users/intel/Desktop/education/education-ai-suite/smart-classroom/monitoring/tools/level-zero/build/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
