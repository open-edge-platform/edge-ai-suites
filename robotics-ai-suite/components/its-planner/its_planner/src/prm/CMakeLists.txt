# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
add_library(prm_lib SHARED
  prm.cpp
  ../path_utils/path_utils.cpp
)

install(TARGETS
  prm_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

set(GCC_COVERAGE_COMPILE_FLAGS "-lboost_serialization")
