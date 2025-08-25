# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import os
import sys

import launch
from launch.actions import DeclareLaunchArgument, SetLaunchConfiguration
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from ament_index_python.packages import get_package_share_directory

params = {
    'server_mode': ['mapping',
        'slam mode supported by server: [mapping, localization, relocalization, remapping]'],
    'grid_size': ['0.2',
        'grid_size for server'],
    'fix_scale': ['true',
        'server parameter'],
    'segment_optimize': ['true',
        'server parameter'],
    'correct_loop': ['true',
        'whether to correct loop or not'],
    'vocabulary': ['orb_vocab.dbow2',
        'vocabulary file, either filename under the config folder or an absolute path'],
    'camera_fusion_stamp_diff_threshold': ['0.05',
        'timestamp difference threshold for front and rear camera fusion'],
    'front_rear_camera_constraint_thr': ['0.5',
        '3D distance threshold for front and rear camera constraint'],
    'iteration_times': ['20',
        'iteration times for global optimizer'],
    'far_distance': ['20.0',
        'far landmark distance threshold'],
    'near_distance': ['0.5',
        'near landmark distance threshold'],
    'back_distance': ['0.0',
        'the distance used to put camera backwards to get more landmarks'],
    'save_map_path': ['',
        'for save map path'],
    'save_traj_folder': ['',
        'for save trajectory output'],
    'delay_time_record_folder': ['',
        'for save message delay time record'],
    'load_map_path': ['',
        'for load map path'],
    'rviz': ['true',
        'whether to launch rviz'],
    'gdb': ['false',
        'whether to launch the server node with gdb for debugging'],
    'log_level': ['warning',
        'spdlog level: [trace, debug, info, warning, error, critical, off]'],
    'sigterm_timeout': ['60',
        'timeout for SIGTERM escalation'],
    'visualization_interval': ['1.0',
        'timeout for rviz updates. Allowed value: (0.01, 1.0]'],
    'force_best_effort': ['false',
        'whether to force best effort QoS for ROS service'],
    'server_zmax': ['0.6',
        'max values of the z axis - gives the height of the robot'],
    'server_zmin': ['0.3',
        'min values of the z axis'],
    'server_remapping_region': ['[0.0]',
        'The four vertexes of remapping region, [P1.x, P1.y, ... , P4.x, P4.y], must be in clockwise or \
         anti-clockwise order']
    }


def declare_configurable_parameters(params):
    return [DeclareLaunchArgument(param, default_value=params[param][0], description=params[param][1]) for param in params]


def set_configurable_parameters(params):
    return dict([(param, launch.substitutions.LaunchConfiguration(param)) for param in params])

def generate_launch_description():
    # Wrap empty string with '""'
    for param in params:
        if type(params[param][0]) is str and len(params[param][0]) == 0:
            params[param][0] = '""'

    # Declare parameters
    description = declare_configurable_parameters(params)

    # Declare and set launch prefix based on the parameter gdb
    description.append(DeclareLaunchArgument('launch_prefix', default_value=''))
    # I hate openning a new terminal. But there is no way to input any commands to gdb in the current terminal.
    # See discussions at https://github.com/ros2/launch_ros/issues/165
    # You can change `gnome-terminal --` to another terminal, such as `xterm -e`
    description.append(SetLaunchConfiguration(
        name='launch_prefix', value='gnome-terminal -- gdb -ex run --args',
        condition=IfCondition(LaunchConfiguration("gdb"))))

    # Launch the server node
    description.append(Node(
        package='univloc_server',
        executable='univloc_server',
        name=['univloc_server'],
        output='screen',
        additional_env={'SPDLOG_LEVEL': LaunchConfiguration("log_level")},
        prefix=LaunchConfiguration("launch_prefix"),
        parameters=[set_configurable_parameters(params)],
        sigterm_timeout=LaunchConfiguration('sigterm_timeout')
    ))

    # Launch rviz
    rviz_config = os.path.join(get_package_share_directory('univloc_server'), 'config', 'rviz2_server.rviz')
    description.append(Node(
        package='rviz2',
        executable='rviz2',
        name='rviz',
        arguments=['-d', rviz_config],
        output='log',
        condition=IfCondition(LaunchConfiguration("rviz"))
    ))

    return launch.LaunchDescription(description)


if __name__ == '__main__':
    generate_launch_description()
