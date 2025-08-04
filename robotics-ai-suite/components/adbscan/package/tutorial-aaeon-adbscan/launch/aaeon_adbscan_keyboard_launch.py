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
    aaeon_config = (
        f'/opt/ros/{ros_distro}/share/ros2_amr_interface/params/'
        'aaeon_node_params.yaml'
    )
    ukf_config = os.path.join(
        install_dir, 'tutorial-aaeon-adbscan', 'ukf_config.yaml'
    )
    adbscan_config = os.path.join(
        install_dir, 'tutorial-aaeon-adbscan', 'adbscan_RS_params.yaml'
    )
    rviz_config = os.path.join(
        install_dir, 'tutorial-aaeon-adbscan', 'adbscan_aaeon.rviz'
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
        }.items()
    )

    # Individual nodes
    aaeon_node = Node(
        package='ros2_amr_interface',
        executable='amr_interface_node',
        name='amr_interface_node',
        output='screen',
        parameters=[aaeon_config],
        remappings=[
            ('/amr/battery', '/sensors/battery_state'),
            ('/amr/cmd_vel', '/cmd_vel'),
        ]
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
        name='ukf_node',
        output='screen',
        parameters=[ukf_config, {'publishTF': False}]
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
        name='adbscan_sub',
        parameters=[adbscan_config],
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
        name='fast_mapping_node',
        output='screen',
        remappings=[
            ('/world/map_updates', '/map_updates'),
            ('/world/map', '/map'),
        ]
    )

    map_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        output='screen',
        parameters=[{'use_sim_time': False}]
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        output='screen'
    )

    on_shutdown_handler = RegisterEventHandler(
        OnShutdown(
            on_shutdown=[
                LogInfo(msg="ADBSCAN App is shutting down..."),
            ]
        )
    )

    return LaunchDescription([
        aaeon_node,
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
