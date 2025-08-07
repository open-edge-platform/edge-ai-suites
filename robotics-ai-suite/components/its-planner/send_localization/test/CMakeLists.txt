# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.5)

# Test send localization
ament_add_gtest(test_send_localization
  test_send_localization.cpp
)

ament_target_dependencies(test_send_localization
  ${dependencies}
)

target_link_libraries(test_send_localization
${library_name}
)