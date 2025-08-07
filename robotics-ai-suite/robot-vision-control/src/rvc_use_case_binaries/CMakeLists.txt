# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(rvc_use_case_binaries)

find_package(ament_cmake REQUIRED)

#install(FILES
#  ai_model_file.bin
#  DESTINATION
#  share/${PROJECT_NAME}/ai_models
#  )

install(FILES
  pcd_objects/cube.pcd
  pcd_objects/nut.pcd
  pcd_objects/gear.pcd
  pcd_objects/bolt.pcd
  DESTINATION
  share/${PROJECT_NAME}/pcd_objects
  )

ament_package()
