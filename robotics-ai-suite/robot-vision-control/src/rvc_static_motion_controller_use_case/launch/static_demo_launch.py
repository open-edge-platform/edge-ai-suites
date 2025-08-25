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
from launch.actions import SetLaunchConfiguration
from launch.actions import (DeclareLaunchArgument, EmitEvent, ExecuteProcess,
                            LogInfo, RegisterEventHandler, TimerAction)
from launch.conditions import IfCondition
from launch.event_handlers import (OnExecutionComplete, OnProcessExit,
                                OnProcessIO, OnProcessStart, OnShutdown)
from launch.events import Shutdown
from launch.substitutions import (EnvironmentVariable, FindExecutable,
                                LaunchConfiguration, LocalSubstitution,
                                PythonExpression)

from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch.actions import GroupAction
from launch_ros.actions import PushRosNamespace, SetRemap

from ament_index_python.packages import get_package_share_directory
from pprint import pprint

from launch_ros.actions import Node


import ast
from launch_ros.substitutions import FindPackageShare
import yaml
from ament_index_python.packages import get_package_share_directory
from launch.conditions import UnlessCondition

import sys
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
from launch.actions import OpaqueFunction

packageName = "rvc_static_motion_controller_use_case"

def load_yaml(package_path, file_path):
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path) as file:
            return yaml.safe_load(file)
    except OSError:  # parent of IOError, OSError *and* WindowsError where available
        print("FATAL: File not found: " + absolute_file_path )
        return None


def launch_setup(context, *args, **kwargs):
    robot_demo_main_dir = get_package_share_directory(packageName)
    # UR specific arguments
    launch_rviz_arg = LaunchConfiguration( "launch_rviz", default="true")

    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI_arg = context.perform_substitution(whoAmIConf)

    fullnamespacecontrollermanager = "/"+ whoAmI_arg + "/controller_manager"

    robot_ip = LaunchConfiguration("robot_ip", default="10.11.12.99")


    robot_description_filename = os.path.join(
        get_package_share_directory(packageName), "urdf/composite_u5_robotiq_2f_gripper.urdf")
    
    with open(robot_description_filename, 'r') as infp:
        robot_description_content = infp.read()

    robot_description = {"robot_description": robot_description_content}

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        namespace=whoAmI_arg,
        parameters=[robot_description],
    )

    world_robot_state_publisher_node = Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            namespace=whoAmI_arg,
            arguments = ['0', '0', '0', '0', '0', '0', 'world', 'base_link'],
            output = 'own_log'
    )

    camera_xacro_path = robot_demo_main_dir + '/cameraurdf/d415camera' + whoAmI_arg + '.xacro'
    camera_robot_state_publisher_node = Node(
            name='camera_robot_state_publisher',
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=whoAmI_arg,
            parameters=[ 
                {
                    'robot_description': 
                        Command(
                            [
                                'xacro',' ', camera_xacro_path, 
                                ' name:=camera', whoAmI_arg,
                            ]
                        ), 
                    'whoAmI': whoAmI_arg, 
                    'name': 'camera'+whoAmI_arg 
                }
            ],
            #parameters=[ {'robot_description': Command(['xacro',' ', camera_xacro_path]), 'whoAmI': whoAmI_arg }],
            remappings=[ ('robot_description' , 'rs_description' )],
            output='own_log'
    )

    robot_demo_main_config = robot_demo_main_dir + "/config/waypoints.yaml"

    ## ros2 run robot_demo_main robot_demo_main --ros-args --params-file install/robot_demo_main/share/robot_demo_main/config/waypoints.yaml
    robot_demo_main_node = Node(
            package=packageName,
            executable=packageName,
            #output="screen",
            namespace=whoAmI_arg,
            parameters=[
                robot_description,
                robot_demo_main_dir + "/config/waypoints.yaml",
                robot_demo_main_dir + "/config/parameters.yaml",
                {"robot_ip": robot_ip},
            ],
    )
    nodes_to_start = [
            robot_state_publisher_node,
            #marker_server_node,
            world_robot_state_publisher_node,
            camera_robot_state_publisher_node,
            robot_demo_main_node,
        ]
    return nodes_to_start

def generate_launch_description():

    robot_demo_main_dir = get_package_share_directory(packageName)

    declared_arguments = []
    # UR specific arguments
    declared_arguments.append(
        DeclareLaunchArgument("motion_controller", default_value="servo", description="controller/motion controller types. values linear_controller, servo.")
    )

    robot_ip_yaml = load_yaml(robot_demo_main_dir, "config/robot_ip.yaml")
    declared_arguments.append(
        DeclareLaunchArgument( 
            "robot_ip", 
            description="IP address by which the robot can be reached.",
            default_value=robot_ip_yaml
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument(
            "whoAmI", 
            default_value="0",
            description="Unique IPC ID, starts from 0, increasing "
        )
    )

    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)] )
