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

"""Launch file for wandering AAEON robot tutorial."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def get_ros_distro():
    """Get the ROS 2 distribution name."""
    return os.environ.get('ROS_DISTRO', 'humble')


def generate_launch_description():  # pylint: disable=too-many-locals
    """Generate launch description for wandering AAEON tutorial."""
    wandering_tutorial_dir = get_package_share_directory(
        'wandering_aaeon_tutorial'
    )

    ros_distro = get_ros_distro()

    if ros_distro == 'humble':
        nav2_param_file = os.path.join(
            wandering_tutorial_dir,
            'params',
            'aaeon_nav.param_humble.yaml'
        )
        # For Humble we use the standard nav2_bringup
        nav2_launch_file = os.path.join(
            get_package_share_directory('nav2_bringup'),
            'launch',
            'navigation_launch.py'
        )
        nav2_launch_args = {
            'params_file': nav2_param_file,
            'namespace': '',
            'use_namespace': 'false',
        }
        timer_period = 4.0
    else:  # jazzy or newer distributions
        nav2_param_file = os.path.join(
            wandering_tutorial_dir,
            'params',
            'aaeon_nav.param_jazzy.yaml'
        )
        # For Jazzy we use a custom launch file
        nav2_launch_file = os.path.join(
            wandering_tutorial_dir,
            'launch',
            'custom_nav2_launch.py'
        )
        nav2_launch_args = {
            'params_file': nav2_param_file,
            'namespace': '',
            'use_sim_time': 'false',
            'autostart': 'true',
        }
        timer_period = 8.0

    aaeon_interface_config = os.path.join(
        get_package_share_directory('ros2_amr_interface'),
        'params',
        'aaeon_node_params.yaml'
    )

    rviz_config_file = os.path.join(
        wandering_tutorial_dir,
        'rviz',
        'wandering-aaeon-tutorial.rviz',
    )

    use_rviz = LaunchConfiguration('use_rviz')
    params_file = LaunchConfiguration('params_file')

    declare_use_rviz_cmd = DeclareLaunchArgument(
        'use_rviz', default_value='true', description='Start navigation configured RViz'
    )

    declare_rviz_config_cmd = DeclareLaunchArgument(
        'rviz_config',
        default_value=rviz_config_file,
        description='Full path to the RViz configuration file',
    )

    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        default_value=nav2_param_file,
        description='Full path to the ROS2 parameters file to use for all launched nodes',
    )

    amr_interface_node = Node(
        package='ros2_amr_interface',
        executable='amr_interface_node',
        parameters=[aaeon_interface_config],
        remappings=[
            ('/amr/cmd_vel', '/cmd_vel'),
            ('/amr/battery', '/sensors/battery_state'),
            ('/amr/odometry', '/odom'),
        ],
    )

    camera_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_tf',
        arguments=['0.09', '0', '0.16', '0', '0', '0', 'base_link', 'camera_link'],
        parameters=[{'use_sim_time': False}],
    )

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                os.path.join(
                    get_package_share_directory('realsense2_camera'), 'launch', 'rs_launch.py'
                )
            ]
        ),
        launch_arguments={
            'enable_infra1': 'true',
            'align_depth.enable': 'true',
            'enable_sync': 'true',
            'init_reset': 'true',
            'pointcloud.enable': 'true',
            'camera_namespace': '/',
        }.items(),
    )

    depthimage_to_laserscan_node = Node(
        package='depthimage_to_laserscan',
        executable='depthimage_to_laserscan_node',
        remappings=[
            ('/depth', '/camera/depth/image_rect_raw'),
            ('/depth_camera_info', '/camera/depth/camera_info'),
        ],
        parameters=[{'scan_time': 0.033}, {'range_min': 0.1}, {'range_max': 2.5}],
    )

    rtabmap_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                os.path.join(
                    wandering_tutorial_dir,
                    'launch',
                    'rtabmap.launch.py',
                )
            ]
        ),
        launch_arguments={'localization': 'false'}.items(),
    )

    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        parameters=[{'remove_gravity_vector': True}, {'use_mag': False}, {'publish_tf': False}],
        remappings=[('/imu/data_raw', '/amr/imu/raw')],
    )

    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(nav2_launch_file),
        launch_arguments=nav2_launch_args.items(),
    )

    rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('nav2_bringup'),
                'launch',
                'rviz_launch.py'
            )
        ),
        launch_arguments={
            'params_file': params_file,
            'namespace': '',
            'use_namespace': 'false',
        }.items(),
        condition=IfCondition(use_rviz),
    )

    wandering_app = Node(
        package='wandering_app',
        executable='wandering',
        parameters=[params_file]
    )

    return LaunchDescription(
        [
            declare_params_file_cmd,
            declare_use_rviz_cmd,
            declare_rviz_config_cmd,
            amr_interface_node,
            camera_tf,
            realsense_launch,
            depthimage_to_laserscan_node,
            rtabmap_launch,
            imu_filter_node,
            TimerAction(
                period=timer_period,
                actions=[
                    navigation_launch,
                ],
            ),
            rviz_launch,
            wandering_app,
        ]
    )
