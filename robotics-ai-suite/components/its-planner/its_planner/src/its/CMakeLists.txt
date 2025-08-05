# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
add_library(its_lib SHARED
  its.cpp
)

install(TARGETS
  its_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

set(GCC_COVERAGE_COMPILE_FLAGS "-lboost_serialization")

target_link_libraries(its_lib PRIVATE ${GCC_COVERAGE_COMPILE_FLAGS})