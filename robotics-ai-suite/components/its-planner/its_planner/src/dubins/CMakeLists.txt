# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
add_library(dubins_lib SHARED
  dubins.cpp
)

install(TARGETS
  dubins_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

set(GCC_COVERAGE_COMPILE_FLAGS "-lboost_serialization")

# target_link_libraries(dubins_lib PRIVATE ${GCC_COVERAGE_COMPILE_FLAGS})
