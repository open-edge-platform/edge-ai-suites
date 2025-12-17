cmake_minimum_required(VERSION 3.12)
project(vpp_va_example_264)

set(TARGET "va_surface_sharing_264")
set(SOURCES "va_surface_sharing_264.cpp")

find_package(VPPSDK REQUIRED)
find_package(OpenCL)
find_package(OpenVINO COMPONENTS Runtime)
find_package(OpenCV REQUIRED)

add_executable(${TARGET} ${SOURCES})
target_include_directories(${TARGET} PRIVATE
    ${VPPSDK_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
    "/opt/intel/media/include")
message(${VPPSDK_INCLUDE_DIRS})
target_link_libraries(${TARGET}
    ${VPPSDK_LIBRARIES}
    openvino::runtime
    ${OpenCL_LIBRARY}
    ${OpenCV_LIBS})

target_link_directories(${TARGET} PRIVATE
    ${VPPSDK_LIB_DIR})




cmake_minimum_required(VERSION 3.12)
project(vpp_va_example_265)

set(TARGET "va_surface_sharing_265")
set(SOURCES "va_surface_sharing_265.cpp")

find_package(VPPSDK REQUIRED)
find_package(OpenCL)
find_package(OpenVINO COMPONENTS Runtime)
find_package(OpenCV REQUIRED)

add_executable(${TARGET} ${SOURCES})
target_include_directories(${TARGET} PRIVATE
${VPPSDK_INCLUDE_DIRS}
${OpenCV_INCLUDE_DIRS}
"/opt/intel/media/include")
message(${VPPSDK_INCLUDE_DIRS})
target_link_libraries(${TARGET}
${VPPSDK_LIBRARIES}
openvino::runtime
${OpenCL_LIBRARY}
${OpenCV_LIBS})

target_link_directories(${TARGET} PRIVATE
${VPPSDK_LIB_DIR})

