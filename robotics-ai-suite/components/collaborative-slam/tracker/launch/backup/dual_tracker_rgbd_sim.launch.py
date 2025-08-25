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
            name='camera1',
            default_value='front_camera'
        ),
        launch.actions.DeclareLaunchArgument(
            name='camera2',
            default_value='rear_camera'
        ),
        launch.actions.DeclareLaunchArgument(
            name='ID1',
            default_value='0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='ID2',
            default_value='1'
        ),
        launch.actions.DeclareLaunchArgument(
            name='camera_setup1',
            default_value='RGBD'
        ),
        launch.actions.DeclareLaunchArgument(
            name='camera_setup2',
            default_value='RGBD'
        ),
        launch.actions.DeclareLaunchArgument(
            name='image1',
            default_value='d455_color'
        ),
        launch.actions.DeclareLaunchArgument(
            name='image2',
            default_value='d455_color'
        ),
        launch.actions.DeclareLaunchArgument(
            name='depthmap_factor',
            default_value='1.0'
        ),
        # Please change the value of camera_fps that represents the real FPS of input camera images, the default value is 30.0 if you don't specify it
        launch.actions.DeclareLaunchArgument(
            name='camera_fps1',
            default_value='30.0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='camera_fps2',
            default_value='30.0'
        ),
        launch.actions.IncludeLaunchDescription(
            launch.launch_description_sources.PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_tracker'), 'launch/tracker.launch.py')
            ),
            launch_arguments={
                'ID': launch.substitutions.LaunchConfiguration('ID1'),
                'camera': launch.substitutions.LaunchConfiguration('camera1'),
                'baselink_frame': launch.substitutions.LaunchConfiguration('image1'),
                'pub_tf_child_frame': launch.substitutions.LaunchConfiguration('camera1'),
                'rviz': 'false',
                'camera_setup': launch.substitutions.LaunchConfiguration('camera_setup1'),
                'image_topic': launch.substitutions.LaunchConfiguration('camera1'),
                'depth_topic': launch.substitutions.LaunchConfiguration('camera1'),
                'depthmap_factor': launch.substitutions.LaunchConfiguration('depthmap_factor'),
                'camera_fps': launch.substitutions.LaunchConfiguration('camera_fps1')
            }.items()
        ),
        launch.actions.IncludeLaunchDescription(
            launch.launch_description_sources.PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_tracker'), 'launch/tracker.launch.py')
            ),
            launch_arguments={
                'ID': launch.substitutions.LaunchConfiguration('ID2'),
                'camera': launch.substitutions.LaunchConfiguration('camera2'),
                'baselink_frame': launch.substitutions.LaunchConfiguration('image2'),
                'pub_tf_child_frame': launch.substitutions.LaunchConfiguration('camera2'),
                'rviz': 'false',
                'camera_setup': launch.substitutions.LaunchConfiguration('camera_setup2'),
                'image_topic': launch.substitutions.LaunchConfiguration('camera2'),
                'depth_topic': launch.substitutions.LaunchConfiguration('camera2'),
                'depthmap_factor': launch.substitutions.LaunchConfiguration('depthmap_factor'),
                'camera_fps': launch.substitutions.LaunchConfiguration('camera_fps2')
            }.items()
        )
    ])
    return ld


if __name__ == '__main__':
    generate_launch_description()
