#!/usr/bin/env python3
# pylint: disable=duplicate-code

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

"""Terminal 2 — Perception nodes for RealSense follow-me with gesture (no audio).

Launches:
    • ADBSCAN node (RealSense / depth-camera config, gesture only)
    • Gesture recognition node
    • Trajectory and image publisher node

Run rs_shared.launch.py in a first terminal before starting this file.

Usage:
    ros2 launch followme_turtlebot3_gazebo rs_gesture.launch.py
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description."""
    # ADBSCAN node — RealSense / depth-camera, gesture only (no audio)
    # Gazebo simulation overrides (YAML keeps hardware defaults):
    #   optical_frame: False — Gazebo Harmonic publishes PointCloud2 in body
    #       frame when gz_frame_id is set, so skip optical→body rotation.
    #   min_dist: 0.3 — The depth camera sees the guide robot's front surface
    #       at ~0.44 m (not the 0.8 m center-to-center spawn distance), so the
    #       YAML's 0.5 m threshold makes the follower think it is "too close"
    #       and sets linear velocity to 0.
    #   init_tgt_loc: 0.5 — Closer to the actual ~0.44 m cluster centroid for
    #       faster initial target lock.
    adbscan_params_file = os.path.join(
        get_package_share_directory('adbscan_ros2_follow_me'),
        'config',
        'adbscan_sub_RS.yaml',
    )
    adbscan_node = Node(
        package='adbscan_ros2_follow_me',
        executable='adbscan_sub_w_gesture',
        parameters=[adbscan_params_file, {
            'use_sim_time': True,
            'optical_frame': False,
            'min_dist': 0.3,
            'init_tgt_loc': 0.5,
        }],
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

    # Trajectory and image publisher
    traj_node = Node(
        package='gesture_recognition_pkg',
        executable='traj_and_img_publisher_node.py',
        parameters=[gesture_params_file, {'use_sim_time': True}],
    )

    ld = LaunchDescription()
    ld.add_action(adbscan_node)
    ld.add_action(gesture_node)
    ld.add_action(traj_node)
    return ld
