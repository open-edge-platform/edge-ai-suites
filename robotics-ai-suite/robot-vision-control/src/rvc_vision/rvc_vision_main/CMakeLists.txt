# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
cmake_minimum_required(VERSION 3.8)
project(rvc_vision_main)


find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch 
	DESTINATION share/${PROJECT_NAME})

ament_package()
