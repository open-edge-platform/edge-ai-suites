#!/usr/bin/env python3
# pylint: disable=duplicate-code

# Copyright (C) 2025 Intel Corporation
# Copyright 2019 ROBOTIS CO., LTD.
#
# SPDX-License-Identifier: Apache-2.0

"""Launch file for TurtleBot3 Gazebo simulation - RS mode (Gazebo + Bridges only)."""

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

    launch_gz_world_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'empty_world_multibot.launch.py')
        ),
        launch_arguments={'x_pose_gbot': x_pose_gbot, 'y_pose_gbot': y_pose_gbot}.items(),
    )

    # Bridge to convert Gazebo /scan/points to ROS2 /camera/points with BEST_EFFORT QoS
    gz_ros_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/scan/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked',
        ],
        remappings=[
            ('/scan/points', '/camera/points'),
        ],
        parameters=[{
            'qos_overrides./camera/points.publisher.reliability': 'best_effort',
        }],
        output='screen',
    )

    # Bridge for follower robot cmd_vel
    gz_cmd_vel_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
        ],
        remappings=[
            ('/cmd_vel', '/tb3/cmd_vel'),
        ],
        output='screen',
    )

    # Bridge for guide robot cmd_vel
    gz_guide_cmd_vel_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/guide_robot/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
        ],
        output='screen',
    )

    # Bridge for guide robot odometry
    gz_guide_odom_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/guide_robot/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',
        ],
        output='screen',
    )

    ld = LaunchDescription()

    # Add the commands to the launch description
    ld.add_action(launch_gz_world_cmd)
    ld.add_action(gz_ros_bridge)
    ld.add_action(gz_cmd_vel_bridge)
    ld.add_action(gz_guide_cmd_vel_bridge)
    ld.add_action(gz_guide_odom_bridge)

    return ld
