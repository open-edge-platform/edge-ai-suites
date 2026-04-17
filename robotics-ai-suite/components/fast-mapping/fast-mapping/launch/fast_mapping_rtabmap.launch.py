#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Launch file for the Fast Mapping application using RTAB-Map and RealSense camera in ROS2.

This module defines a launch description that starts the following components:
- RViz2 for visualization with a predefined configuration.
- RTAB-Map SLAM system using a RealSense D400 camera.
- Fast Mapping node with specific parameters for projection and robot configuration.
- RealSense2 camera driver with depth alignment enabled.

Each node is launched with specific timing delays to ensure proper startup order.
"""

import os

from ament_index_python.packages import get_package_share_directory

import launch_ros.actions

import launch
import launch.actions
from launch.actions.timer_action import TimerAction
import launch.substitutions


fast_mapping_parameters = [
    {
        'projection_min_z': 0.2,
        'projection_max_z': 0.5,
        'max_depth_range': 3.0,
        'noise_factor': 0.08,
        'robot_radius': 0.2,
    }
]


def generate_launch_description():
    """
    Generates a ROS 2 launch description for the Fast Mapping application.
    This launch description includes the following components:
    - RViz2: Visualization tool configured with a specific RViz config file.
    - SLAM (RTAB-Map): Launches the RTAB-Map SLAM system using a RealSense D400 launch file.
    - Fast Mapping Node: Launches the Fast Mapping node with specified parameters.
    - RealSense Camera: Launches the RealSense camera driver with depth alignment enabled.
    Node startup is staggered using timers to ensure proper initialization order:
    - RViz2 starts immediately.
    - RTAB-Map launches after 10 seconds.
    - Fast Mapping node launches after 12 seconds.
    - RealSense camera launches after 15 seconds.
    Returns:
        launch.LaunchDescription: The composed launch description containing all nodes and timers.
    """

    # ================== rviz2 ===============
    package_share_directory = get_package_share_directory('fast_mapping')
    rviz_config_dir = os.path.join(
        package_share_directory, 'launch', 'config', 'fastmapping_tutorial_config.rviz'
    )
    rviz2_launch = launch_ros.actions.Node(
        name='rviz', package='rviz2', executable='rviz2', arguments=['-d', rviz_config_dir]
    )

    # ============== SLAM ====================
    dir_path = get_package_share_directory('rtabmap_examples')
    rtabmap_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
            dir_path + '/launch/realsense_d400.launch.py'
        )
    )

    # =================== FastMapping ===================
    fm_launch = launch_ros.actions.Node(
        # node initialization as before
        name='fast_mapping',
        package='fast_mapping',
        executable='fast_mapping_node',
        output='screen',
        parameters=fast_mapping_parameters,
    )

    # =================== Camera ===================
    rs_dir_path = get_package_share_directory('realsense2_camera')
    rs_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
            rs_dir_path + '/launch/rs_launch.py'
        ),
        launch_arguments={'align_depth.enable': 'true', 'camera_namespace': '/'}.items(),
    )
    # ================== Node startup timings ===============
    launch_rtabmap_after_timer = TimerAction(period=10.0, actions=[rtabmap_launch])
    launch_fm_after_timer = TimerAction(period=12.0, actions=[fm_launch])
    launch_rs_after_timer = TimerAction(period=15.0, actions=[rs_launch])

    return launch.LaunchDescription(
        [rviz2_launch, launch_rtabmap_after_timer, launch_fm_after_timer, launch_rs_after_timer]
    )
