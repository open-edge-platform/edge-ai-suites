cmake_minimum_required(VERSION 3.13)
project(vpp_example)

set (CMAKE_CXX_STANDARD 14)

# ----Open Sanitizer ----
option(ENABLE_SANITIZERS "Enable ASan/UBSan" OFF)

if(ENABLE_SANITIZERS)
    message(STATUS "Sanitizers enabled: AddressSanitizer + UndefinedBehaviorSanitizer")

    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -g3 -O0 -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize-recover=all")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g3 -O0 -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize-recover=all -Wall -Wextra -Wpedantic -Werror=return-type")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fsanitize=address,undefined -fno-sanitize-recover=all")
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -fsanitize=address,undefined -fno-sanitize-recover=all")
else()
    # 不开 sanitizer 时，也建议至少保留 return-type 检查
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic -Werror=return-type")
endif()

set(TARGET "decode_encode")
set(SOURCES "decode_encode.cpp")

# 搜索vppsdk
find_package(VPPSDK REQUIRED)
message(STATUS "VPPSDK_LIBRARIES=${VPPSDK_LIBRARIES}")
message(STATUS "VPPSDK_LIB_DIR=${VPPSDK_LIB_DIR}")
message(STATUS "VPPSDK_INCLUDE_DIRS=${VPPSDK_INCLUDE_DIRS}")

# 把 vppsdk 解析成“真实库文件全路径”，不要依赖 -L/-l
find_library(VPPSDK_LIB_FULL
NAMES vppsdk libvppsdk.so libvppsdk.a libvppsdk.so.1
PATHS ${VPPSDK_LIB_DIR} ${VPPSDK_LIB_DIR}/../lib64
NO_DEFAULT_PATH
)
if(NOT VPPSDK_LIB_FULL)
message(FATAL_ERROR
"Cannot find vppsdk library in ${VPPSDK_LIB_DIR}. "
"Please check /opt/intel/vppsdk/lib or lib64 contains libvppsdk.so/libvppsdk.a"
)
endif()
message(STATUS "VPPSDK_LIB_FULL=${VPPSDK_LIB_FULL}")

add_subdirectory(rtsp)

add_executable(${TARGET} ${SOURCES})

target_include_directories(${TARGET} PRIVATE
 ${VPPSDK_INCLUDE_DIRS}
)

target_link_libraries(${TARGET}
 PRIVATE
 rtsp # 链接 rtsp 库，从而继承 include 路径
 ${VPPSDK_LIB_FULL}
)

# 避免运行时还要手工 export LD_LIBRARY_PATH（如果是 so）
set_target_properties(${TARGET} PROPERTIES
 BUILD_RPATH "${VPPSDK_LIB_DIR}"
 INSTALL_RPATH "${VPPSDK_LIB_DIR}"
)
