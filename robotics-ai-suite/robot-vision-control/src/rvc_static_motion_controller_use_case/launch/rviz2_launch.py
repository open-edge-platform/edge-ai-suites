# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

from launch import LaunchContext, LaunchDescription
import launch.actions
#import launch.actions.LogInfo
import launch.substitutions
import launch_ros.actions
import os
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch.actions import LogInfo
from launch.actions import IncludeLaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution, PythonExpression


from ament_index_python.packages import get_package_share_directory
from pprint import pprint

from launch_ros.actions import Node

from launch import invalid_launch_file_error
import sys

import ast

from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch.actions import ExecuteProcess, LogInfo, OpaqueFunction

def launch_setup(context, *args, **kwargs):

    whoAmIConf = LaunchConfiguration("namespace",default="ipc")


    os.environ['DISPLAY'] = ':0'
    os.environ['LIBGL_ALWAYS_INDIRECT'] = "0"
    packageName="rvc_static_motion_controller_use_case"
    robot_demo_main_dir = get_package_share_directory(packageName)

    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI= context.perform_substitution(whoAmIConf)
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        #name="rviz2",
        namespace=whoAmI,
        output="both",
        arguments=["-d" , robot_demo_main_dir + "/config/robot_demo_config_qt.rviz" ],
    )

    return [rviz_node]

def generate_launch_description():
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument( 
            "namespace", 
            description="Namespace for the whole perception composition. has to match with the motion controller",
            default_value="ipc"
        )
    )

    return LaunchDescription( declared_arguments + [OpaqueFunction(function=launch_setup) ])
