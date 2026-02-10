cmake_minimum_required(VERSION 3.5.1)

project(StreamReaderTest)

set(INC_DIRS ../../rtsp/include)
set(LIBS pthread)

add_executable(BitstreamFileReaderTest ./test_bitstream_file_reader.cpp)
target_include_directories(BitstreamFileReaderTest PRIVATE  ${INC_DIRS})
target_link_libraries(BitstreamFileReaderTest  PRIVATE BitstreamReader ${LIBS})

if(WITH_RTSP)
add_executable(BitstreamRTSPReaderTest ./test_bitstream_rtsp_reader.cpp)
target_include_directories(BitstreamRTSPReaderTest PRIVATE  ${INC_DIRS})
target_link_libraries(BitstreamRTSPReaderTest  PRIVATE  BitstreamReader ${LIBS})
endif(WITH_RTSP)

