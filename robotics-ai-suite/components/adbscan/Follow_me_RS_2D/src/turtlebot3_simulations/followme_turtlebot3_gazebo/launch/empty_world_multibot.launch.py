#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 Joep Tool ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    launch_file_dir = os.path.join(
        get_package_share_directory('followme_turtlebot3_gazebo'), 'launch'
    )
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')
    x_pose_gbot = LaunchConfiguration('x_pose_gbot', default='0.4')
    y_pose_gbot = LaunchConfiguration('y_pose_gbot', default='0.0')

    # Declare the launch arguments

    declare_x_pos_gbot = DeclareLaunchArgument(
        'x_pose_gbot',
        default_value='0.0',
        description='Specify initial x position of the guide robot',
    )
    declare_y_pos_gbot = DeclareLaunchArgument(
        'y_pose_gbot',
        default_value='0.0',
        description='Specify initial y position of the guide robot',
    )

    world = os.path.join(
        get_package_share_directory('followme_turtlebot3_gazebo'), 'worlds', 'empty_world.world'
    )

    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world}.items(),
    )

    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py'))
    )

    # turtlebot: robot state publisher and spawn_entity
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

    # guide robot: robot state publisher and spawn_entity
    gbot_robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'gbot_robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )

    spawn_gbot_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(launch_file_dir, 'spawn_gbot.launch.py')),
        launch_arguments={'x_pose': x_pose_gbot, 'y_pose': y_pose_gbot}.items(),
    )

    ld = LaunchDescription()

    # Add the commands to the launch description
    ld.add_action(declare_x_pos_gbot)
    ld.add_action(declare_y_pos_gbot)

    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)
    ld.add_action(gbot_robot_state_publisher_cmd)
    ld.add_action(spawn_gbot_cmd)

    return ld
