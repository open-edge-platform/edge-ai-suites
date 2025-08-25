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

from launch_ros.actions import Node

from launch import LaunchDescription
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='rvc_rotated_object_detection',
            executable='object_detection',
            output='screen',
            parameters=[{
                'roi': {
                    'crop_top': 200,
                    'crop_bottom': 150,
                    'crop_left': 100,
                    'crop_right': 400
                },
                'orb': {
                    'min_matches': 20,
                    'matches_limit': 20,
                },
                'objects': ['robot'],
                'object': {
                    'robot': {
                        'image_path': PathJoinSubstitution([FindPackageShare('rvc_rotated_object_detection'),'resources','IntelBox128.png']),
                        'nfeatures': 100,
                        'thickness': 0.044  
                    }
                },
                'project': True,
                'projection_distance': 0.6
            }]
        )
    ])
