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

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LOG_LEVEL = 'warn'

def generate_launch_description():

    ld = LaunchDescription()

    package_path = get_package_share_directory('robot_config')
    launch_dir = os.path.join(package_path, 'launch')

    launch_stack = LaunchConfiguration('launch_stack')
    declare_launch_stack = DeclareLaunchArgument('launch_stack', default_value='true',
                                         description='Enable/Disable Nav2 launch')
    ld.add_action(declare_launch_stack)

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    declare_use_sim_time = DeclareLaunchArgument(
        name='use_sim_time', default_value='true', description='Use simulator time'
    )
    ld.add_action(declare_use_sim_time)

    # Gazebo Environment Launch
    gazebo_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_dir, 'gazebo.launch.py')),
        launch_arguments={ 'use_sim_time': use_sim_time
                          }.items()
                        )
    ld.add_action(gazebo_launch_cmd)

    conveyorbelt_spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-file', os.path.join(package_path, 'urdf', 'conveyor_belt', 'model.sdf'),
            '-entity', 'conveyor_belt',
            '-x', '0.83',
            '-y', '-1.3',
            '-z', '0.0',
            '-unpause',
            '--ros-args', '--log-level', LOG_LEVEL,
        ],
        output='screen',
    )
    ld.add_action(conveyorbelt_spawn_entity)

    cube_event = TimerAction(
            period=10.0,
            actions=[
                Node(
                package='robot_config',
                executable='cube_controller.py',
                output='screen',
                arguments=[
                    '--ros-args', '--log-level', LOG_LEVEL,
                ]),
                Node(
                package="robot_config",
                executable='arm1_controller.py',
                output="screen",
                arguments=[
                    "--ros-args", "--log-level", LOG_LEVEL,
                ])
                ]
        )
    ld.add_action(cube_event)
    amr_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_dir, 'amr.launch.py')),
        launch_arguments={ 'amr_name': 'amr1',
                           'x_pos': '-0.1',
                           'y_pos': '-0.3',
                           'yaw': '3.14159',
                           'use_sim_time': use_sim_time,
                           'launch_stack': launch_stack,
                          }.items()
                        )

    ld.add_action(amr_launch_cmd)

    map_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_dir, 'map.launch.py')),
            launch_arguments={ 'use_sim_time': use_sim_time,
                         }.items()
                        )

    ld.add_action(map_launch_cmd)

    arm1_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_dir, 'arm.launch.py')),
        launch_arguments={ 'arm_name': 'arm1',
                           'x_pos': '0.18',
                           'y_pos': '0.0',
                           'yaw': '0.0',
                           'pedestal_height': '0.16',
                           'use_sim_time': use_sim_time,
                           'launch_stack': launch_stack,
                           'wait_on': 'topic /amr1/cmd_vel'
                          }.items()
                        )
    ld.add_action(arm1_launch_cmd)

    arm2_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_dir, 'arm.launch.py')),
        launch_arguments={ 'arm_name': 'arm2',
                           'x_pos': '-4.0',
                           'y_pos': '0.0',
                           'yaw': '0.0',
                           'use_sim_time': use_sim_time,
                           'launch_stack': launch_stack,
                           'wait_on': 'action /arm1/arm_controller/follow_joint_trajectory'
                          }.items()
                        )
    ld.add_action(arm2_launch_cmd)

    return ld

