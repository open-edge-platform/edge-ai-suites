#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext


class build_ext(_build_ext):
    def run(self):
        import numpy as np
        for ext in self.extensions:
            ext.include_dirs.append(np.get_include())
        super().run()


setup(
    name="yolov8-processor",
    scripts=['pyrealsense2_ai_demo_launcher.py'],
    cmdclass={'build_ext': build_ext},
    ext_modules=[
        Extension(
            name="yolov8_model",
            sources=['yolov8_model.pyx'],
            include_dirs=["."],
            extra_compile_args=["-Wall", "-Wextra", "-O3"],
            extra_link_args=["-fPIC", "-Wno-unused-command-line-argument"],
            language="c++"
        )
    ]
)



