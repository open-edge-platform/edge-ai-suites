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
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node
import os

def generate_launch_description():

    localization = LaunchConfiguration('localization')
    params_file = LaunchConfiguration('params_file')

    remappings=[
          ('rgbd_image','/sensors/camera_0/camera/rgbd_image')]

    remapping_rs=[
          ('rgbd_image',      '/sensors/camera_0/camera/rgbd_image'),
          ('rgb/image',       '/sensors/camera_0/camera/color/image_raw'),
          ('rgb/camera_info', '/sensors/camera_0/camera/color/camera_info'),
          ('depth/image',     '/sensors/camera_0/camera/aligned_depth_to_color/image_raw')]

    return LaunchDescription([

        DeclareLaunchArgument(
            'qos', default_value='2',
            description='QoS used for input sensor topics'),

        DeclareLaunchArgument(
            'localization', default_value='false',
            description='Launch in localization mode.'),

        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(get_package_share_directory('wandering_jackal_tutorial'), 'params', 'jackal_nav.param.yaml'),
            description='Full path to the ROS2 parameters file to use for all launched nodes'),

        # SLAM node:
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

        # Localization node:
        Node(
            condition=IfCondition(localization),
            package='rtabmap_slam', executable='rtabmap', output='screen',
            parameters=[params_file,
              {'Mem/IncrementalMemory':'False',
               'Mem/InitWMWithAllNodes':'True'}],
            remappings=remappings),
   ])
