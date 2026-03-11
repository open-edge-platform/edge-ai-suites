#!/usr/bin/env python3
# pylint: disable=duplicate-code

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

"""Terminal 1 — Gazebo world + bridges for LiDAR follow-me.

Launches:
    • empty_world with two robots (TurtleBot3 waffle + guide robot)
    • Gazebo-ROS bridges: clock, laser scan, cmd_vel (follower + guide),
      guide odometry, camera image

Run lidar_gesture.launch.py or lidar_gesture_audio.launch.py in a second
terminal to start the perception / control nodes.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description."""
    launch_file_dir = os.path.join(
        get_package_share_directory('followme_turtlebot3_gazebo'), 'launch'
    )

    x_pose_gbot = LaunchConfiguration('x_pose_gbot', default='0.8')
    y_pose_gbot = LaunchConfiguration('y_pose_gbot', default='0.0')
    yaw_pose_gbot = LaunchConfiguration('yaw_pose_gbot', default='0.0')

    # --- Gazebo world with two robots ---
    launch_gz_world_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'empty_world_multibot.launch.py')
        ),
        launch_arguments={
            'x_pose_gbot': x_pose_gbot,
            'y_pose_gbot': y_pose_gbot,
            'yaw_pose_gbot': yaw_pose_gbot,
        }.items(),
    )

    # --- Gazebo-ROS bridges ---

    # Clock (Gazebo → ROS2) — required for use_sim_time nodes
    gz_clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
    )

    # LiDAR scan (Gazebo → ROS2)
    gz_scan_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'],
        output='screen',
    )

    # Follower robot cmd_vel (ROS2 → Gazebo)
    gz_cmd_vel_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist'],
        remappings=[('/cmd_vel', '/tb3/cmd_vel')],
        output='screen',
    )

    # Guide robot cmd_vel (ROS2 → Gazebo)
    gz_guide_cmd_vel_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/guide_robot/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist'],
        output='screen',
    )

    # Guide robot odometry (Gazebo → ROS2)
    gz_guide_odom_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/guide_robot/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry'],
        output='screen',
    )

    # Camera image (Gazebo → ROS2) for RViz
    gz_camera_image_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image'],
        output='screen',
    )

    ld = LaunchDescription()
    ld.add_action(launch_gz_world_cmd)
    ld.add_action(gz_clock_bridge)
    ld.add_action(gz_scan_bridge)
    ld.add_action(gz_cmd_vel_bridge)
    ld.add_action(gz_guide_cmd_vel_bridge)
    ld.add_action(gz_guide_odom_bridge)
    ld.add_action(gz_camera_image_bridge)
    return ld
