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
    # Get the urdf file from official turtlebot3_gazebo package
    turtlebot3_model = os.environ.get('TURTLEBOT3_MODEL', 'waffle')
    model_folder = 'turtlebot3_' + turtlebot3_model
    default_urdf_path = os.path.join(
        get_package_share_directory('turtlebot3_gazebo'),
        'models',
        model_folder,
        'model.sdf',
    )

    # Launch configuration variables specific to simulation
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')
    model_sdf_path = LaunchConfiguration('model_sdf_path', default=default_urdf_path)

    # Declare the launch arguments
    declare_x_position_cmd = DeclareLaunchArgument(
        'x_pose', default_value='0.0', description='Specify namespace of the robot'
    )

    declare_y_position_cmd = DeclareLaunchArgument(
        'y_pose', default_value='0.0', description='Specify namespace of the robot'
    )

    declare_model_sdf_path_cmd = DeclareLaunchArgument(
        'model_sdf_path',
        default_value=default_urdf_path,
        description='Path to custom model SDF file (overrides TURTLEBOT3_MODEL default)',
    )

    start_gazebo_ros_spawner_cmd = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-entity',
            turtlebot3_model,
            '-file',
            model_sdf_path,
            '-x',
            x_pose,
            '-y',
            y_pose,
            '-z',
            '0.01',
        ],
        output='screen',
    )

    ld = LaunchDescription()

    # Declare the launch options
    ld.add_action(declare_x_position_cmd)
    ld.add_action(declare_y_position_cmd)
    ld.add_action(declare_model_sdf_path_cmd)

    # Add any conditioned actions
    ld.add_action(start_gazebo_ros_spawner_cmd)

    return ld
