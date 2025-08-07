# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import os
import sys

import launch
import launch_ros.actions
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    ld = launch.LaunchDescription([
        launch.actions.DeclareLaunchArgument(
            name='camera',
            default_value='front_camera'
        ),
        launch.actions.DeclareLaunchArgument(
            name='ID',
            default_value='0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='camera_setup',
            default_value='RGBD'
        ),
        launch.actions.DeclareLaunchArgument(
            name='image',
            default_value='d455_color'
        ),
        launch.actions.DeclareLaunchArgument(
            name='depthmap_factor',
            default_value='1.0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='rviz',
            default_value='false'
        ),
        launch.actions.DeclareLaunchArgument(
            name='orb_ini_fast_threshold',
            default_value='20'
        ),
        launch.actions.DeclareLaunchArgument(
            name='orb_min_fast_threshold',
            default_value='5'
        ),
        # Please change the value of camera_fps that represents the real FPS of input camera images, the default value is 30.0 if you don't specify it
        launch.actions.DeclareLaunchArgument(
            name='camera_fps',
            default_value='30.0'
        ),
        launch.actions.IncludeLaunchDescription(
            launch.launch_description_sources.PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_tracker'), 'launch/tracker.launch.py')
            ),
            launch_arguments={
                'ID': launch.substitutions.LaunchConfiguration('ID'),
                'camera': launch.substitutions.LaunchConfiguration('camera'),
                'baselink_frame': launch.substitutions.LaunchConfiguration('image'),
                'pub_tf_child_frame': launch.substitutions.LaunchConfiguration('camera'),
                'rviz': launch.substitutions.LaunchConfiguration('rviz'),
                'camera_setup': launch.substitutions.LaunchConfiguration('camera_setup'),
                'image_topic': launch.substitutions.LaunchConfiguration('camera'),
                'depth_topic': launch.substitutions.LaunchConfiguration('camera'),
                'depthmap_factor': launch.substitutions.LaunchConfiguration('depthmap_factor'),
                'orb_ini_fast_threshold': launch.substitutions.LaunchConfiguration('orb_ini_fast_threshold'),
                'orb_min_fast_threshold': launch.substitutions.LaunchConfiguration('orb_min_fast_threshold'),
                'camera_fps': launch.substitutions.LaunchConfiguration('camera_fps')
            }.items()
        )
    ])
    return ld


if __name__ == '__main__':
    generate_launch_description()
