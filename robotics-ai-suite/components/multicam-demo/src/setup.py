#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

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



