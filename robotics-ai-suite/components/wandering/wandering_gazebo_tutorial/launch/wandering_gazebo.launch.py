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

"""Launch file for Gazebo-based TurtleBot3 wandering navigation tutorial."""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    """
    Generate launch description for Gazebo TurtleBot3 wandering navigation.

    Returns
    -------
    LaunchDescription
        Launch configuration with all navigation components.

    """
    # Get the launch directory
    bringup_dir = get_package_share_directory('nav2_bringup')
    turtlebot3_dir = get_package_share_directory('turtlebot3_gazebo')
    rtabmap_dir = get_package_share_directory('rtabmap_demos')
    gazebo_tutorial_dir = get_package_share_directory('wandering_gazebo_tutorial')

    # Select params file based on ROS distribution
    ros_distro = os.environ.get('ROS_DISTRO', 'jazzy')
    if ros_distro == 'humble':
        default_params_file = os.path.join(bringup_dir, 'params', 'nav2_params.yaml')
    else:
        default_params_file = os.path.join(gazebo_tutorial_dir, 'params', 'nav2_params_jazzy.yaml')

    # Launch configurations
    use_sim_time = LaunchConfiguration('use_sim_time')
    use_rviz = LaunchConfiguration('use_rviz')
    log_level = LaunchConfiguration('log_level')
    world = LaunchConfiguration('world')
    params_file = LaunchConfiguration('params_file')

    # Create the launch description and add environment variables
    ld = LaunchDescription()
    ld.add_action(SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'))
    ld.add_action(SetEnvironmentVariable('TURTLEBOT3_MODEL', 'waffle'))
    ld.add_action(
        SetEnvironmentVariable('GAZEBO_MODEL_PATH', os.path.join(turtlebot3_dir, 'models'))
    )

    # Add launch argument declarations
    ld.add_action(
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true',
        )
    )
    ld.add_action(
        DeclareLaunchArgument(
            'use_rviz', default_value='true', description='Start navigation configured RViz'
        )
    )
    ld.add_action(
        DeclareLaunchArgument(
            'gui_required',
            default_value='true',
            description='Terminate launch script when Gazebo client exits',
        )
    )
    ld.add_action(
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='Full path to the ROS2 parameters file to use for all nodes',
        )
    )
    ld.add_action(
        DeclareLaunchArgument('log_level', default_value='info', description='log level')
    )
    ld.add_action(
        DeclareLaunchArgument('world', default_value='world', description='Turtlebot3 world')
    )

    # Create substitution dictionaries for launch arguments
    param_substitutions = {'use_sim_time': use_sim_time}
    nav_launch_arguments = {
        'use_sim_time': use_sim_time,
        'params_file': params_file,
    }

    # Create the load_nodes action with all launch components
    ld.add_action(
        GroupAction(
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        [
                            PathJoinSubstitution(
                                [
                                    turtlebot3_dir,
                                    'launch',
                                    PythonExpression(
                                        ['"turtlebot3_" + str("', world, '") + ".launch.py"']
                                    ),
                                ]
                            )
                        ]
                    ),
                    launch_arguments=param_substitutions.items(),
                ),
                # delay the start of the other nodes to give time to Gazebo to load
                TimerAction(
                    period=1.5,
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                os.path.join(
                                    rtabmap_dir, 'launch', 'turtlebot3/turtlebot3_scan.launch.py'
                                )
                            ),
                            launch_arguments=param_substitutions.items(),
                        )
                    ],
                ),
                TimerAction(
                    period=2.5,
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                os.path.join(bringup_dir, 'launch', 'navigation_launch.py')
                            ),
                            launch_arguments=nav_launch_arguments.items(),
                        )
                    ],
                ),
                TimerAction(
                    period=3.5,
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                os.path.join(bringup_dir, 'launch', 'rviz_launch.py')
                            ),
                            condition=IfCondition(use_rviz),
                            launch_arguments=param_substitutions.items(),
                        )
                    ],
                ),
                TimerAction(
                    period=4.0,
                    actions=[
                        Node(
                            package='wandering_app',
                            executable='wandering',
                            name='wandering',
                            output='screen',
                            parameters=[param_substitutions],
                            arguments=['--ros-args', '--log-level', log_level],
                        )
                    ],
                ),
            ]
        )
    )

    return ld
