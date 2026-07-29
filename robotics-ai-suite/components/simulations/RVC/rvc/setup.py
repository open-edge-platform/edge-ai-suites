# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Intel Corporation
from setuptools import setup

package_name = "rvc"

setup(
    name=package_name,
    version="1.0.0",
    packages=[package_name],
    py_modules=[],
    package_dir={"": "scripts"},
    install_requires=["setuptools"],
    zip_safe=True,
    author="ECI Maintainer",
    author_email="eci.maintainer@intel.com",
    maintainer="ECI Maintainer",
    maintainer_email="eci.maintainer@intel.com",
    keywords=["ROS2"],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Topic :: Software Development",
    ],
    description="RVC single-arm two-conveyor pick-and-place demo.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "cube_controller = scripts.cube_controller:main",
            "arm1_controller = scripts.arm1_controller:main",
        ],
    },
)
