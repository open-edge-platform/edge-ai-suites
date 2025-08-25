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
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

from launch.actions import DeclareLaunchArgument, ExecuteProcess

from launch.actions import ExecuteProcess, OpaqueFunction
from launch import LaunchDescription
from launch.actions import OpaqueFunction

def exit_process_function(_launch_context):
    ExecuteProcess( cmd=['cp', 'core','/home/drusso'], log_cmd=True)
    print('exit_process_function() called')


def launch_setup(context, *args, **kwargs):
    packageName ="rvc_vision_main"

    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI= context.perform_substitution(whoAmIConf)

    mySerialNumberConf = LaunchConfiguration("rs_serial")
    mySerialNumber= context.perform_substitution(mySerialNumberConf)

    camera_name = "camera" + whoAmI
    camera_namespace = whoAmI +"/camera"

    rvc_pose_detector_path = get_package_share_directory("rvc_pose_detector")
    rvc_object_detection_path = get_package_share_directory("rvc_object_detection_engine")
    container = ComposableNodeContainer(
            name='rvc_container',
            namespace= whoAmI,
            package='rclcpp_components',
            executable='component_container_mt',
            composable_node_descriptions=[
                ComposableNode(
                    package='realsense2_camera',
                    plugin='realsense2_camera::RealSenseNodeFactory',
                    name=camera_name,
                    namespace=camera_namespace,
                    parameters=[ get_package_share_directory(packageName) + "/config/rs_parameters.yaml", 
                        { 
                            'camera_name': camera_name,
                            'serial_no': mySerialNumber,
                        }],
                    extra_arguments=[{'use_intra_process_comms': True}]
                    ),
                ComposableNode(
                    package='rvc_object_detection_engine',
                    namespace= whoAmI,
                    plugin='RVC::ObjectDetection',
                    parameters=[ rvc_object_detection_path + "/config/parameters.yaml" ],
                    extra_arguments=[{'use_intra_process_comms': True}]
                    ),
                ComposableNode(
                    package='rvc_pose_detector',
                    namespace= whoAmI,
                    plugin='RVC::PoseDetector',
                    parameters=[ rvc_pose_detector_path + "/config/parameters.yaml" ],
                    extra_arguments=[{'use_intra_process_comms': True}]
                    ),
                ComposableNode(
                    package='rvc_profiler',
                    namespace= whoAmI,
                    plugin='RVC::Profiler',
                    extra_arguments=[{'use_intra_process_comms': True}]
                    ),

            ],
            output='both',
        )
    return [container]

def generate_launch_description():
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument(
            'camera_name', 
            default_value='camera'
        )
    )
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
