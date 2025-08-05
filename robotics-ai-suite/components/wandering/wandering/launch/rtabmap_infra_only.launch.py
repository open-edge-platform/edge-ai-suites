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


# Requirements:
#   A realsense D400 series
#   Install realsense2 ros2 package (refactor branch)
# Example:
#   $ ros2 launch realsense2_camera rs_launch.py align_depth:=true
#   $ ros2 launch rtabmap_ros realsense_d400.launch.py

from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():

    parameters = [{
          'frame_id': 'base_link',
          'subscribe_depth': False,
          'subscribe_scan': False,
          'subscribe_stereo': True,
          'stereo_to_depth': False,
          'wait_imu_to_init': True,
          'imu_topic': '/rtabmap/imu',
          'approx_sync': True,
          'publish_null_when_lost': False,
          'Odom/ResetCountdown': '1',
          'Odom/AlignWithGround': 'false',
          'Grid/RangeMin': '0.1',
          'Grid/RangeMax': '5.0',
          'Grid/FromDepth': 'true',
          'Grid/NoiseFilteringRadius': '0',
          'Grid/3D': 'false',
          'Grid/RayTracing': 'true',
          'Grid/MaxGroundHeight': '0.1',
          'Grid/MaxObstacleHeight': '2.0',
          'Grid/NormalsSegmentation': 'false',
          'Grid/MaxGroundAngle': '45',
          'Grid/FootprintHeight': '0.57',
          'Grid/FootprintLength': '0.354',
          'Grid/FootprintWidth': '0.354'},
    ]
    remappings = [
          ('left/camera_info', '/camera/infra1/camera_info'),
          ('right/camera_info', '/camera/infra2/camera_info'),
          ('left/image_rect', '/camera/infra1/image_rect_raw'),
          ('right/image_rect', '/camera/infra2/image_rect_raw'),
          ('scan', '/scan')
    ]

    return LaunchDescription([
        # Set env var to print messages to stdout immediately
        SetEnvironmentVariable('RCUTILS_CONSOLE_STDOUT_LINE_BUFFERED', '0'),

        # Nodes to launch
        Node(
            package='rtabmap_ros', node_executable='rgbd_odometry', output='screen',
            parameters=parameters,
            remappings=remappings),

        Node(
            package='rtabmap_ros', node_executable='rtabmap', output='screen',
            parameters=parameters,
            remappings=remappings,
            arguments=['-d']),
    ])
