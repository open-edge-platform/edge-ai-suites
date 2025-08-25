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

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, GroupAction
from launch.conditions import IfCondition, LaunchConfigurationEquals
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.launch_description_sources import PythonLaunchDescriptionSource
import launch
from launch_ros.actions import Node, PushRosNamespace
from nav2_common.launch import RewrittenYaml

def generate_launch_description():

    launch_dir = get_package_share_directory('pointcloud_groundfloor_segmentation')

    # Create the launch configuration variables
    namespace = LaunchConfiguration('namespace')
    node_params_file = LaunchConfiguration('node_params_file')
    standalone = LaunchConfiguration('standalone')
    camera_name = LaunchConfiguration('camera_name')
    standalone_height_above_ground = LaunchConfiguration('standalone_height_above_ground')

    use_best_effort_qos = LaunchConfiguration('use_best_effort_qos')
    with_rviz = LaunchConfiguration('with_rviz')
    rviz_config_file = os.path.join(launch_dir, 'rviz', 'standalone.rviz')

    node_params = RewrittenYaml(
        source_file=node_params_file,
        param_rewrites={'use_best_effort_qos' : use_best_effort_qos, 'name' : camera_name},
        root_key=namespace,
        convert_types=True)

    # Create the launch description and populate
    return LaunchDescription([
        DeclareLaunchArgument('namespace', description='Namespace of nodes/topics.', default_value=''),
        DeclareLaunchArgument('camera_name', description='Name of the RealSense camera (or another sensor) this node will contect to.', default_value='camera'),
        DeclareLaunchArgument('use_best_effort_qos', description='Use BestEffort as QoS for subscriber/publisher topics', default_value='False'),
        DeclareLaunchArgument('standalone', description='Run this application only with a RealSense camera but without any robot (assumes camera is parallel to ground)', default_value='False'),
        DeclareLaunchArgument('standalone_height_above_ground', description='Can be used with standalone flag to provide indication of camera position above ground', default_value='0.1'),
        DeclareLaunchArgument('with_rviz', description='Run with rviz', default_value='False'),
        DeclareLaunchArgument('node_params_file', description='Path to the node params', default_value=os.path.join(launch_dir, 'params', 'groundfloor_segmentation_params.yaml')),

        GroupAction([
            PushRosNamespace(
                condition=IfCondition(PythonExpression(['"" != "', namespace,'"'])),
                namespace=namespace),
            
            Node(
                condition=IfCondition(PythonExpression([standalone])),
                package='tf2_ros',
                executable='static_transform_publisher',
                name = 'base_link_static_tf',
                arguments = ['0', '0', standalone_height_above_ground, '0', '0', '0', '1', '/base_link', PythonExpression(["'", camera_name, "_link'"])],
                remappings=[('/tf_static', 'tf_static')],
                on_exit=launch.actions.Shutdown()
            ),

            Node(
                condition=IfCondition(PythonExpression([standalone])),
                package='tf2_ros',
                executable='static_transform_publisher',
                name = 'base_link_static_tf',
                arguments = ['0', '0', '0.0', '0', '0', '0', '1', '/map', '/base_link'],
                remappings=[('/tf_static', 'tf_static')],
                on_exit=launch.actions.Shutdown()
            ),

            Node(
                package='pointcloud_groundfloor_segmentation',
                executable='pointcloud_groundfloor_segmentation',
                output='screen',
                parameters=[node_params],
                remappings=[('/tf_static', 'tf_static'), ('/tf', 'tf')],
                on_exit=launch.actions.Shutdown()
            ),

            Node(
                condition=IfCondition(PythonExpression([with_rviz])),
                package='rviz2',
                executable='rviz2',
                arguments=['-d', rviz_config_file, '--ros-args', '--remap', 'use_sim_time:=True'],
                output={'both': 'log'},
                remappings=[("/tf", "tf"), ("/tf_static", "tf_static")]
            )
        ])
    ])
