cmake_minimum_required(VERSION 3.5.1)

option(WITH_RTSP "support for RTSP pull libray" ON)

project(BitstreamReaderLib)
#set (CMAKE_CXX_STANDARD 11)
#set (CMAKE_BUILD_TYPE "Debug")

set(SRC_FILES ./src/bitstream_reader.cpp
	      ./src/bitstream_file_reader.cpp)

set(INC_DIRS ./include)
set(LIBS pthread)

if(WITH_RTSP)

set(SRC_FILES ${SRC_FILES}
	      ./src/bitstream_rtsp_reader.cpp
              ./src/buffer_sink.cpp
	      ./src/rtsp_client_deamon.cpp)

set(INC_DIRS ${INC_DIRS}
	     /usr/local/include/UsageEnvironment
	     /usr/local/include/groupsock
	     /usr/local/include/liveMedia
	     /usr/local/include/BasicUsageEnvironment
	     /usr/local/include
	     ../thirdparty/spdlog/include
	     )

set(LIBS     ${LIBS}
             /usr/local/lib/libliveMedia.so
	     /usr/local/lib/libgroupsock.so
	     /usr/local/lib/libBasicUsageEnvironment.so
	     /usr/local/lib/libUsageEnvironment.so
	     /usr/local/lib/libEpollTaskScheduler.so
	     ssl crypto)

endif(WITH_RTSP)

add_library(BitstreamReader STATIC ${SRC_FILES})
target_include_directories(BitstreamReader PUBLIC ${INC_DIRS})
target_link_libraries(BitstreamReader PUBLIC -L. ${LIBS})

