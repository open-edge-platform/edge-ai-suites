cmake_minimum_required(VERSION 3.5)

project(adbscan_ros2)

option(WITH_ONEAPI "Build with parallelization using Intel OneAPI" FALSE)
    
# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++17
set(CMAKE_CXX_STANDARD 17)

if("$ENV{ROS_DISTRO}" STRLESS "humble")
    add_compile_definitions(PRE_ROS_HUMBLE)
endif()

if(WITH_ONEAPI)
    add_compile_definitions(USE_ONEAPI)
endif()

# Flags
if(UNIX OR APPLE)
  # Linker flags.
  if(${CMAKE_CXX_COMPILER_ID} STREQUAL "GNU" OR ${CMAKE_CXX_COMPILER_ID} STREQUAL "Intel")
    # GCC specific flags. ICC is compatible with them.
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -z noexecstack -z relro -z now")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -z noexecstack -z relro -z now")
  elseif(${CMAKE_CXX_COMPILER_ID} STREQUAL "Clang")
    # In Clang, -z flags are not compatible, they need to be passed to linker via -Wl.
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} \
      -Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} \
      -Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now")
    # flag to enable NaN/INFINITY support in oneAPI
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fhonor-nans")
  endif()
  
  # Compiler flags.
  if(${CMAKE_CXX_COMPILER_ID} STREQUAL "GNU")
    # GCC specific flags.
    if(CMAKE_CXX_COMPILER_VERSION VERSION_GREATER 4.9 OR
	CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL 4.9)
      set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIE -fstack-protector-strong")
    else()
      set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIE -fstack-protector")
    endif()
  elseif(${CMAKE_CXX_COMPILER_ID} STREQUAL "Clang")
    # Clang is compatbile with some of the flags.
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIE -fstack-protector")
  elseif(${CMAKE_CXX_COMPILER_ID} STREQUAL "Intel")
    # Same as above, with exception that ICC compilation crashes with -fPIE option, even
    # though it uses -pie linker option that require -fPIE during compilation. Checksec
    # shows that it generates correct PIE anyway if only -pie is provided.
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fstack-protector")
  endif()
  
  # Generic flags.
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC -fno-operator-names -Wformat -Wformat-security \
    -Wall -fopenmp")
  set( CUDA_PROPAGATE_HOST_FLAGS OFF )
  set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -D_FORTIFY_SOURCE=2")
  set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -pie")
endif()

# Enable oneapi KDTree only when oneapi tool kit is present
if(WITH_ONEAPI)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DUSE_ONEAPI_KDTREE=1 -fsycl -fsycl-unnamed-lambda")
  set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -lsycl")
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  if(NOT FUZZTEST_FUZZING_MODE)
    add_compile_options(-Wall -Wextra -fstack-protector-all -Wno-deprecated-declarations -Wformat-overflow=1)
  endif()
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(nav2_dynamic_msgs REQUIRED)
find_package(pcl_conversions REQUIRED)
if(WITH_ONEAPI)
    find_package(PCL REQUIRED COMPONENTS common io kdtree octree oneapi_kdtree oneapi_octree)
else()
    find_package(PCL REQUIRED COMPONENTS common io)
endif()

include_directories(include)
ament_export_include_directories(include)

set(HEADER_FILES src/ADBScan.h src/dbscan_adaptiveK.h src/doDBSCAN.hpp src/print_info.h src/Util.hpp)
add_library(adbscan_lib src/dbscan_adaptiveK.cpp src/doDBSCAN.cpp src/print_info.cpp src/Util.cpp ${HEADER_FILES})

if(WITH_ONEAPI)
target_link_libraries (adbscan_lib pcl_oneapi_kdtree pcl_kdtree  pcl_oneapi_octree pcl_octree pcl_io)
endif()

set(dependencies "geometry_msgs" "rclcpp" "nav2_dynamic_msgs" "PCL" "pcl_conversions" "sensor_msgs" "visualization_msgs")
add_executable(adbscan_pub src/adbscan_pub.cpp)
ament_target_dependencies(adbscan_pub ${dependencies})

include_directories(${PCL_INCLUDE_DIRS})
link_directories(${PCL_LIBRARY_DIRS})
add_definitions(${PCL_DEFINITIONS})

add_executable(adbscan_sub src/adbscan_sub.cpp src/print_info.cpp src/Util.cpp src/doDBSCAN.cpp src/Util.cpp src/dbscan_adaptiveK.cpp)
ament_target_dependencies(adbscan_sub ${dependencies})  
target_link_libraries (adbscan_sub ${PCL_LIBRARIES})


if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  set(TESTFILES
    test/main.cpp
    test/test_adbscan_clusters.cpp)
  ament_add_gtest(${PROJECT_NAME}_test ${TESTFILES})
  target_link_libraries(${PROJECT_NAME}_test adbscan_lib)

  install(TARGETS
    ${PROJECT_NAME}_test
    DESTINATION lib/${PROJECT_NAME})
endif()

if(FUZZTEST_FUZZING_MODE)
  # Fuzztest requires Clang
  if(NOT CXX MATCHES "clang")
    message(FATAL_ERROR "Please set the CXX option to your Clang installation (e.g. -DCXX=clang++)")
  endif()

  # Use a symlink from the compiled frameworks.industrial.edge-controls.actions.fuzzer version
  add_subdirectory(/fuzztest fuzztest)
  enable_testing()
  include(GoogleTest)

  # Enable fuzzing mode
  fuzztest_setup_fuzzing_flags()

  # Enable sanitizers: https://llvm.org/docs/LibFuzzer.html#fuzzer-usage
  #  - Note: memory and address cannot be used at the same time!
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fprofile-instr-generate -fcoverage-mapping -fsanitize=address,signed-integer-overflow -g")
  set(HEADERS src/ADBScan.h src/dbscan_adaptiveK.h src/doDBSCAN.hpp src/print_info.h src/Util.hpp)
  add_library(adbscan_fuzztest_lib src/dbscan_adaptiveK.cpp src/doDBSCAN.cpp src/print_info.cpp src/Util.cpp ${HEADERS})
  add_executable(
     fuzz_clusters
     test/fuzzing/fuzz_clusters.cpp
  )
  target_link_libraries(
    fuzz_clusters 
    PRIVATE 
    adbscan_fuzztest_lib
  )
  link_fuzztest(fuzz_clusters)
endif()

install(TARGETS
  adbscan_pub
  adbscan_sub
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()
