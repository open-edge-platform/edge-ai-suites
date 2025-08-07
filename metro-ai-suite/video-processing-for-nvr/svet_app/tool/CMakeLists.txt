cmake_minimum_required(VERSION 3.5.1)

project(ConfigGen)
set (CMAKE_CXX_STANDARD 14)
set(CMAKE_BUILD_TYPE "Debug")

set(INC_DIRS 	../include
	        ../thirdparty/spdlog/include)

set(LIBS pthread)

add_executable(ConfigGen config_gen.cpp)
target_include_directories(ConfigGen PRIVATE  ${INC_DIRS})
target_link_libraries(ConfigGen  PRIVATE ${LIBS})


