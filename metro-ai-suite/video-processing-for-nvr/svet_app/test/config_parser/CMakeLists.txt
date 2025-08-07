cmake_minimum_required(VERSION 3.5.1)

project(ConfigParserTest)

set(INC_DIRS 	../../include
	        ../../thirdparty/spdlog/include)
#set(LIBS pthread)

add_executable(ConfigParserTest ../../src/config_parser.cpp  ./test_config_parser.cpp)
target_include_directories(ConfigParserTest PRIVATE  ${INC_DIRS})
#target_link_libraries(BitstreamFileReaderTest  PRIVATE BitstreamReader ${LIBS})


