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
from launch.conditions import IfCondition, LaunchConfigurationEquals

from python_utils import ReplaceString

# Based on https://github.com/raulmur/ORB_SLAM2/tree/master/Examples/Monocular
# and https://github.com/billamiable/openvslam/tree/master/example/kitti
# Sequences Odom gray from 0 to 2 are having same parameters, 3 for itself
# and 4-12 for itself
s00_02 = {
        # width, height, fx, fy, cx, cy
        'camera_intrinsics': '[1241.0, 376.0, 718.856, 718.856, 607.1928, 185.2157]',
        # k1, k2, p1, p2, k3
        'camera_distortion': '[0.0, 0.0, 0.0, 0.0, 0.0]',
        'orb_ini_fast_threshold': '20'
}

s03 = {
        # width, height, fx, fy, cx, cy
        'camera_intrinsics': '[1242.0, 375.0, 721.5377, 721.5377, 609.5593, 172.854]',
        # k1, k2, p1, p2, k3
        'camera_distortion': '[0.0, 0.0, 0.0, 0.0, 0.0]',
        'orb_ini_fast_threshold': '20'
}

s04_12 = {
        # width, height, fx, fy, cx, cy
        'camera_intrinsics': '[1226.0, 370.0, 707.0912, 707.0912, 601.8873, 183.1104]',
        # k1, k2, p1, p2, k3
        'camera_distortion': '[0.0, 0.0, 0.0, 0.0, 0.0]',
        'orb_ini_fast_threshold': '20'
}


def declare_configurable_parameters(params):
    return [DeclareLaunchArgument(param, default_value=str(params[param]), description="") for param in params]

def set_conditioned_launch_configuration(params, cond):
    return [SetLaunchConfiguration(name=param, value=params[param],
            condition=cond) for param in params]

def set_configurable_parameters(params):
    return dict([(param, LaunchConfiguration(param)) for param in params])

def generate_launch_description():

    configFilePath = os.path.join(get_package_share_directory('univloc_tracker'),'config','kitti.yaml')

    with open(configFilePath, 'r') as file:
        configParams = yaml.safe_load(file)['univloc_tracker']
    configParams['camera_setup'] = 'Stereo'
    # Wrap empty string with '""'
    for param in configParams:
        #print("type: {}; value:{}".format(type(configParams[param]), configParams[param]))
        if type(configParams[param]) is str and len(configParams[param]) == 0:
            if param == "namespace":
                configParams[param] = '/'
            else:
                configParams[param] = '""'
    description = declare_configurable_parameters(configParams)

    description.append(DeclareLaunchArgument('s00_02', default_value='true'))
    description.append(DeclareLaunchArgument('s03', default_value='false'))
    description.append(DeclareLaunchArgument('s04_12', default_value='false'))

    description_cond1 = set_conditioned_launch_configuration(s00_02,
                            IfCondition(LaunchConfiguration('s00_02')))
    description_cond2 = set_conditioned_launch_configuration(s03,
                            IfCondition(LaunchConfiguration('s03')))
    description_cond3 = set_conditioned_launch_configuration(s04_12,
                            IfCondition(LaunchConfiguration('s04_12')))

    description = description + description_cond1 + description_cond2 + description_cond3

    # Declare and set launch prefix based on the parameter gdb
    description.append(DeclareLaunchArgument('launch_prefix', default_value=''))
    # I hate openning a new terminal. But there is no way to input any commands to gdb in the current terminal.
    # See discussions at https://github.com/ros2/launch_ros/issues/165
    # You can change `gnome-terminal --` to another terminal, such as `xterm -e`
    description.append(SetLaunchConfiguration(
        name='launch_prefix', value='gnome-terminal -- gdb -ex run --args',
        condition=IfCondition(LaunchConfiguration("gdb"))))

    # Launch the tracker node
    namespace = LaunchConfiguration('namespace')
    tracker_name = ['univloc_tracker_', LaunchConfiguration('ID')]
    description.append(Node(
        namespace=namespace,
        package='univloc_tracker',
        executable='univloc_tracker_ros',
        name=tracker_name,
        output='screen',
        additional_env={'SPDLOG_LEVEL': LaunchConfiguration("log_level")},
        prefix=LaunchConfiguration("launch_prefix"),
        parameters=[set_configurable_parameters(configParams)],
        on_exit = EmitEvent(event=Shutdown())
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
