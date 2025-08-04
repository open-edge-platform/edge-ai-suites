# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from launch import LaunchDescription
from launch.actions import RegisterEventHandler, LogInfo, OnShutdown
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare('tutorial_follow_me')
    package_name = package_share.find('tutorial_follow_me')
    adbscan_param_file = os.path.join(
        package_name,
        'params',
        'followme_adbscan_RS_params.yaml'
    )
    rviz_config_file = os.path.join(
        package_name, 'config', 'adbscan_RS_config.rviz')

    # RealSense camera launch
    realsense_launch_dir = os.path.join(
        FindPackageShare('realsense2_camera').find('realsense2_camera'),
        'launch'
    )
    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(realsense_launch_dir, 'rs_launch.py')
        ),
        launch_arguments={
            'pointcloud.enable': 'true',
            'camera_namespace': '/'
        }.items(),
    )

    # adbscan follow-me node
    adbscan_node = Node(
        package='adbscan_ros2_follow_me',
        executable='adbscan_sub',
        output='screen',
        parameters=[adbscan_param_file]
    )

    # RViz
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_file],
        output='screen'
    )

    on_shutdown_handler = RegisterEventHandler(
        event_handler=OnShutdown(
            on_shutdown=[
                LogInfo(msg="App is shutting down..."),
            ]
        )
    )

    return LaunchDescription([
        realsense_launch,
        adbscan_node,
        rviz_node,
        on_shutdown_handler,
    ])
