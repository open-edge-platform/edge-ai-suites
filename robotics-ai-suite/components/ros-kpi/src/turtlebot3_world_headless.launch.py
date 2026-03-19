#!/usr/bin/env python3
# Headless version of turtlebot3_world.launch.py — gzclient (GUI) removed.
# Copied from /opt/ros/jazzy/share/turtlebot3_gazebo/launch/turtlebot3_world.launch.py
# and modified to omit the gz sim -g (client) process so the launch does not
# require a display and does not crash when running headless.

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    launch_file_dir = os.path.join(get_package_share_directory('turtlebot3_gazebo'), 'launch')
    ros_gz_sim = get_package_share_directory('ros_gz_sim')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    x_pose = LaunchConfiguration('x_pose', default='-2.0')
    y_pose = LaunchConfiguration('y_pose', default='-0.5')

    # Use local fast world (RTF=3, iters=50) by default.
    # Override via: ros2 launch ... world:=/path/to/other.world
    this_dir = os.path.dirname(os.path.abspath(__file__))
    fast_world = os.path.join(this_dir, 'turtlebot3_world_fast.world')
    world = LaunchConfiguration('world', default=fast_world)

    # Server only — GUI client intentionally omitted to avoid display requirement
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': ['-r -s -v2 ', world], 'on_exit_shutdown': 'true'}.items()
    )

    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )

    spawn_turtlebot_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'spawn_turtlebot3.launch.py')
        ),
        launch_arguments={
            'x_pose': x_pose,
            'y_pose': y_pose
        }.items()
    )

    set_env_vars_resources = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(
            get_package_share_directory('turtlebot3_gazebo'),
            'models'))

    ld = LaunchDescription()
    # Declare world arg so it can be overridden from the CLI or parent launch
    from launch.actions import DeclareLaunchArgument
    ld.add_action(DeclareLaunchArgument(
        'world', default_value=fast_world,
        description='Path to Gazebo world file (default: fast world with RTF=3, iters=50)'
    ))
    ld.add_action(gzserver_cmd)
    # gzclient_cmd deliberately omitted — no GUI window
    ld.add_action(spawn_turtlebot_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(set_env_vars_resources)

    return ld
