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

import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    
    package_share_directory = get_package_share_directory('fast_mapping')
    bags_dir = os.path.join('/opt/ros/humble', 'share', 'bagfiles', 'spinning')
    rviz_dir = os.path.join(package_share_directory, 'launch', 'config', 'fastmapping_tutorial_config.rviz')

    # Define nodes and actions
    nodes = [
        Node(
            package='fast_mapping',
            executable='fast_mapping_node',
            output='screen',
            name='fast_mapping'
        ),
        ExecuteProcess(
            cmd=['rviz2', '-d', rviz_dir],
            output='screen',
            name='rviz',
            additional_env={'LD_LIBRARY_PATH': os.environ['LD_LIBRARY_PATH']}
        ),
        ExecuteProcess(
            cmd=['ros2', 'bag', 'play', bags_dir],
            output='screen',
            additional_env={'LD_LIBRARY_PATH': os.environ['LD_LIBRARY_PATH']},
            shell=True,
            name='bag_playback'
        )
    ]

    # Add TimerActions to introduce delays
    delay_actions = []
    delay_duration = 2.0  # seconds

    for i in range(len(nodes)):
        if i > 0:
            delay_actions.append(TimerAction(period=delay_duration, actions=[]))

    # Combine nodes and delay actions
    launch_description = LaunchDescription(nodes + delay_actions)

    return launch_description
