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

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import os

def generate_launch_description():

    localization = LaunchConfiguration('localization')
    params_file = LaunchConfiguration('params_file')
    urdf_file = LaunchConfiguration('urdf_file')

    remappings=[
          ('imu', [LaunchConfiguration('irobot_ns'), '/imu']),
          ('rgbd_image','/camera/rgbd_image')]

    remapping_rs=[
          ('rgbd_image','/camera/rgbd_image'),
          ('rgb/image', '/camera/color/image_raw'),
          ('rgb/camera_info', '/camera/color/camera_info'),
          ('depth/image', '/camera/aligned_depth_to_color/image_raw')]


    robot_desc = ParameterValue(Command(['xacro ', urdf_file]), value_type=str)
    rsp_params = {'robot_description': robot_desc}

    return LaunchDescription([

        DeclareLaunchArgument(
            'qos', default_value='2',
            description='QoS used for input sensor topics'),

        DeclareLaunchArgument(
            'localization', default_value='false',
            description='Launch in localization mode.'),

        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(get_package_share_directory('wandering_irobot_tutorial'), 'params', 'irobot_nav.param.yaml'),
            description='Full path to the ROS2 parameters file to use for all launched nodes'),

        DeclareLaunchArgument(
            'urdf_file',
            default_value=os.path.join(get_package_share_directory('wandering_irobot_tutorial'), 'urdf', 'create3.urdf.xacro'),
            description="Full path to the robot URDF file"),

        # Nodes to launch
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[rsp_params, {'use_sim_time':False}, params_file],
            ),

        # SLAM mode:
        Node(
            package='rtabmap_sync', executable='rgbd_sync', remappings=remapping_rs,
            parameters=[{'approx_sync' : False }]
            ),

        Node(
            condition=UnlessCondition(localization),
            package='rtabmap_slam', executable='rtabmap', output='screen',
            parameters=[params_file],
            remappings=remappings,
            arguments=['-d']), # This will delete the previous database (~/.ros/rtabmap.db)

        # Localization mode:
        Node(
            condition=IfCondition(localization),
            package='rtabmap_slam', executable='rtabmap', output='screen',
            parameters=[params_file,
              {'Mem/IncrementalMemory':'False',
               'Mem/InitWMWithAllNodes':'True'}],
            remappings=remappings),
   ])
