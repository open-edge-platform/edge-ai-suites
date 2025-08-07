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

from ament_index_python import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.actions import DeclareLaunchArgument
from tempfile import NamedTemporaryFile
from launch.actions import LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessStart


from launch.actions import OpaqueFunction
from launch.actions import TimerAction

import os
import ast

def generate_tmp_conf_file(name, namespace, naked_origin):
    temp = NamedTemporaryFile(suffix=str(os.getpid()), mode="w", encoding="utf-8", delete=False)
    print(name + ": temp file: " + temp.name)
    inp = open( naked_origin )
    if namespace:
        namespace = namespace + "/"
    temp.write( namespace + name +":\n" );
    temp.write("  ros__parameters:\n" )
    for line in inp:
        temp.write(line);
    return temp

def launch_setup(context, *args, **kwargs):
    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI= context.perform_substitution(whoAmIConf)

    mySerialNumberConf = LaunchConfiguration("rs_serial")
    mySerialNumber= context.perform_substitution(mySerialNumberConf)

    camera_name = "camera"+whoAmI
    #camera_name = "camera" + whoAmI
    camera_namespace = whoAmI + "/camera"
    rvc_vision_main_name = "rvc_vision_main"
    rvc_object_detection_node_name = "object_detection"
    rvc_object_detection_name = "rvc_object_detection_engine"
    rvc_pose_detector_node_name = "rvc_pose_detector"
    rvc_pose_detector_name = "rvc_pose_detector"
    rvc_pose_detector_path = get_package_share_directory(rvc_pose_detector_name)
    rvc_object_detection_path = get_package_share_directory(rvc_object_detection_name)

    print(camera_name)
    camera_temp = generate_tmp_conf_file(camera_name, camera_namespace, get_package_share_directory(rvc_vision_main_name) + "/config/rs_parameters.yaml")
    od_temp = generate_tmp_conf_file( rvc_object_detection_node_name, whoAmI, get_package_share_directory(rvc_object_detection_name) + "/config/parameters.yaml")
    pd_temp = generate_tmp_conf_file(rvc_pose_detector_node_name, whoAmI, get_package_share_directory(rvc_pose_detector_name) + "/config/parameters.yaml" )

    rs2_camera_node = Node(
        package='realsense2_camera',
        name=camera_name,
        namespace=camera_namespace,
        executable='realsense2_camera_node',
        parameters=[ 
            camera_temp.name, 
            {

                'camera_name': 'camera' + whoAmI,
                'serial_no': mySerialNumber,
            }
        ],
        output='screen',
        arguments=['--ros-args'],
        emulate_tty=True,
    )

    od_node = Node(
        package=rvc_object_detection_name,
        executable='rvc_object_detection',
        namespace= whoAmI,
        parameters=[
            od_temp.name, 
            {
                'camera_name': 'camera' + whoAmI,
            }
        ],
    )

    pd_node = Node(
        package=rvc_pose_detector_name,
        executable='rvc_pose_detector',
        namespace= whoAmI,
        parameters=[
            pd_temp.name,
            {
                'camera_name': 'camera' + whoAmI,
            }
        ], 
    )

    profiler_node = Node(
        package='rvc_profiler',
        namespace= whoAmI,
        executable='rvc_profiler'
    )

    return [
	    od_node, 
	    pd_node,
	    profiler_node,
	    rs2_camera_node,
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

