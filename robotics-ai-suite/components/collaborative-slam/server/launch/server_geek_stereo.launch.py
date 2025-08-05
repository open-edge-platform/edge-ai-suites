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
            name='server_mode',
            default_value='mapping'
        ),
        launch.actions.DeclareLaunchArgument(
            name='fix_scale',
            default_value='true'
        ),
        launch.actions.DeclareLaunchArgument(
            name='save_map_path',
            default_value=''
        ),
        launch.actions.DeclareLaunchArgument(
            name='load_map_path',
            default_value=''
        ),
        launch.actions.DeclareLaunchArgument(
            name='rviz',
            default_value='false'
        ),
        launch.actions.DeclareLaunchArgument(
            name='gdb',
            default_value='false'
        ),
        launch.actions.DeclareLaunchArgument(
            name='save_traj_folder',
            default_value=''
        ),
        launch.actions.DeclareLaunchArgument(
            name='segment_optimize',
            default_value='true'
        ),
        launch.actions.DeclareLaunchArgument(
            name='near_distance',
            default_value='0.0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='far_distance',
            default_value='20.0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='back_distance',
            default_value='1.0'
        ),
        launch.actions.DeclareLaunchArgument(
            name='server_zmax',
            default_value='0.6'
        ),
        launch.actions.DeclareLaunchArgument(
            name='server_zmin',
            default_value='0.3'
        ),
        launch.actions.DeclareLaunchArgument(
            name='server_remapping_region',
            default_value='[0.0]'
        ),
        launch.actions.IncludeLaunchDescription(
            launch.launch_description_sources.PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_server'), 'launch/server.launch.py')
            ),
            launch_arguments={
                'server_mode': launch.substitutions.LaunchConfiguration('server_mode'),
                'rviz': launch.substitutions.LaunchConfiguration('rviz'),
                'fix_scale': launch.substitutions.LaunchConfiguration('fix_scale'),
                'gdb': launch.substitutions.LaunchConfiguration('gdb'),
                'save_map_path': launch.substitutions.LaunchConfiguration('save_map_path'),
                'load_map_path': launch.substitutions.LaunchConfiguration('load_map_path'),
                'save_traj_folder': launch.substitutions.LaunchConfiguration('save_traj_folder'),
                'segment_optimize': launch.substitutions.LaunchConfiguration('segment_optimize'),
                'far_distance': launch.substitutions.LaunchConfiguration('far_distance'),
                'near_distance': launch.substitutions.LaunchConfiguration('near_distance'),
                'back_distance': launch.substitutions.LaunchConfiguration('back_distance'),
                'server_zmax': launch.substitutions.LaunchConfiguration('server_zmax'),
                'server_zmin': launch.substitutions.LaunchConfiguration('server_zmin'),
                'server_remapping_region': launch.substitutions.LaunchConfiguration('server_remapping_region')
            }.items()
        )
    ])
    return ld


if __name__ == '__main__':
    generate_launch_description()
