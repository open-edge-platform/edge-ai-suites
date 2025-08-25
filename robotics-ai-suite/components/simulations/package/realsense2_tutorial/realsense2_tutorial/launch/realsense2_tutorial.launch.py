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
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, ExecuteProcess, TimerAction, RegisterEventHandler, LogInfo, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, EnvironmentVariable
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node

def generate_launch_description():

    # Launch file argument to change type camera
    use_usb_camera = LaunchConfiguration('use_usb_camera')

    declare_use_usb_camera_cmd = DeclareLaunchArgument(
        'use_usb_camera',
        default_value='true',
        description='Launch with USB camera (true) or GMSL camera (false)'
    )

    # Get the path to the RealSense Tutorial package share directory
    realsense2_tutorial_share_dir = get_package_share_directory('realsense2_tutorial')

    # Get the path to the RealSense Camera package share directory
    realsense2_camera_share_dir = get_package_share_directory('realsense2_camera')

    # RealSense Camera launch file
    realsense2_camera_launch_file_path = os.path.join(realsense2_camera_share_dir, 'launch', 'rs_launch.py')

    launch_description = LaunchDescription()

    # ROS2 topic list command
    ros2_topic_list_cmd = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'list'],
                output='screen'
            )
        ]
    )

    # USB
    realsense2_usb_launch_file = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(realsense2_camera_launch_file_path),
        launch_arguments={'align_depth.enable': 'true',
                          'camera_namespace': '/'}.items(),
        condition=IfCondition(use_usb_camera)
    )

    rviz2_usb_config_file = os.path.join(realsense2_tutorial_share_dir, 'config', 'realsense_config.rviz')

    rviz2_usb_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', rviz2_usb_config_file],
        condition=IfCondition(use_usb_camera)
    )

    ros2_usb_hz_cmd = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'hz', '/camera/color/image_raw'],
                output='screen'
            )
        ],
        condition=IfCondition(use_usb_camera)
    )

    # GMSL
    realsense2_gmsl_launch_file = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(realsense2_camera_launch_file_path),
        launch_arguments={'align_depth.enable': 'true',
                          'camera_name': 'D457_mux_a',
                          'device_type': 'd457',
                          'camera_namespace': '/'}.items(),
        condition=UnlessCondition(use_usb_camera)
    )

    rviz2_gmsl_config_file = os.path.join(realsense2_tutorial_share_dir, 'config', 'realsense_config_rsd457_gmsl.rviz')

    rviz2_gmsl_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', rviz2_gmsl_config_file],
        condition=UnlessCondition(use_usb_camera)
    )

    ros2_gmsl_hz_cmd = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'hz', '/D457_mux_a/color/image_raw'],
                output='screen'
            )
        ],
        condition=UnlessCondition(use_usb_camera)
    )

    launch_description.add_action(declare_use_usb_camera_cmd)
    launch_description.add_action(realsense2_usb_launch_file)
    launch_description.add_action(realsense2_gmsl_launch_file)
    launch_description.add_action(rviz2_usb_node)
    launch_description.add_action(rviz2_gmsl_node)
    launch_description.add_action(ros2_topic_list_cmd)
    launch_description.add_action(ros2_usb_hz_cmd)
    launch_description.add_action(ros2_gmsl_hz_cmd)

    return launch_description
