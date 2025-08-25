#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import os.path
import sysconfig

import numpy as np
from setuptools import Extension, setup


setup (
    name="yolov8 processor",
    author="eci.maintainer@intel.com <ECI Maintainer>",
    version="1.0.1",
    install_requires=[
        'ultralytics==8.0.43',
    ],
    packages=['pyrealsense2_ai_demo'],
    scripts=['pyrealsense2_ai_demo_launcher.py'],
    description="Intel Realsense2 python demo w/ Openvino Extension for yolov8",
    license="Apache 2.0",
	ext_modules = 	[
		Extension(

			name = "yolov8_model", 
			sources = [
					'yolov8_model.pyx'
				], 
			include_dirs = [ 
					".", 
					np.get_include()
				],
			
            extra_compile_args = [
	                "-Wall",
	                "-Wextra",
	                "-O3"
	            ],
			extra_link_args = [
					"-fPIC", "-Wno-unused-command-line-argument"
					],
			language="c++"

        )
	]
)



