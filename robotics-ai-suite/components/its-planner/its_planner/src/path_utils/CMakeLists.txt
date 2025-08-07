# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
add_library(path_utils_lib SHARED
  path_utils.cpp
)

install(TARGETS
  path_utils_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
