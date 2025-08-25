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

    namespace = LaunchConfiguration('namespace')
    pointcloud_topic = LaunchConfiguration('pointcloud_topic')

    launch_desc_segmentation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(launch_dir, 'launch', 'realsense_groundfloor_segmentation_launch.py')),
        launch_arguments={'camera_name': 'pseudo_camera'}.items())

    # Create the launch description and populate
    return LaunchDescription([
        DeclareLaunchArgument('namespace', description='Namespace of nodes/topics.', default_value=''),
        DeclareLaunchArgument('pointcloud_topic', description='Name of input pointcloud topic.', default_value='/input/points'),
        GroupAction([
            PushRosNamespace(
                condition=IfCondition(PythonExpression(['"" != "', namespace,'"'])),
                namespace=namespace),

            Node(
                package='pointcloud_groundfloor_segmentation',
                executable='pointcloud_input_node',
                output='screen',
                remappings=[('/tf_static', 'tf_static'), ('/tf', 'tf'), ('/input/points', pointcloud_topic)],
                on_exit=launch.actions.Shutdown()
            ),

            launch_desc_segmentation
        ])
    ])
