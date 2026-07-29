#!/usr/bin/env python3
# pylint: disable=duplicate-code

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 Joep Tool ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

"""Launch file for TurtleBot3 simulation in empty world."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """Generate launch description for TurtleBot3 in empty world."""
    launch_file_dir = os.path.join(
        get_package_share_directory('followme_turtlebot3_gazebo'), 'launch'
    )
    pkg_gazebo_ros = get_package_share_directory('ros_gz_sim')
    turtlebot3_gazebo_path = get_package_share_directory('turtlebot3_gazebo')

    # Set GZ_SIM_RESOURCE_PATH to include both official turtlebot3_gazebo and custom models
    gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=os.path.join(turtlebot3_gazebo_path, 'models') + ':' +
        os.path.join(get_package_share_directory('followme_turtlebot3_gazebo'), 'models')
    )

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')

    # Use world file from official turtlebot3_gazebo package
    world = os.path.join(
        turtlebot3_gazebo_path, 'worlds', 'empty_world.world'
    )

    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': ['-r ', world], 'on_exit_shutdown': 'true'}.items(),
    )

    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )

    spawn_turtlebot_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(launch_file_dir, 'spawn_turtlebot3.launch.py')),
        launch_arguments={'x_pose': x_pose, 'y_pose': y_pose}.items(),
    )

    ld = LaunchDescription()

    # Set environment variable first
    ld.add_action(gz_resource_path)

    # Add the commands to the launch description
    ld.add_action(gzserver_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)

    return ld
