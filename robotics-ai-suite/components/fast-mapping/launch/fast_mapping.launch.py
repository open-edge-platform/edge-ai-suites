#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
This module defines a ROS 2 launch description for the 'fast_mapping' package.
It launches the following components:
- The 'fast_mapping_node' from the 'fast_mapping' package.
- RViz2 with a specific configuration file for visualization.
- Playback of a ROS 2 bag file containing recorded sensor data.

A delay is introduced between the startup of each component using TimerAction
to ensure proper initialization order.
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch_ros.actions import Node

from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch.actions import TimerAction


def generate_launch_description():
    """
    Creates and returns a LaunchDescription object that specifies the nodes
    and processes to be launched, along with the necessary delays between them.

    Returns:
        LaunchDescription: The launch description object specifying the nodes
        and processes to be launched, including the necessary delays between them.
    """

    package_share_directory = get_package_share_directory('fast_mapping')
    bags_dir = os.path.join('/opt/ros/humble', 'share', 'bagfiles', 'spinning')
    rviz_dir = os.path.join(
        package_share_directory, 'launch', 'config', 'fastmapping_tutorial_config.rviz'
    )

    # Define nodes and actions
    nodes = [
        Node(
            package='fast_mapping',
            executable='fast_mapping_node',
            output='screen',
            name='fast_mapping',
        ),
        ExecuteProcess(
            cmd=['rviz2', '-d', rviz_dir],
            output='screen',
            name='rviz',
            additional_env={'LD_LIBRARY_PATH': os.environ['LD_LIBRARY_PATH']},
        ),
        ExecuteProcess(
            cmd=['ros2', 'bag', 'play', bags_dir],
            output='screen',
            additional_env={'LD_LIBRARY_PATH': os.environ['LD_LIBRARY_PATH']},
            shell=True,
            name='bag_playback',
        ),
    ]

    # Add TimerActions to introduce delays
    delay_actions = []
    delay_duration = 2.0  # seconds

    for i in range(len(nodes)):
        if i > 0:
            delay_actions.append(TimerAction(period=delay_duration, actions=[]))

    # Combine nodes and delay actions
    launch_description = LaunchDescription(nodes + delay_actions)

    return launch_description
