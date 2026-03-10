#!/usr/bin/env python3
# pylint: disable=duplicate-code

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 Darby Lim ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

"""Launch file for TurtleBot3 robot state publisher."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for TurtleBot3 robot state publisher."""
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    # urdf_file_name = 'turtlebot3_' + turtlebot3_model + '.urdf'
    urdf_file_name = 'turtlebot3_waffle_w_depth_cam.urdf'
    print(f'urdf_file_name : {urdf_file_name}')

    urdf_path = os.path.join(
        get_package_share_directory('followme_turtlebot3_gazebo'), 'urdf', urdf_file_name
    )

    with open(urdf_path, 'r', encoding='utf-8') as infp:
        robot_desc = infp.read()

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'use_sim_time',
                default_value='false',
                description='Use simulation (Gazebo) clock if true',
            ),
            Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                name='robot_state_publisher_tb3',
                namespace='tb3',
                output='screen',
                parameters=[{'use_sim_time': use_sim_time, 'robot_description': robot_desc}],
                remappings=[('tf', 'tb3/tf')],
                # ('robot_description', 'tb3/robot_description'),
                # ('joint_states', 'tb3/joint_states')
                # ],
            ),
        ]
    )
