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

# Description: Helper launch file to spawn AMR in Gazebo separated by namespace
# Example usage:
#
#    gazebo_launch_cmd = IncludeLaunchDescription(
#        PythonLaunchDescriptionSource(
#            os.path.join(robot_config_launch_dir, 'gazebo.launch.py')),
#        launch_arguments={ 'use_sim_time': 'true',
#                           'world': os.path.join(
#                                        package_path,
#                                        'worlds',
#                                        'warehouse.world',
#                                    )
#                          }.items()
#                        )
#    ld.add_action(gazebo_launch_cmd)

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    package_path = get_package_share_directory('robot_config')
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world = LaunchConfiguration('world')

    # Default world file
    declare_world_path = DeclareLaunchArgument(
        'world',
        default_value=os.path.join(
            package_path,
            'worlds',
            'no_roof_small_warehouse',
            'no_roof_small_warehouse.world',
        ),
        description='Full path to world model file to load',
    )
    ld.add_action(declare_world_path)

    # Gazebo Harmonic server + client in one
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': [world, ' -v 4'],
            'on_exit_shutdown': 'true'
        }.items(),
    )
    ld.add_action(gzserver_cmd)

    # Clock Bridge (global)
    gz_ros_bridge_clock = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
    )
    ld.add_action(gz_ros_bridge_clock)

    # TF Bridge (global)
    gz_ros_bridge_tf = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
            '/tf_static@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V'
        ],
        output='screen',
    )
    ld.add_action(gz_ros_bridge_tf)

    # Entity State Bridge - for entity_location function (via services)
    gz_ros_bridge_entity = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/world/default/get_entity_state@gazebo_msgs/srv/GetEntityState',
            '/world/default/set_entity_state@gazebo_msgs/srv/SetEntityState',
        ],
        output='screen',
    )
    ld.add_action(gz_ros_bridge_entity)

    return ld
