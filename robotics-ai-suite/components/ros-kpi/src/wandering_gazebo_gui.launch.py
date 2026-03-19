#!/usr/bin/env python3
# Local GUI version of wandering_gazebo.launch.py.
# Identical to the system wandering_gazebo_tutorial launch EXCEPT:
#   - Uses turtlebot3_world_gui.launch.py (our server+client, accepts world:=<path>)
#   - Accepts world:=<full_path_to_.world_file> instead of a template name
#   - Default world: turtlebot3_world_fast.world (RTF=3, iters=50)
#   - Stock world override: world:=/opt/ros/jazzy/share/turtlebot3_gazebo/worlds/turtlebot3_world.world
#
# This allows us to drive the 4-permutation comparison:
#   headless+stock / headless+fast / gui+stock / gui+fast

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup_dir = get_package_share_directory('nav2_bringup')
    turtlebot3_dir = get_package_share_directory('turtlebot3_gazebo')
    rtabmap_dir = get_package_share_directory('rtabmap_demos')
    gazebo_tutorial_dir = get_package_share_directory('wandering_gazebo_tutorial')

    this_dir = os.path.dirname(os.path.abspath(__file__))
    gui_world_launch = os.path.join(this_dir, 'turtlebot3_world_gui.launch.py')
    fast_world = os.path.join(this_dir, 'turtlebot3_world_fast.world')

    ros_distro = os.environ.get('ROS_DISTRO', 'jazzy')
    if ros_distro == 'humble':
        default_params_file = os.path.join(bringup_dir, 'params', 'nav2_params.yaml')
    else:
        default_params_file = os.path.join(gazebo_tutorial_dir, 'params', 'nav2_params_jazzy.yaml')

    use_sim_time = LaunchConfiguration('use_sim_time')
    use_rviz = LaunchConfiguration('use_rviz')
    log_level = LaunchConfiguration('log_level')
    params_file = LaunchConfiguration('params_file')
    world = LaunchConfiguration('world')

    ld = LaunchDescription()
    ld.add_action(SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'))
    ld.add_action(SetEnvironmentVariable('TURTLEBOT3_MODEL', 'waffle'))
    ld.add_action(
        SetEnvironmentVariable('GAZEBO_MODEL_PATH', os.path.join(turtlebot3_dir, 'models'))
    )

    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation (Gazebo) clock if true'
    ))
    ld.add_action(DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Start navigation configured RViz'
    ))
    ld.add_action(DeclareLaunchArgument(
        'params_file', default_value=default_params_file,
        description='Full path to the ROS2 parameters file'
    ))
    ld.add_action(DeclareLaunchArgument(
        'log_level', default_value='info',
        description='log level'
    ))
    ld.add_action(DeclareLaunchArgument(
        'world', default_value=fast_world,
        description='Full path to Gazebo world file (default: fast world RTF=3)'
    ))

    param_substitutions = {'use_sim_time': use_sim_time}
    nav_launch_arguments = {
        'use_sim_time': use_sim_time,
        'params_file': params_file,
    }

    ld.add_action(
        GroupAction(actions=[
            # World: server + GUI client, world file path passed through
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(gui_world_launch),
                launch_arguments={'world': world, **param_substitutions}.items(),
            ),
            TimerAction(period=1.5, actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(rtabmap_dir, 'launch', 'turtlebot3/turtlebot3_scan.launch.py')
                    ),
                    launch_arguments=param_substitutions.items(),
                )
            ]),
            TimerAction(period=2.5, actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(bringup_dir, 'launch', 'navigation_launch.py')
                    ),
                    launch_arguments=nav_launch_arguments.items(),
                )
            ]),
            TimerAction(period=3.5, actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(bringup_dir, 'launch', 'rviz_launch.py')
                    ),
                    condition=IfCondition(use_rviz),
                    launch_arguments=param_substitutions.items(),
                )
            ]),
            TimerAction(period=4.0, actions=[
                Node(
                    package='wandering_app',
                    executable='wandering',
                    name='wandering',
                    output='screen',
                    parameters=[param_substitutions],
                    arguments=['--ros-args', '--log-level', log_level],
                )
            ]),
        ])
    )

    return ld
