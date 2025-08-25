#!/usr/bin/env python3
#
# Copyright 2019 ROBOTIS CO., LTD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    launch_file_dir = os.path.join(get_package_share_directory('followme_turtlebot3_gazebo'), 'launch')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    x_pose_gbot = LaunchConfiguration('x_pose_gbot', default='1.0')
    y_pose_gbot = LaunchConfiguration('y_pose_gbot', default='1.0')


    launch_gz_world_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'empty_world_multibot.launch.py')
        ),
        launch_arguments={
            'x_pose_gbot': x_pose_gbot,
            'y_pose_gbot': y_pose_gbot
        }.items()
    )

    # Adbscan node
    # adbscan_params_file = os.path.join(get_package_share_directory('adbscan_ros2_follow_me'),'config','adbscan_sub_RS.yaml')
    # adbscan_node = Node(
        # package="adbscan_ros2_follow_me",
        # executable="adbscan_sub_w_gesture",
        # parameters=[adbscan_params_file],
        # remappings=[
            # ('cmd_vel','tb3/cmd_vel')]
    # )

    # Gesture node
    gesture_recognition_params_file = os.path.join(get_package_share_directory('gesture_recognition_pkg'),'config','gesture_recognition.yaml')
    gesture_recognition_node = Node(
        package="gesture_recognition_pkg",
        executable="gesture_recognition_node.py",
        parameters=[gesture_recognition_params_file]
    )

    # traj_and_img_publisher node
    # traj_and_img_publisher_node = Node(
        # package="gesture_recognition_pkg",
        # executable="traj_and_img_publisher_node.py",
        # parameters=[gesture_recognition_params_file]
    # )
    
    
    ld = LaunchDescription()

    # Add the commands to the launch description
    ld.add_action(launch_gz_world_cmd)
    # ld.add_action(adbscan_node)
    ld.add_action(gesture_recognition_node)
    # ld.add_action(traj_and_img_publisher_node)


    return ld
