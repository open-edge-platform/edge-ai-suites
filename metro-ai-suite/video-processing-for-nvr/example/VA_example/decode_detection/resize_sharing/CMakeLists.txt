cmake_minimum_required(VERSION 3.12)
project(dec_det_sharing)

# 1. 设置 C++ 标准 (解决枚举转换报错的关键：有些编译器标准下检查更严)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(TARGET "dec_det_sharing")
set(SOURCES "dec_det_sharing.cpp")

# 2. 抑制 OpenCL 的警告消息
add_definitions(-DCL_HPP_TARGET_OPENCL_VERSION=200)
add_definitions(-DCL_HPP_MINIMUM_OPENCL_VERSION=200)

# 3. 查找依赖包
find_package(VPPSDK REQUIRED)
find_package(OpenCL REQUIRED)
find_package(OpenVINO REQUIRED COMPONENTS Runtime)
find_package(OpenCV REQUIRED)

# 4. 创建可执行程序
add_executable(${TARGET} ${SOURCES})

# 5. 头文件包含
target_include_directories(${TARGET} PRIVATE
    ${VPPSDK_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
    ${OpenCL_INCLUDE_DIRS}
    "/opt/intel/media/include"  # 保持对硬件解码头文件的引用
)

# 6. 链接库
target_link_libraries(${TARGET}
    ${VPPSDK_LIBRARIES}
    openvino::runtime
    ${OpenCL_LIBRARIES}
    ${OpenCV_LIBS}
)

# 7. 库搜索路径
target_link_directories(${TARGET} PRIVATE
    ${VPPSDK_LIB_DIR}
)

# 打印信息用于调试
message(STATUS "VPPSDK Include Dirs: ${VPPSDK_INCLUDE_DIRS}")
message(STATUS "OpenCV Libs: ${OpenCV_LIBS}")