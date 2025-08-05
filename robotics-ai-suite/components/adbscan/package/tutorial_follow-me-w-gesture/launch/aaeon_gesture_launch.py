# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription
from launch.event_handlers import OnShutdown
from launch.actions import RegisterEventHandler, LogInfo


def generate_launch_description():
    # launch arguments for two cameras one for nav and other for gesture
    camera1_serial_no_arg = DeclareLaunchArgument(
        'camera1_serial_no',
        description='Serial number of camera 1'
    )
    camera2_serial_no_arg = DeclareLaunchArgument(
        'camera2_serial_no',
        description='Serial number of camera 2'
    )

    amr_interface_config_file = (
        '/opt/ros/humble/share/ros2_amr_interface/params/'
        'aaeon_node_params.yaml'
    )
    package_name = (
        FindPackageShare('tutorial_follow_me_w_gesture')
        .find('tutorial_follow_me_w_gesture')
    )
    adbscan_param_file = os.path.join(
        package_name,
        'params',
        'followme_adbscan_RS_params.yaml'
    )
    gesture_param_file = os.path.join(
        package_name,
        'params',
        'gesture_recognition_robot_bringup.yaml'
    )
    rviz_file = os.path.join(package_name, 'config', 'adbscan_RS_config.rviz')

    # Aaeon AMR interface node
    amr_interface_node = Node(
        package='ros2_amr_interface',
        executable='amr_interface_node',
        parameters=[amr_interface_config_file],
        remappings=[
            ('/amr/cmd_vel', '/cmd_vel'),
            ('/amr/battery', '/sensors/battery_state')
        ]
    )

    # RealSense launch
    realsense_launch_dir = os.path.join(
        FindPackageShare('realsense2_camera').find('realsense2_camera'),
        'launch'
    )
    # RealSense camera 1 node launch
    realsense_camera1_node = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(realsense_launch_dir, 'rs_launch.py')
        ),
        launch_arguments={
            'pointcloud.enable': 'true',
            'camera_name': 'camera',
            'camera_namespace': '/',
            'serial_no': LaunchConfiguration('camera1_serial_no')
        }.items(),
    )

    # RealSense camera 2 node launch
    realsense_camera2_node = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(realsense_launch_dir, 'rs_launch.py')
        ),
        launch_arguments={
            'pointcloud.enable': 'true',
            'camera_name': 'camera2',
            'camera_namespace': '/',
            'serial_no': LaunchConfiguration('camera2_serial_no')
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
        parameters=[gesture_param_file],
        remappings=[
            ('/camera/color/image_raw', '/camera2/color/image_raw')
        ]
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
        camera1_serial_no_arg,
        camera2_serial_no_arg,
        amr_interface_node,
        realsense_camera1_node,
        realsense_camera2_node,
        adbscan_node,
        gesture_node,
        rviz_node,
        on_shutdown_handler,
    ])
