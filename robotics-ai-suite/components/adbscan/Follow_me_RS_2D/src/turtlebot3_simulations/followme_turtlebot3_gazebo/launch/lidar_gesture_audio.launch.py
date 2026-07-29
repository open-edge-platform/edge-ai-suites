#!/usr/bin/env python3
# pylint: disable=duplicate-code

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

"""Terminal 2 — Perception nodes for LiDAR follow-me with gesture + audio.

Launches:
    • ADBSCAN node (2D LiDAR config)
    • Gesture recognition node
    • Speech recognition node
    • Trajectory/image publisher and audio file publisher

Run lidar_shared.launch.py in a first terminal before starting this file.

Usage:
    ros2 launch followme_turtlebot3_gazebo lidar_gesture_audio.launch.py
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description."""
    # ADBSCAN node — 2D LiDAR mode
    adbscan_params_file = os.path.join(
        get_package_share_directory('adbscan_ros2_follow_me'),
        'config',
        'adbscan_sub_2D.yaml',
    )
    adbscan_node = Node(
        package='adbscan_ros2_follow_me',
        executable='adbscan_sub_w_gesture_audio',
        parameters=[adbscan_params_file, {'use_sim_time': True}],
        remappings=[('cmd_vel', 'tb3/cmd_vel')],
        output='screen',
    )

    # Gesture recognition
    gesture_params_file = os.path.join(
        get_package_share_directory('gesture_recognition_pkg'),
        'config',
        'gesture_recognition.yaml',
    )
    gesture_node = Node(
        package='gesture_recognition_pkg',
        executable='gesture_recognition_node.py',
        parameters=[gesture_params_file, {'use_sim_time': True}],
    )

    # Speech recognition
    speech_params_file = os.path.join(
        get_package_share_directory('speech_recognition_pkg'),
        'config',
        'speech_recognition.yaml',
    )
    speech_node = Node(
        package='speech_recognition_pkg',
        executable='speech_recognition_node.py',
        parameters=[speech_params_file, {'use_sim_time': True}],
        output='screen',
    )

    # Trajectory and image publisher
    traj_node = Node(
        package='gesture_recognition_pkg',
        executable='traj_and_img_publisher_node.py',
        parameters=[gesture_params_file, {'use_sim_time': True}],
    )

    # Audio file publisher
    audio_pub_node = Node(
        package='speech_recognition_pkg',
        executable='audio_publisher_node.py',
        parameters=[speech_params_file, {'use_sim_time': True}],
        output='screen',
    )

    ld = LaunchDescription()
    ld.add_action(adbscan_node)
    ld.add_action(gesture_node)
    ld.add_action(speech_node)
    ld.add_action(traj_node)
    ld.add_action(audio_pub_node)
    return ld
