cmake_minimum_required(VERSION 3.12)
project(vpp_va_example)

set(TARGET "va_surface_map_npu")
set(SOURCES "va_surface_map_npu.cpp")

find_package(VPPSDK REQUIRED)
find_package(OpenCL)
find_package(OpenVINO COMPONENTS Runtime)
find_package(OpenCV REQUIRED)

add_executable(${TARGET} ${SOURCES})
target_include_directories(${TARGET} PRIVATE
    ${VPPSDK_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS})

target_link_libraries(${TARGET}
    ${VPPSDK_LIBRARIES}
    openvino::runtime
    ${OpenCL_LIBRARY}
    ${OpenCV_LIBS})

target_link_directories(${TARGET} PRIVATE
    ${VPPSDK_LIB_DIR})