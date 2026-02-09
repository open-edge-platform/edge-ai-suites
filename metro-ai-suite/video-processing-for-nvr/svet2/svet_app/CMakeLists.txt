cmake_minimum_required(VERSION 3.5.1)

project(CLI_Test)
set (CMAKE_CXX_STANDARD 14)
set(CMAKE_BUILD_TYPE "Debug")

add_subdirectory(rtsp)
add_subdirectory(test)
add_subdirectory(tool)

#add_executable(test_config_parser ./test/test_config_parser.cpp ./src/config_parser.cpp)
#target_include_directories(test_config_parser 
#	                    PRIVATE
#                            thirdparty/spdlog/include
#                            ./include)
file(GLOB SVET_APP_SOURCE
		./src/*.cpp
		)

set(SVET_COMPILER_FLAGS "-Wformat -Wformat-security -Werror=format-security -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fno-strict-overflow -fwrapv -fno-delete-null-pointer-checks -fPIE -fPIC")
set(SVET_SHARED_LINKER_FLAGS "-z relro -z now -z noexecstack")
set(CMAKE_CXX_FLAGS  "${CMAKE_CXX_FLAGS} ${SVET_COMPILER_FLAGS}")
set(CMAKE_C_FLAGS  "${CMAKE_C_FLAGS} ${SVET_COMPILER_FLAGS}")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${SVET_SHARED_LINKER_FLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${SVET_SHARED_LINKER_FLAGS}")

set(VPP_LIBRARY_PATH /opt/intel/vppsdk/lib)
link_directories( ${VPP_LIBRARY_PATH} )

add_compile_definitions(VPPSDK_PP)
add_compile_definitions(VPPSDK_DEC)
add_compile_definitions(VPPSDK_DISP)
add_compile_definitions(VPPSDK_OSD)

add_executable(svet_app ${SVET_APP_SOURCE})

add_compile_definitions(RTSP_ENABLE)

target_include_directories(svet_app
		PRIVATE
                thirdparty/spdlog/include
                ./rtsp/include
                /opt/intel/vppsdk/include 
		./include)


target_link_libraries(svet_app PRIVATE BitstreamReader vppsdk ${LIBS})
