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

import os
from ament_index_python.packages import get_package_share_directory

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration


def launch_setup(context, *args, **kwargs):

    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI= context.perform_substitution(whoAmIConf)

    mySerialNumberConf = LaunchConfiguration("rs_serial")
    mySerialNumber= context.perform_substitution(mySerialNumberConf)

    camera_name = "camera" + whoAmI
    camera_namespace = whoAmI +"/camera"


    realsense_node = Node(
        package='realsense2_camera',
        name=camera_name,
        namespace=camera_namespace,
        executable='realsense2_camera_node',
        parameters=[{ 
            'enable_depth': 'false',
            #'rgb_camera.profile': '1280x720x15',
            'rgb_camera.profile': '1920x1080x15',
            'camera_name': camera_name,
            'serial_no': mySerialNumber,
        }],
        output='screen',
        arguments=['--ros-args'],
        emulate_tty=True,
    )

    rot_obj_detection = Node(
            package='rvc_rotated_object_detection',
            executable='object_detection',
            output='screen',
            namespace=whoAmI,
            parameters=[{
                #'cam_prefix': whoAmI+"/camera/color",
                'cam_prefix': "camera/color",
                'roi': {
                    'crop_top': 200,
                    'crop_bottom': 150,
                    'crop_left': 100,
                    'crop_right': 400
                },
                'orb': {
                    'min_matches': 20,
                    'matches_limit': 20,
                },
                'objects': ['robot'],
                'object': {
                    'robot': {
                        'image_path': PathJoinSubstitution([FindPackageShare('rvc_rotated_object_detection'),'resources','IntelBox96.png']),
                        'nfeatures': 100,
                        'thickness': 0.044  
                    }
                },
                'project': True,
                'projection_distance': 0.67
            }]
        )

    camera_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="camera_static_transform_publisher",
        output="log",
        arguments=["0.0", "0.0", "0.8", "0.0", "1.57079632679", "0.0", "world", "camera_link"],
    )

    return [
        realsense_node,
        camera_tf,
        rot_obj_detection
    ]


def generate_launch_description():
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument( 
            "namespace", 
            description="Namespace for the whole vision composition. has to match with the motion controller",
            default_value="ipc"
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument( 
            "rs_serial", 
            description="serial number of the realsense camera, if there are more than one",
            default_value=""
        )
    )

    return LaunchDescription ( declared_arguments + [OpaqueFunction(function=launch_setup) ])

