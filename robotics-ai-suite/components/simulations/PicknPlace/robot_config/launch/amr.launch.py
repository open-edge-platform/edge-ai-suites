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

# Description: Helper launch file to spawn AMR in Gazebo separated by namespace
# Example usage:
# amr_launch_cmd = IncludeLaunchDescription(
#        PythonLaunchDescriptionSource(
#            os.path.join(robot_config_launch_dir, 'amr.launch.py')),
#                launch_arguments={ 'amr_name': 'amr1',
#                           'x_pos': '1.0',
#                           'y_pos': '1.0',
#                           'yaw': '0.0',
#                           'use_sim_time': 'true',
#                           'launch_stack': 'true',
#                           'wait_on': 'service /spawn_entity'
#                          }.items()
#                        )
#
# ld.add_action(amr_launch_cmd)

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_context import LaunchContext
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node

import robot_config.utils as util

LOG_LEVEL = 'info'

def generate_launch_description():

    return LaunchDescription([
        OpaqueFunction(function = launch_setup),
        ])

def launch_setup(context: LaunchContext):

    TURTLEBOT3_MODEL = 'waffle'

    ros_distro = os.environ.get('ROS_DISTRO')
    
    package_path = get_package_share_directory('robot_config')
    nav_launch_dir = os.path.join(package_path, 'launch', 'nav2_bringup', ros_distro)

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    amr_name = context.launch_configurations['amr_name']
    x_pos = context.launch_configurations['x_pos']
    y_pos = context.launch_configurations['y_pos']
    yaw = context.launch_configurations['yaw']

    if 'mode' in context.launch_configurations:
        mode = context.launch_configurations['mode']
    else:
        mode = 'full'

    urdf = os.path.join(
        package_path, 'urdf', 'turtlebot3_' + TURTLEBOT3_MODEL + '.urdf'
    )

    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    actions = []
    
    # If launch request with Full or Gazebo only mode.
    if mode == 'full' or mode == 'gazebo' :
        # Create state publisher node for that instance
        turtlebot_state_publisher = Node(
            package='robot_state_publisher',
            namespace=['/', amr_name],
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time,
                        'publish_frequency': 10.0}],
            remappings=remappings,
            arguments=[urdf],
        )

        actions.append(turtlebot_state_publisher)

        # Create spawn call
        spawn_turtlebot3 = Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-file', os.path.join(package_path,'models', 'turtlebot3_' + TURTLEBOT3_MODEL, 'model_tray_camera.sdf'),
                '-entity', amr_name,
                '-robot_namespace', ['/', amr_name],
                '-x', x_pos, '-y', y_pos,
                '-z', '0.05', '-Y', yaw,
                '-unpause',
            ],
            output='screen',
        )
        actions.append(spawn_turtlebot3)

    # Create stack nodes for Full or stack only mode.
    if  mode == 'full' or mode == 'stack':
        params_file = LaunchConfiguration('nav_params_file',  default=os.path.join(package_path, 'params', 'nav2_params_' + ros_distro + '.yaml'))
        bringup_cmd = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav_launch_dir, 'bringup_launch.py')),
                launch_arguments={
                                'slam': 'False',
                                'namespace': ['/', amr_name],
                                'use_namespace': 'True',
                                'map': '',
                                'map_server': 'False',
                                'params_file': params_file,
                                'default_bt_xml_filename': os.path.join(
                                    get_package_share_directory('nav2_bt_navigator'),
                                    'behavior_trees', 'navigate_w_replanning_and_recovery.xml'),
                                'autostart': 'true',
                                'use_composition': 'False',
                                'use_sim_time': use_sim_time, 'log_level': LOG_LEVEL}.items(),
                )
        
        qx, qy, qz, qw = util.quaternion_from_euler(0.0, 0.0, float(yaw))

        # Wait for initialpose before setting initial pose.
        wait_for_initialpose = ExecuteProcess(
                cmd=[
                    'ros2', 'run', 'robot_config', 'wait_for_interface.py', 'topic',
                    '/' + amr_name + '/initialpose',
                ], output='screen',
            )

        message = f"{{header: {{frame_id: map}}, pose: {{pose: {{position: \
                    {{x: {context.launch_configurations['x_pos']}, y: {context.launch_configurations['y_pos']}, \
                    z: {0.05} }}, orientation: {{x: {qx}, y: {qy}, z: {qz}, w: {qw} }} }}, }} }}"

        initial_pose_cmd = ExecuteProcess(
            cmd=['ros2', 'topic', 'pub', '-1', '--qos-reliability', 'reliable', '/' + amr_name + '/initialpose',
                'geometry_msgs/PoseWithCovarianceStamped', message],
            output='screen'
        )

        set_pose_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=wait_for_initialpose,
                on_exit=[initial_pose_cmd]
            )
        )

        actions.append(bringup_cmd)
        actions.append(wait_for_initialpose)
        actions.append(set_pose_event)

    # Check if wait_on is provided.  If exist then create a dependency action on it
    if "wait_on" in context.launch_configurations:
        wait_on = context.launch_configurations['wait_on'].split(' ')
        wait_for_action_server = ExecuteProcess(
            cmd=[
                'ros2', 'run', 'robot_config', 'wait_for_interface.py', wait_on[0],
                wait_on[1]
            ], output='screen',
        )
        # Create a dependency action for spawn turtlebot3
        action = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=wait_for_action_server,
                on_exit=actions,
            )
        )

        actions = [wait_for_action_server, action]
   
    return actions

