# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess


def generate_launch_description():
    ros_distro = 'humble'
    install_dir = f'/opt/ros/{ros_distro}/share/adbscan_ros2'
    rviz_config_file = f'{install_dir}/config/adbscan_RS_config.rviz'
    adbscan_param_file = f'{install_dir}/config/adbscan_sub_RS.yaml'
    bag_file = f'/opt/ros/{ros_distro}/share/bagfiles/laser-pointcloud'

    return LaunchDescription([
        # Launch adbscan node with parameters
        Node(
            package='adbscan_ros2',
            executable='adbscan_sub',
            parameters=[adbscan_param_file]
        ),
        # Play rosbag in loop
        ExecuteProcess(
            cmd=['ros2', 'bag', 'play', '--loop', bag_file],
            output='screen'
        ),
        # Start RViz with config
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', rviz_config_file]
        ),
    ])
