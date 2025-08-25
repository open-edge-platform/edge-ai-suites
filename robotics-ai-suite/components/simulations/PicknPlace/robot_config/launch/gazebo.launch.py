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
import yaml
import xacro

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit, OnExecutionComplete
from launch.launch_context import LaunchContext
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch.substitutions.path_join_substitution import PathJoinSubstitution
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml

from robot_config import utils



LOG_LEVEL = "info"

def generate_launch_description():

    ld = LaunchDescription()
   
    # ros support github link -> https://github.com/bponsler/ros2-support
    package_path = get_package_share_directory("robot_config")
    
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    world = LaunchConfiguration("world")

    # Default world file
    declare_world_path = DeclareLaunchArgument(
        "world",
        default_value=os.path.join(
            package_path,
            "worlds",
            "no_roof_small_warehouse",
            "no_roof_small_warehouse.world",
        ),
        description="Full path to world model file to load",
    )
    ld.add_action(declare_world_path)

    gazebo_server = ExecuteProcess(
        cmd=[
            "gzserver",
            "--verbose",
            "-u",
            "-s", "libgazebo_ros_factory.so",
            "-s", "libgazebo_ros_init.so",
            "-s", "libgazebo_ros_namespace.so",
            world,
            "--ros-args", "--log-level", LOG_LEVEL,
        ],
        output="screen",
    )
    ld.add_action(gazebo_server)

    gazebo_client = ExecuteProcess(cmd=["gzclient"], output="screen")
    ld.add_action(gazebo_client)
   
    return ld

