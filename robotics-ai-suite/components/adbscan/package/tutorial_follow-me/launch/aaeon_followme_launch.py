# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnShutdown


def generate_launch_description():
    amr_interface_config_file = (
        '/opt/ros/humble/share/ros2_amr_interface/params/'
        'aaeon_node_params.yaml'
    )
    package_share = FindPackageShare('tutorial_follow_me')
    package_name = package_share.find('tutorial_follow_me')
    adbscan_param_file = os.path.join(
        package_name, 'params', 'followme_adbscan_RS_params.yaml'
    )
    rviz_config_file = os.path.join(
        package_name, 'config', 'adbscan_RS_config.rviz'
    )

    # RealSense launch
    realsense_launch_dir = os.path.join(
        FindPackageShare('realsense2_camera').find('realsense2_camera'),
        'launch'
    )
    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            realsense_launch_dir, 'rs_launch.py')
        ),
        launch_arguments={
            'pointcloud.enable': 'true',
            'camera_namespace': '/'
        }.items(),
    )

    # Launch the AAEON Robot Motor Board Interface
    aaeon_node = Node(
        package='ros2_amr_interface',
        executable='amr_interface_node',
        name='amr_interface_node',
        output='screen',
        parameters=[amr_interface_config_file],
        remappings=[
            ('/amr/cmd_vel', '/cmd_vel'),
            ('/amr/battery', '/sensors/battery_state')
        ]
    )

    # Launch the adbscan follower node
    adbscan_node = Node(
        package='adbscan_ros2_follow_me',
        executable='adbscan_sub',
        name='adbscan_follow_me',
        output='screen',
        parameters=[adbscan_param_file]
    )

    # Launch RViz
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
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
        aaeon_node,
        realsense_launch,
        adbscan_node,
        rviz_node,
        on_shutdown_handler,
    ])
