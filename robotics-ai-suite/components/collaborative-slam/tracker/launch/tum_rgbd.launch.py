# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import os
import sys
import yaml

import launch
from launch.actions import DeclareLaunchArgument, SetLaunchConfiguration
from launch.actions import ExecuteProcess, TimerAction, EmitEvent
from launch.events import Shutdown
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.actions import DeclareLaunchArgument, SetLaunchConfiguration
from launch.conditions import IfCondition

from python_utils import ReplaceString

camera_intrinsics_dict = {
    'fr1': '[640.0, 480.0, 517.306408, 516.469215, 318.643040, 255.313989]',
    'fr2': '[640.0, 480.0, 520.908620, 521.007327, 325.141442, 249.701764]',
    'fr3': '[640.0, 480.0, 535.4, 539.2, 320.1, 247.6]'
    }

camera_distortion_dict = {
    'fr1': '[0.262383, -0.953104, -0.005358, 0.002628, 1.163314]',
    'fr2': '[0.231222, -0.784899, -0.003257, -0.000105, 0.917205]',
    'fr3': '[0.0, 0.0, 0.0, 0.0, 0.0]'
    }

def declare_configurable_parameters(params):
    return [DeclareLaunchArgument(param, default_value=str(params[param]), description="") for param in params]


def set_configurable_parameters(params):
    return dict([(param, LaunchConfiguration(param)) for param in params])

def generate_launch_description():

    configFilePath = os.path.join(get_package_share_directory('univloc_tracker'),'config','tum_rgbd.yaml')

    with open(configFilePath, 'r') as file:
        configParams = yaml.safe_load(file)['univloc_tracker']

    # Wrap empty string with '""'
    for param in configParams:
        #print("type: {}; value:{}".format(type(configParams[param]), configParams[param]))
        if type(configParams[param]) is str and len(configParams[param]) == 0:
            if param == "namespace":
                configParams[param] = '/'
            else:
                configParams[param] = '""'

    # Declare parameters
    description = declare_configurable_parameters(configParams)

    # Declare and set launch prefix based on the parameter gdb
    description.append(DeclareLaunchArgument('launch_prefix', default_value=''))
    # I hate openning a new terminal. But there is no way to input any commands to gdb in the current terminal.
    # See discussions at https://github.com/ros2/launch_ros/issues/165
    # You can change `gnome-terminal --` to another terminal, such as `xterm -e`
    description.append(SetLaunchConfiguration(
        name='launch_prefix', value='gnome-terminal -- gdb -ex run --args',
        condition=IfCondition(LaunchConfiguration("gdb"))))

    # Declare parameters fr1/2/3
    description.append(DeclareLaunchArgument('fr1', default_value='false'))
    description.append(DeclareLaunchArgument('fr2', default_value='false'))
    description.append(DeclareLaunchArgument('fr3', default_value='false'))

    # Set camera intrinsics and camera_distortion based on the parameter fr1/2/3
    for fr in camera_intrinsics_dict:
        description.append(SetLaunchConfiguration(name='camera_intrinsics', value=camera_intrinsics_dict[fr],
            condition=IfCondition(LaunchConfiguration(fr))))
    for fr in camera_distortion_dict:
        description.append(SetLaunchConfiguration(name='camera_distortion', value=camera_distortion_dict[fr],
            condition=IfCondition(LaunchConfiguration(fr))))

    # Launch the tracker node
    namespace = LaunchConfiguration('namespace')
    tracker_name = ['univloc_tracker_', LaunchConfiguration('ID')]
    description.append(Node(
        package='univloc_tracker',
        executable='univloc_tracker_ros',
        name=tracker_name,
        output='screen',
        additional_env={'SPDLOG_LEVEL': LaunchConfiguration("log_level")},
        prefix=LaunchConfiguration("launch_prefix"),
        parameters=[set_configurable_parameters(configParams)]
    ))

    # We don't add namespace to the camera topic name.
    # We leave it up to the user to provide the camera name and to include the namespace.
    description.append(SetLaunchConfiguration(
        name='image_topic', value=['/', LaunchConfiguration('camera'), '/color/image_raw'],
        condition=IfCondition(PythonExpression(["'", LaunchConfiguration('image_topic'), "' ==  '\"\"' "]))))

    # Launch rviz
    rviz_config = os.path.join(get_package_share_directory('univloc_tracker'), 'config', 'rviz2_tracker.rviz')
    image_topic = LaunchConfiguration('image_topic')
    description.append(DeclareLaunchArgument(
        'robot_namespace',
        default_value='',
        description='Top-level namespace'))

    description.append(SetLaunchConfiguration(
        name='robot_namespace', value=('/', namespace),
        condition=IfCondition(PythonExpression(["'", LaunchConfiguration('namespace'), "' != '/'"]))))

    robot_namespace = LaunchConfiguration('robot_namespace')

    namespaced_rviz_config_file = ReplaceString(
        source_file=rviz_config,
        replacements={'<robot_namespace>': robot_namespace, '<tracker_name>': tracker_name, '<image_topic>': image_topic})

    description.append(Node(
        package='rviz2',
        executable='rviz2',
        name='rviz',
        arguments=['-d', namespaced_rviz_config_file],
        output='log',
        condition=IfCondition(LaunchConfiguration("rviz"))
    ))

    return launch.LaunchDescription(description)


if __name__ == '__main__':
    generate_launch_description()
