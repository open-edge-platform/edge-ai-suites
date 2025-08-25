# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import os
import yaml

import launch
from launch.actions import DeclareLaunchArgument, SetLaunchConfiguration
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition
from ament_index_python.packages import get_package_share_directory

from python_utils import ReplaceString

def declare_configurable_parameters(params):
    return [DeclareLaunchArgument(param, default_value=str(params[param]), description="") for param in params]

def set_configurable_parameters(params):
    return dict([(param, LaunchConfiguration(param)) for param in params])

def generate_launch_description():

    configFilePath = os.path.join(get_package_share_directory('univloc_tracker'),'config','tracker.yaml')

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
    description.append(DeclareLaunchArgument(
        'launch_prefix', default_value=''))
    # I hate openning a new terminal. But there is no way to input any commands to gdb in the current terminal.
    # See discussions at https://github.com/ros2/launch_ros/issues/165
    # You can change `gnome-terminal --` to another terminal, such as `xterm -e`
    description.append(SetLaunchConfiguration(
        name='launch_prefix', value='gnome-terminal -- gdb -ex run --args',
        condition=IfCondition(LaunchConfiguration("gdb"))))

    remappings = [('/tf', 'tf'),
        ('/tf_static', 'tf_static')]

    tracker_name = ['univloc_tracker_', LaunchConfiguration('ID')]
    namespace = LaunchConfiguration('namespace')
    # Launch the tracker node
    description.append(Node(
        namespace=namespace,
        package='univloc_tracker',
        executable='univloc_tracker_ros',
        name=tracker_name,
        output='screen',
        additional_env={'SPDLOG_LEVEL': LaunchConfiguration("log_level")},
        prefix=LaunchConfiguration("launch_prefix"),
        parameters=[set_configurable_parameters(configParams)],
        remappings=remappings,
    ))

    # We don't add namespace to the camera topic name. 
    # We leave it up to the user to provide the camera name and to include the namespace.
    description.append(SetLaunchConfiguration(
        name='image_topic', value=['/', LaunchConfiguration('camera'), '/color/image_raw'],
        condition=IfCondition(PythonExpression(["'", LaunchConfiguration('image_topic'), "' ==  '\"\"' "]))))

    # Launch rviz
    rviz_config = os.path.join(get_package_share_directory('univloc_tracker'), 'config', 'rviz2_tracker.rviz')
    
    use_rviz = LaunchConfiguration('rviz')
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
        output='own_log',
        condition=IfCondition(use_rviz),
        remappings=remappings,
    ))

    return launch.LaunchDescription(description)


if __name__ == '__main__':
    generate_launch_description()
