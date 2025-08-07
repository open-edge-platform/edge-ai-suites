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
import launch.substitutions
import launch_ros.actions
import os
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, OpaqueFunction

from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution, PythonExpression

from ament_index_python.packages import get_package_share_directory

def launch_setup(context, *args, **kwargs):

    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    staticMotionControllerPackageName="rvc_static_motion_controller_use_case"

    robot_ip = LaunchConfiguration("robot_ip", default="127.0.0.1")
    robot_ip_arg = context.perform_substitution(robot_ip)
    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI_arg = context.perform_substitution(whoAmIConf)
    launch_rviz = LaunchConfiguration("launch_rviz")
    launch_rviz_arg = context.perform_substitution(launch_rviz)

    
    launch_args = {
                'robot_ip': robot_ip_arg,
                'whoAmI': whoAmI_arg, 
         }


    rvc_static_motion_controller_use_case_node = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                launch_ros.substitutions.FindPackageShare(staticMotionControllerPackageName),
                'launch',
                'static_demo_launch.py'
            ])
        ]),
        launch_arguments=launch_args.items(),
    )

    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                launch_ros.substitutions.FindPackageShare(staticMotionControllerPackageName),
                'launch',
                'rviz2_launch.py'
            ])
        ]),
        launch_arguments=launch_args.items(),
    )

    nodes_to_start = [
            rvc_static_motion_controller_use_case_node,
        ]
    
    if (launch_rviz_arg == "true"):
        nodes_to_start.append(rviz)

    return nodes_to_start

def generate_launch_description():


    declared_arguments = []

    declared_arguments.append(
        DeclareLaunchArgument( 
            "robot_ip", 
            description="IP address by which the robot can be reached.",
            default_value="127.0.0.1"
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument(
            "whoAmI", 
            default_value="true",
            description="Unique IPC ID, starts from 0, increasing "
        )
    )
    
    declared_arguments.append(
        DeclareLaunchArgument( 
            "launch_rviz", 
            description="Enable/disable displaying rviz",
            default_value="1"
        )
    )
    
 
    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)] )
