# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)
# Test dynamic parameters
ament_add_gtest(test_dynamic_parameters
  test_dynamic_parameters.cpp
)

# Test PRM
ament_add_gtest(test_prm
  test_prm.cpp
)

# Test ITS
ament_add_gtest(test_its
  test_its.cpp
)

ament_target_dependencies(test_dynamic_parameters
  ${dependencies}
)
ament_target_dependencies(test_prm
  ${dependencies}
)
ament_target_dependencies(test_its
  ${dependencies}
)

target_link_libraries(test_dynamic_parameters
  ${library_name}
)
target_link_libraries(test_prm
  ${library_name}
)
target_link_libraries(test_its
  ${library_name}
)