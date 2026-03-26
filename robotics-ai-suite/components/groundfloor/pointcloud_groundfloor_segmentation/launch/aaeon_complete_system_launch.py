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

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.actions import (
    DeclareLaunchArgument,
    TimerAction,
    SetEnvironmentVariable
)
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    EnvironmentVariable,
    PythonExpression,
    PathJoinSubstitution
)


def generate_launch_description():

    ros_distro = EnvironmentVariable('ROS_DISTRO')

    with_aaeon = LaunchConfiguration('with_aaeon')
    with_twist_bridge = LaunchConfiguration('with_twist_bridge')

    # Determine cmd_vel topic based on ROS distro
    cmd_vel_topic = PythonExpression([
        "'cmd_vel_twist' if '", ros_distro, "' != 'humble' else 'cmd_vel'"
    ])

    aaeon_params_file = PathJoinSubstitution([
        FindPackageShare('ros2_amr_interface'),
        'params',
        'aaeon_node_params.yaml'
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'with_aaeon',
            default_value='True',
            description='Launch AAEON interface'
        ),
        DeclareLaunchArgument(
            'with_twist_bridge',
            default_value='True',
            description='Launch twist bridge'
        ),

        SetEnvironmentVariable(
            name='AAEON_NODE_CONFIG_FILE',
            value=PathJoinSubstitution([
                FindPackageShare('ros2_amr_interface'),
                'params',
                'aaeon_node_params.yaml'
            ])
        ),

        # AAEON AMR Interface Node
        Node(
            condition=IfCondition(with_aaeon),
            package='ros2_amr_interface',
            executable='amr_interface_node',
            name='amr_interface_node',
            output='screen',
            parameters=[aaeon_params_file],
            remappings=[
                ('/amr/cmd_vel', cmd_vel_topic),
                ('/amr/battery', '/sensors/battery_state')
            ]
        ),

        # Twist Bridge Node
        TimerAction(
            period=3.0,
            actions=[
                Node(
                    condition=IfCondition(with_twist_bridge),
                    package='pointcloud_groundfloor_segmentation',
                    executable='twist_bridge.py',
                    name='twist_bridge',
                    output='screen'
                )
            ]
        ),

        # TF: base_link -> camera_link
        TimerAction(
            period=7.0,
            actions=[
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='static_tf_base_to_camera',
                    arguments=['0', '0', '0.1', '0', '0', '0', '1', 'base_link', 'camera_link'],
                    output='screen'
                )
            ]
        ),

        # TF: map -> odom
        TimerAction(
            period=8.0,
            actions=[
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='static_tf_map_to_odom',
                    arguments=['0', '0', '0', '0', '0', '0', '1', 'map', 'odom'],
                    output='screen'
                )
            ]
        ),
    ])
