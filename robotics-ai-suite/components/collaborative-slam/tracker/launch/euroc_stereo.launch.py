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

#===================================#
# Stereo Rectification Params Given #
#===================================#

params1 = {
    # width, height, fx, fy, cx, cy
    'camera_intrinsics': '[752.0, 480.0, 435.2046959714599, 435.2046959714599, 367.4517211914062, 252.2008514404297]',
    # k1, k2, p1, p2, k3
    'camera_distortion': '[0.0, 0.0, 0.0, 0.0, 0.0]',
    'K_left': '[458.654, 0.0, 367.215, 0.0, 457.296, 248.375, 0.0, 0.0, 1.0]',
    'D_left': '[-0.28340811, 0.07395907, 0.00019359, 1.76187114e-05, 0.0]',
    'R_left': '[0.999966347530033, -0.001422739138722922, 0.008079580483432283, 0.001365741834644127, 0.9999741760894847, 0.007055629199258132, -0.008089410156878961, -0.007044357138835809, 0.9999424675829176]',
    'K_right': '[457.587, 0.0, 379.999, 0.0, 456.134, 255.238, 0.0, 0.0, 1.0]',
    'D_right': '[-0.28368365, 0.07451284, -0.00010473, -3.555907e-05, 0.0]',
    'R_right': '[0.9999633526194376, -0.003625811871560086, 0.007755443660172947, 0.003680398547259526, 0.9999684752771629, -0.007035845251224894, -0.007729688520722713, 0.007064130529506649, 0.999945173484644]',
    'focal_x_baseline': '47.90639384423901',
    }

#=======================================#
# Stereo Rectification Params Not Given #
#=======================================#

params2 = {
    # width, height, left camera (fx, fy, cx, cy, fx), right camera (fx, fy, cx, cy)
    'camera_intrinsics': '[752.0, 480.0, 458.654, 457.296, 367.215, 248.375, 457.587, 456.134, 379.999, 255.238]',
    # left camera (k1, k2, p1, p2, k3), right camera (k1, k2, p1, p2, k3)
    'camera_distortion': '[-0.28340811, 0.07395907, 0.00019359, 1.76187114e-05, 0.0, -0.28368365, 0.07451284, -0.00010473, -3.555907e-05, 0.0]',
    # TODO the values can be more precise
    'left_to_right_transform': '[1.0, 0.0, 0.0, 0.11, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]',
    }


def mix_ros1_and_2_env(ros1_path):
    mixed_env = os.environ.copy()
    mixed_env.update({"ROS_PACKAGE_PATH": os.path.join(ros1_path, "share")})
    mixed_env.update({"ROS_ETC_DIR": os.path.join(ros1_path, "etc/ros")})
    mixed_env.update({"ROS_MASTER_URI": "http://localhost:11311"})
    mixed_env.update({"ROS_LOCALHOST_ONLY": "0"})
    mixed_env.update({"ROS_ROOT": os.path.join(ros1_path, "share/ros")})
    ld_path = mixed_env["LD_LIBRARY_PATH"] + ":" + os.path.join(ros1_path, "lib")
    mixed_env.update({"LD_LIBRARY_PATH": ld_path})

    return mixed_env

def declare_configurable_parameters(params):
    return [DeclareLaunchArgument(param, default_value=str(params[param]), description="") for param in params]

def set_conditioned_launch_configuration(params, cond):
    return [SetLaunchConfiguration(name=param, value=params[param],
            condition=cond) for param in params]

def set_configurable_parameters(params):
    return dict([(param, LaunchConfiguration(param)) for param in params])

def generate_launch_description():

    configFilePath = os.path.join(get_package_share_directory('univloc_tracker'),'config','euroc.yaml')

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

    # Set stereo-related parameters
    print("type: {}; value:{}".format(type(configParams['publish_tf']), configParams['publish_tf']))
    print("type: {}; value:{}".format(type(configParams['rectifier_params_given']), configParams['rectifier_params_given']))
    rectifier_params_given = LaunchConfiguration('rectifier_params_given')
    description_cond1 = set_conditioned_launch_configuration(params1,
                            IfCondition(PythonExpression(['"', rectifier_params_given, '".lower() == "true"'])))
    description_cond2 = set_conditioned_launch_configuration(params2,
                            IfCondition(PythonExpression(['"', rectifier_params_given, '".lower() == "false"'])))
    description = description + description_cond1 + description_cond2

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
