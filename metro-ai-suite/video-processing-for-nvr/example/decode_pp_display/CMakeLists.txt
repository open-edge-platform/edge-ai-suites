cmake_minimum_required(VERSION 3.12)
project(vpp_example)

set(TARGET "decode_pp_display")
set(SOURCES "decode_pp_display.cpp")

add_executable(${TARGET} ${SOURCES})

find_package(VPPSDK REQUIRED)

target_include_directories(${TARGET} PRIVATE
    ${VPPSDK_INCLUDE_DIRS})

target_link_libraries(${TARGET}
    ${VPPSDK_LIBRARIES})

target_link_directories(${TARGET} PRIVATE
    ${VPPSDK_LIB_DIR})