# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler, LogInfo, OnShutdown
from launch import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    camera_serial_no_arg = DeclareLaunchArgument(
        'camera_serial_no',
        description='Serial number of the camera'
    )

    package_name = (
        FindPackageShare('tutorial_follow_me_w_gesture')
        .find('tutorial_follow_me_w_gesture')
    )
    adbscan_param_file = os.path.join(
        package_name, 'params', 'followme_adbscan_RS_params.yaml'
    )
    gesture_param_file = os.path.join(
        package_name, 'params', 'gesture_recognition_robot_bringup.yaml'
    )
    rviz_file = os.path.join(package_name, 'config', 'adbscan_RS_config.rviz')

    # RealSense launch
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
            'camera_name': 'camera',
            'serial_no': LaunchConfiguration('camera_serial_no'),
            'depth_module.depth_profile': '640x480x30',
            'depth_module.infra_profile': '640x480x30',
            'rgb_camera.color_profile': '1280x720x24',
            'camera_namespace': '/',
        }.items(),
    )

    # Adbscan follow-me node
    adbscan_node = Node(
        package='adbscan_ros2_follow_me',
        executable='adbscan_sub_w_gesture',
        parameters=[adbscan_param_file]
    )

    # Gesture recognition node
    gesture_node = Node(
        package='gesture_recognition_pkg',
        executable='gesture_recognition_node.py',
        parameters=[gesture_param_file]
    )

    # RViz node
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_file]
    )

    on_shutdown_handler = RegisterEventHandler(
        event_handler=OnShutdown(
            on_shutdown=[
                LogInfo(msg="App is shutting down..."),
            ]
        )
    )

    return LaunchDescription([
        camera_serial_no_arg,
        realsense_launch,
        adbscan_node,
        gesture_node,
        rviz_node,
        on_shutdown_handler,
    ])
