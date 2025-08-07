#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import datetime
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def set_logging_dir(new_log_dir):
    """Set ROS2 logging directory

    ROS2 Rolling adds action launch_ros.actions.SetROSLogDir for
    setting the logging directory for all ROS nodes from a launch file.

    This function is borrowed from rolling launch_ros.actions.set_ros_log_dir.py
    """
    from rclpy.logging import get_logging_directory

    current_rclpy_logging_directory = get_logging_directory()
    # Prefer ROS_LOG_DIR over what rclpy reports, but fall back to that if not set.
    current_log_dir = os.environ.get('ROS_LOG_DIR', current_rclpy_logging_directory)
    # If new_log_dir is abs, then current_log_dir will be truncated and not used.
    log_dir = os.path.join(current_log_dir, new_log_dir)
    assert os.path.isabs(log_dir)
    os.environ['ROS_LOG_DIR'] = log_dir


def generate_launch_description():
    nav2_param_file = os.path.join(get_package_share_directory('wandering_irobot_tutorial'), 'params', 'irobot_nav.param.yaml')
    twist_param_file = os.path.join(get_package_share_directory('wandering_irobot_tutorial'), 'params', 'twist-mux-params.yaml')
    rviz_config_file = os.path.join(get_package_share_directory('wandering_irobot_tutorial'), 'rviz', 'wandering-irobot-tutorial.rviz')

    use_rviz = LaunchConfiguration('use_rviz')
    params_file = LaunchConfiguration('params_file')
    irobot_ns = LaunchConfiguration('irobot_ns')
    lidar_type = LaunchConfiguration('lidar_type')
    use_joystick = LaunchConfiguration('use_joystick')

    set_logging_dir(f"wandering_irobot-{datetime.datetime.now(datetime.timezone.utc).isoformat()}")

    declare_use_rviz_cmd = DeclareLaunchArgument(
        'use_rviz',
        default_value='true',
        description='Start navigation configured RViz')

    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        default_value=nav2_param_file,
        description='Full path to the ROS2 parameters file to use for all launched nodes')

    declare_rviz_config_cmd = DeclareLaunchArgument(
        'rviz_config',
        default_value=rviz_config_file,
        description='Full path to the RViz configuration file')

    declare_irobot_ns_cmd = DeclareLaunchArgument(
        'irobot_ns',
        description='iRobot create 3 namespace, set in the web interface of the robot')

    declare_lidar_type_cmd = DeclareLaunchArgument(
        'lidar_type',
        default_value='a2m8',
        description='RPLidar model type: a2m8 or a3.')

    declare_lidar_serial_cmd = DeclareLaunchArgument(
        'lidar_serial',
        default_value='/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0',
        description='RPLidar serial port.')

    declare_use_joystick_cmd = DeclareLaunchArgument(
        'use_joystick',
        default_value='false',
        description='Start nodes for joystick control')

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('realsense2_camera'), 'launch', 'rs_launch.py')),
        launch_arguments={
            'enable_infra1': 'true',
            'align_depth.enable': 'true',
            'enable_sync': 'true',
            'init_reset': 'true',
            'pointcloud.enable': 'true',
            'camera_namespace': '/'
        }.items()
    )

    rplidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([get_package_share_directory('rplidar_ros'),
                                  'launch', 'rplidar_']),
            lidar_type,
            '_launch.py'
        ]),
        launch_arguments={
            'serial_port': LaunchConfiguration('lidar_serial'),
            'frame_id': 'lidar_link',
        }.items(),
    )

    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        remappings=[('cmd_vel_out', [irobot_ns, '/cmd_vel'])],
        parameters=[
            twist_param_file
        ]
    )

    joy_node = Node(
        package='joy',
        executable='joy_node',
        condition=IfCondition(use_joystick)
    )

    teleop_twist_joy_node = Node(
        package='teleop_twist_joy',
        executable='teleop_node',
        remappings=[('cmd_vel', '/joy_vel')],
        parameters=[
            twist_param_file
        ],
        condition=IfCondition(use_joystick)
    )

    # Topics from robot namespace that are needed in the root
    # namespace
    relay_tf_node = Node(
        name='relay_tf',
        package='topic_tools',
        executable='relay',
        arguments=[[irobot_ns, '/tf'], '/tf'],
    )

    relay_tf_static_node = Node(
        name='relay_tf_static',
        package='topic_tools',
        executable='relay',
        arguments=[[irobot_ns, '/tf_static'], '/tf_static'],
    )

    relay_odom_node = Node(
        name='relay_odom',
        package='topic_tools',
        executable='relay',
        arguments=[[irobot_ns, '/odom'], '/odom'],
    )

    groundfloor_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('pointcloud_groundfloor_segmentation'), 'launch', 'realsense_groundfloor_segmentation_launch.py')),
        launch_arguments={
            'node_params_file': params_file,
        }.items()
    )

    rtabmap_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('wandering_irobot_tutorial'), 'launch', 'rtabmap.launch.py')),
        launch_arguments={'localization': 'false'}.items()
    )

    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')),
        launch_arguments={'params_file': params_file}.items()
    )

    rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'rviz_launch.py')),
        condition=IfCondition(use_rviz)
    )

    wandering_app_node = Node(
        package='wandering_app',
        executable='wandering',
        parameters=[params_file]
    )

    return LaunchDescription([
        declare_params_file_cmd,
        declare_use_rviz_cmd,
        declare_rviz_config_cmd,
        declare_irobot_ns_cmd,
        declare_lidar_type_cmd,
        declare_lidar_serial_cmd,
        declare_use_joystick_cmd,
        relay_tf_node,
        relay_tf_static_node,
        relay_odom_node,
        twist_mux_node,
        realsense_launch,
        rplidar_launch,
        groundfloor_launch,
        rtabmap_launch,
        TimerAction(
            period=4.0,
            actions=[
                navigation_launch,
            ]
        ),
        rviz_launch,
        joy_node,
        teleop_twist_joy_node,
        wandering_app_node
    ])
