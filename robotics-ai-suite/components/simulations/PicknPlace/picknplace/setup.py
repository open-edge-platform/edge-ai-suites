# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
from setuptools import setup, find_packages

package_name = 'picknplace'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    py_modules=[],
    package_dir={'': 'scripts'}
    install_requires=['setuptools'],
    zip_safe=True,
    author='ECI Maintainer',
    author_email='eci.maintainer@intel.com',
    maintainer='ECI Maintainer',
    maintainer_email='eci.maintainer@intel.com',
    keywords=['ROS2'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: TODO License declaration',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ],
    description='Examples of minimal subscribers using rclpy.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'cube_controller = scripts.cube_controller:main',
            'arm1_controller = scripts.arm1_controller:main',
            'arm2_controller = scripts.arm2_controller:main',
            'turtlebot_controller = scripts.turtlebot_controller:main',            
        ],
    },
)
