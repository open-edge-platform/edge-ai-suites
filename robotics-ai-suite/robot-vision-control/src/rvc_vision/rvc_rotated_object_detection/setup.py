# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import os
from glob import glob
from setuptools import find_packages, setup
from generate_parameter_library_py.setup_helper import generate_parameter_module

generate_parameter_module(
  "rotated_object_detection_parameters", # python module name for parameter library
  "rvc_rotated_object_detection/detection_parameters.yaml", # path to input yaml file
)

package_name = 'rvc_rotated_object_detection'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*')),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'resources'), glob('resources/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ros',
    maintainer_email='robotics@intel.com',
    description='Rotated object detection using ORB features',
    license='Proprietary',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
                'object_detection = rvc_rotated_object_detection.object_detection:main',
        ],
    },
)
