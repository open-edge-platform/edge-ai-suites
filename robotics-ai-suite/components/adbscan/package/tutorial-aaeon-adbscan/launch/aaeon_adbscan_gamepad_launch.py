# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from launch import LaunchDescription
from launch.actions import LogInfo, IncludeLaunchDescription
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ros_distro = 'humble'
    install_dir = f'/opt/ros/{ros_distro}/share/aaeon_adbscan'
    aaeon_node_config_file = (
        f'/opt/ros/{ros_distro}/share/ros2_amr_interface/params/'
        'aaeon_node_params.yaml'
    )
    twist_mux_config_file = (
        f'{install_dir}/tutorial-aaeon-adbscan/twist_mux_topics.yaml'
    )
    teleop_joy_config_file = (
        f'{install_dir}/tutorial-aaeon-adbscan/joy.config.yaml'
    )
    localization_config_file = (
        f'{install_dir}/tutorial-aaeon-adbscan/ukf_config.yaml'
    )
    adbscan_config_file = (
        f'{install_dir}/tutorial-aaeon-adbscan/adbscan_RS_params.yaml'
    )
    rviz_config_file = (
        f'{install_dir}/tutorial-aaeon-adbscan/adbscan_aaeon.rviz'
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
            'align_depth.enable': 'true',
            'enable_sync': 'true',
            'init_reset': 'true',
            'pointcloud.enable': 'true',
            'camera_namespace': '/'
        }.items(),
    )

    # Individual nodes
    aaeon_node = Node(
        package='ros2_amr_interface',
        executable='amr_interface_node',
        parameters=[aaeon_node_config_file],
        remappings=[('/amr/battery', '/sensors/battery_state')],
        output='screen',
    )

    joy_node = Node(
        package='joy_linux',
        executable='joy_linux_node',
        output='screen',
    )

    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        parameters=[twist_mux_config_file],
        remappings=[('cmd_vel_out', '/amr/cmd_vel')],
        output='screen',
    )

    teleop_twist_joy_node = Node(
        package='teleop_twist_joy',
        executable='teleop_node',
        parameters=[teleop_joy_config_file],
        remappings=[('cmd_vel', '/joy_vel')],
        output='screen',
    )

    imu_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=[
            '-0.07', '0', '0', '0', '0', '3.14', 'base_link', 'imu_link'
        ],
        parameters=[{'use_sim_time': False}],
        output='screen',
    )

    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        parameters=[
            {
                'remove_gravity_vector': True,
                'use_mag': False,
                'publish_tf': False
            }
        ],
        remappings=[('/imu/data_raw', '/amr/imu/raw')],
        output='screen',
    )

    ukf_node = Node(
        package='robot_localization',
        executable='ukf_node',
        parameters=[localization_config_file],
        output='screen',
    )

    camera_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=[
            '0.09', '0', '0.16', '0', '0', '0', 'base_link', 'camera_link'
        ],
        parameters=[{'use_sim_time': False}],
        output='screen',
    )

    adbscan_node = Node(
        package='adbscan_ros2',
        executable='adbscan_sub',
        parameters=[adbscan_config_file],
        output='screen',
    )

    adbscan_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'adbscan_link'],
        parameters=[{'use_sim_time': False}],
        output='screen',
    )

    fast_mapping_node = Node(
        package='fast_mapping',
        executable='fast_mapping_node',
        remappings=[
            ('/world/map_updates', '/map_updates'),
            ('/world/map', '/map')
        ],
        output='screen',
    )

    map_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        parameters=[{'use_sim_time': False}],
        output='screen',
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config_file],
        output='screen',
    )

    on_shutdown_handler = RegisterEventHandler(
        event_handler=OnShutdown(
            on_shutdown=[
                LogInfo(msg="ADBSCAN App is shutting down..."),
            ]
        )
    )

    # Return all nodes and launch inclusions in one list (flat)
    return LaunchDescription([
        aaeon_node,
        joy_node,
        twist_mux_node,
        teleop_twist_joy_node,
        imu_static_tf,
        imu_filter_node,
        ukf_node,
        realsense_launch,
        camera_static_tf,
        adbscan_node,
        adbscan_static_tf,
        fast_mapping_node,
        map_static_tf,
        rviz_node,
        on_shutdown_handler,
    ])
