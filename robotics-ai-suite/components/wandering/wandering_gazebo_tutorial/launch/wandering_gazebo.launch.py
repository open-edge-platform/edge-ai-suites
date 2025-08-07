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
from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription,
                            SetEnvironmentVariable, Shutdown,
                            TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.substitutions import PathJoinSubstitution, TextSubstitution
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    # Get the launch directory
    bringup_dir = get_package_share_directory('nav2_bringup')
    turtlebot3_dir = get_package_share_directory('turtlebot3_gazebo')
    rtabmap_dir = get_package_share_directory('rtabmap_demos')
    wandering_dir = get_package_share_directory('wandering_app')

    use_sim_time = LaunchConfiguration('use_sim_time')
    use_rviz = LaunchConfiguration('use_rviz')
    params_file = LaunchConfiguration('params_file')
    log_level = LaunchConfiguration('log_level')
    world = LaunchConfiguration('world')

    # Create our own temporary YAML files that include substitutions
    param_substitutions = {
        'use_sim_time': use_sim_time,
    }

    stdout_linebuf_envvar = SetEnvironmentVariable(
        'RCUTILS_LOGGING_BUFFERED_STREAM', '1')
    turtlebot3_model_envvar = SetEnvironmentVariable(
        'TURTLEBOT3_MODEL', 'waffle')
    gazebo_model_path_envvar = SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH', os.path.join(turtlebot3_dir, 'models'))

    declare_use_sim_time_cmd = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true')

    declare_use_rviz_cmd = DeclareLaunchArgument(
        'use_rviz',
        default_value='true',
        description='Start navigation configured RViz')

    # This parameter is used by gazebo_ros gzclient.launch.py started
    # by turtlebot3_gazebo turtlebot3_world.launch.py.  It's
    # redeclared here to change its default value to 'true', so that
    # the launch script exits when the Gazebo client is closed.
    declare_gui_required_cmd = DeclareLaunchArgument(
        'gui_required',
        default_value='true',
        description='Terminate launch script when Gazebo client exits')

    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(bringup_dir, 'params', 'nav2_params.yaml'),
        description='Full path to the ROS2 parameters file to use for all launched nodes')

    declare_log_level_cmd = DeclareLaunchArgument(
        'log_level', default_value='info',
        description='log level')

    declare_world_cmd = DeclareLaunchArgument(
        'world', default_value='world',
        description='Turtlebot3 world')

    load_nodes = GroupAction(
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource([
                    PathJoinSubstitution([turtlebot3_dir, 'launch',
                                          PythonExpression(['"turtlebot3_" + str("', world, '") + ".launch.py"'])])]),
                launch_arguments=param_substitutions.items()),
            # delay the start of the other nodes to give time to Gazebo to load
            TimerAction(
                period=1.5,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(rtabmap_dir, 'launch', 'turtlebot3/turtlebot3_scan.launch.py')),
                        launch_arguments=param_substitutions.items())]
            ),
            TimerAction(
                period=2.5,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(bringup_dir, 'launch', 'navigation_launch.py')),
                        launch_arguments=param_substitutions.items())]
            ),
            TimerAction(
                period=3.5,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(bringup_dir, 'launch', 'rviz_launch.py')),
                        condition=IfCondition(use_rviz),
                        launch_arguments=param_substitutions.items())]
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
                        arguments=['--ros-args', '--log-level', log_level])]
            ),
        ]
    )

    # Create the launch description and populate
    ld = LaunchDescription()

    # Set environment variables
    ld.add_action(stdout_linebuf_envvar)
    ld.add_action(turtlebot3_model_envvar)
    ld.add_action(gazebo_model_path_envvar)

    # Declare the launch options
    ld.add_action(declare_use_sim_time_cmd)
    ld.add_action(declare_use_rviz_cmd)
    ld.add_action(declare_gui_required_cmd)
    ld.add_action(declare_params_file_cmd)
    ld.add_action(declare_log_level_cmd)
    ld.add_action(declare_world_cmd)

    # Add the actions to launch all of the navigation nodes
    ld.add_action(load_nodes)

    return ld
