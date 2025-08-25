# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import os
import sys
import yaml

import launch
from launch.actions import DeclareLaunchArgument, SetLaunchConfiguration, TimerAction
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
    # Declare parameters
    configFilePath = os.path.join(get_package_share_directory('univloc_tracker'),'config','nav_tracker.yaml')

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

    # Launch the server node
    description.append(Node(
        package='univloc_server',
        executable='univloc_server',
        name=['univloc_server'],
        output='screen',
        additional_env={'SPDLOG_LEVEL': LaunchConfiguration("server_log_level")},
        parameters=[set_configurable_parameters(configParams)],
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
        condition=IfCondition(LaunchConfiguration("server_rviz"))
    ))

    remappings = [('/tf', 'tf'),
        ('/tf_static', 'tf_static'),
        ('/univloc_tracker_0/map', 'map')]

    tracker_name = ['univloc_tracker_', LaunchConfiguration('ID')]
    namespace = LaunchConfiguration('namespace')
    
    tracker_node = Node(
        namespace=namespace,
        package='univloc_tracker',
        executable='univloc_tracker_ros',
        name=tracker_name,
        output='screen',
        additional_env={'SPDLOG_LEVEL': LaunchConfiguration("tracker_log_level")},
        parameters=[set_configurable_parameters(configParams)],
        remappings=remappings,
    )
    
    launch_tracker_timer = TimerAction(period=2.0, actions=[tracker_node])

    # Launch the tracker node
    description.append(launch_tracker_timer)

    # We don't add namespace to the camera topic name. 
    # We leave it up to the user to provide the camera name and to include the namespace.
    description.append(SetLaunchConfiguration(
        name='image_topic', value=['/', LaunchConfiguration('camera'), '/color/image_raw'],
        condition=IfCondition(PythonExpression([LaunchConfiguration('image_topic'), " == '""'"]))))

    # Launch rviz
    rviz_config = os.path.join(get_package_share_directory('univloc_tracker'), 'config', 'rviz2_tracker.rviz')
    
    use_rviz = LaunchConfiguration('tracker_rviz')
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

