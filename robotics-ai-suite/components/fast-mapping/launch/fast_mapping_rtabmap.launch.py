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
import launch
import launch.actions
import launch.substitutions
import launch_ros.actions
from launch.actions.timer_action import TimerAction
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition


fast_mapping_parameters = [
    {
        "projection_min_z": 0.2,
        "projection_max_z": 0.5,
        "max_depth_range": 3.0,
        "noise_factor": 0.08,
        "robot_radius": 0.2,
    }
]
def generate_launch_description():

    # ================== rviz2 ===============
    package_share_directory = get_package_share_directory('fast_mapping')
    rviz_config_dir = os.path.join(package_share_directory, 'launch', 'config', 'fastmapping_tutorial_config.rviz')
    rviz2_launch = launch_ros.actions.Node(
        name='rviz',package='rviz2',executable='rviz2',
        arguments=['-d' , rviz_config_dir]
    )

    # ============== SLAM ====================
    dir_path = get_package_share_directory('rtabmap_examples')
    rtabmap_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                dir_path + '/launch/realsense_d400.launch.py')
    )

    # =================== FastMapping ===================
    fm_launch = launch_ros.actions.Node(
            #node initialization as before
            name='fast_mapping',package='fast_mapping', executable='fast_mapping_node', output='screen',
            parameters=fast_mapping_parameters
    )

    # =================== Camera ===================
    rs_dir_path = get_package_share_directory('realsense2_camera')
    rs_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                rs_dir_path + '/launch/rs_launch.py'),
        launch_arguments={'align_depth.enable': 'true','camera_namespace':'/'}.items()
    )
    # ================== Node startup timings ===============
    launch_rtabmap_after_timer = TimerAction(period=10.0, actions=[rtabmap_launch])
    launch_fm_after_timer = TimerAction(period=12.0, actions=[fm_launch])
    launch_rs_after_timer = TimerAction(period=15.0, actions=[rs_launch])

    return launch.LaunchDescription([
            rviz2_launch,
            launch_rtabmap_after_timer,
            launch_fm_after_timer,
            launch_rs_after_timer
    ])
