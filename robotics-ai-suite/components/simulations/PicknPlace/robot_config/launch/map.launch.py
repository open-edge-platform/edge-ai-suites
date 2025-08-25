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

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LOG_LEVEL = 'warn'

def generate_launch_description():

    ld = LaunchDescription()   
    # ros support github link -> https://github.com/bponsler/ros2-support
    package_path = get_package_share_directory("robot_config")
    
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    map_file = LaunchConfiguration('map', default=os.path.join(package_path, 'maps', 'default.yaml'))
    remappings = [('/tf', 'tf'),
                  ('/tf_static', 'tf_static')]
    
    map_server=Node(package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[{'yaml_filename': map_file},],
        remappings=remappings)

    map_server_lifecyle=Node(package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_map_server',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time},
                        {'autostart': True},
                        {'node_names': ['map_server']}])

    ld.add_action(map_server)
    ld.add_action(map_server_lifecyle)


   
    return ld