# Copyright (C) 2025 Intel Corporation
# pylint: disable=duplicate-code
# Copyright 2019 Open Source Robotics Foundation, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Launch file for TurtleBot3 Gazebo simulation."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description."""
    # Get the urdf file
    model_folder = 'guide_robot'
    urdf_path = os.path.join(
        get_package_share_directory('followme_turtlebot3_gazebo'),
        'models',
        model_folder,
        'model.sdf',
    )

    # Launch configuration variables specific to simulation
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')
    yaw_pose = LaunchConfiguration('yaw_pose', default='0.0')

    # Declare the launch arguments
    declare_x_position_cmd = DeclareLaunchArgument(
        'x_pose', default_value='0.0', description='Initial x position of the guide robot'
    )

    declare_y_position_cmd = DeclareLaunchArgument(
        'y_pose', default_value='0.0', description='Initial y position of the guide robot'
    )

    declare_yaw_cmd = DeclareLaunchArgument(
        'yaw_pose', default_value='0.0', description='Initial yaw of the guide robot'
    )

    start_gazebo_ros_spawner_cmd = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-entity',
            'guide_robot',
            '-file',
            urdf_path,
            '-x',
            x_pose,
            '-y',
            y_pose,
            '-z',
            '0.01',
            '-Y',
            yaw_pose,
        ],
        output='screen',
    )

    ld = LaunchDescription()

    # Declare the launch options
    ld.add_action(declare_x_position_cmd)
    ld.add_action(declare_y_position_cmd)
    ld.add_action(declare_yaw_cmd)

    # Add any conditioned actions
    ld.add_action(start_gazebo_ros_spawner_cmd)

    return ld
