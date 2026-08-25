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
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import LaunchConfigurationEquals
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Run scripts/find_cameras.sh to determine which value to pass here.
    camera_type = LaunchConfiguration('camera_type')

    declare_camera_type_cmd = DeclareLaunchArgument(
        'camera_type',
        default_value='usb',
        choices=['usb', 'gmsl'],
        description='Connected camera type, as reported by scripts/find_cameras.sh',
    )

    realsense2_tutorial_share_dir = get_package_share_directory('realsense2_tutorial')
    realsense2_camera_launch_file_path = os.path.join(
        get_package_share_directory('realsense2_camera'), 'launch', 'rs_launch.py'
    )
    # Restricts each raw image topic to its compatible image_transport plugins;
    # see the file for why this is needed.
    image_transport_overrides_path = os.path.join(
        realsense2_tutorial_share_dir, 'config', 'image_transport_overrides.yaml'
    )

    realsense2_usb_launch_file = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(realsense2_camera_launch_file_path),
        launch_arguments={
            'align_depth.enable': 'true',
            'camera_namespace': '/',
            'config_file': image_transport_overrides_path,
        }.items(),
        condition=LaunchConfigurationEquals('camera_type', 'usb'),
    )

    realsense2_gmsl_launch_file = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(realsense2_camera_launch_file_path),
        launch_arguments={
            'align_depth.enable': 'true',
            'camera_name': 'D457_mux_a',
            'device_type': 'd457',
            'camera_namespace': '/',
            'config_file': image_transport_overrides_path,
            # D457 GMSL only exposes YUYV; without an explicit profile the
            # driver's "first available profile" fallback picks an invalid
            # resolution and fails to open the RGB stream.
            'rgb_camera.color_profile': '640x480x30',
            'depth_module.depth_profile': '640x480x30',
        }.items(),
        condition=LaunchConfigurationEquals('camera_type', 'gmsl'),
    )

    rviz2_usb_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=[
            '-d', os.path.join(realsense2_tutorial_share_dir, 'config', 'realsense_config.rviz')
        ],
        condition=LaunchConfigurationEquals('camera_type', 'usb'),
    )

    rviz2_gmsl_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=[
            '-d',
            os.path.join(
                realsense2_tutorial_share_dir, 'config', 'realsense_config_rsd457_gmsl.rviz'
            ),
        ],
        condition=LaunchConfigurationEquals('camera_type', 'gmsl'),
    )

    return LaunchDescription(
        [
            declare_camera_type_cmd,
            realsense2_usb_launch_file,
            realsense2_gmsl_launch_file,
            rviz2_usb_node,
            rviz2_gmsl_node,
        ]
    )
