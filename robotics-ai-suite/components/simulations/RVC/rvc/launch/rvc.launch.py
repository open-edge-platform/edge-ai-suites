#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Intel Corporation
#
# Description: Launch the RVC scenario — one UR5 arm (arm1) shuttling
# cubes between two parallel conveyor belts in a Gazebo simulation.

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    RegisterEventHandler,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.actions import ExecuteProcess
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LOG_LEVEL = "info"


def generate_launch_description():
    ld = LaunchDescription()

    package_path = get_package_share_directory("rvc")
    robot_config_path = get_package_share_directory("robot_config")
    robot_config_launch_dir = os.path.join(robot_config_path, "launch")

    launch_stack = LaunchConfiguration("launch_stack")
    ld.add_action(
        DeclareLaunchArgument(
            "launch_stack",
            default_value="true",
            description="Enable/Disable robot stack components.",
        )
    )

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    ld.add_action(
        DeclareLaunchArgument(
            name="use_sim_time", default_value="true", description="Use simulator time."
        )
    )

    # --- Resource paths for Gazebo asset discovery --------------------------
    # this combines multiple directories into a single GZ_SIM_RESOURCE_PATH,
    # so Gazebo can find all the models and textures.
    prev_env = ""
    if "GZ_SIM_RESOURCE_PATH" in os.environ:
        prev_env = os.environ["GZ_SIM_RESOURCE_PATH"] + ":"

    pkg = Path(package_path)
    rc = Path(robot_config_path)
    gz_paths = [
        pkg / "urdf",
        pkg / "urdf" / "objects",
        pkg / "urdf" / "workcell" / "materials" / "textures",
        rc / "models",
        rc / "models" / "aws_robomaker",
        rc / "urdf" / "ur" / "meshes",
    ]
    env_str = prev_env + ":".join(str(p) for p in gz_paths)
    ld.add_action(AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", env_str))

    # CycloneDDS configuration (raises participant limit; useful for multi-node
    # ROS graphs running alongside Gazebo).
    cyclonedds_config = os.path.join(package_path, "cyclonedds.xml")
    if os.path.exists(cyclonedds_config):
        ld.add_action(
            SetEnvironmentVariable("CYCLONEDDS_URI", f"file://{cyclonedds_config}")
        )

    # --- Gazebo bringup ------------------------------------------------------
    gazebo_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, "gazebo.launch.py")
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "world": os.path.join(package_path, "worlds", "rvc.world"),
        }.items(),
    )
    ld.add_action(gazebo_launch_cmd)

    # --- Conveyor belt 1 (source) -------------------------------------------
    # Belt 1 sits on arm1's +X side. Cubes spawn at its near end and travel
    # along +Y until the arm intercepts them near y = 2.92.
    conveyor_belt1_spawn = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-file",
            os.path.join(package_path, "urdf", "conveyor_belt", "model.sdf"),
            "-name",
            "conveyor_belt1",
            "-x",
            "0.83",
            "-y",
            "2.3",
            "-z",
            "0.08",
            "-unpause",
            "--ros-args",
            "--log-level",
            LOG_LEVEL,
        ],
        output="screen",
    )
    ld.add_action(conveyor_belt1_spawn)

    # --- Conveyor belt 2 (sink) ---------------------------------------------
    # Mirrored across arm1 (base at x=0.18) onto the -X side, yawed 180° so
    # cubes placed at the near end (y ~= 2.92) travel toward y < 0 and then
    # off the belt, where cube_controller despawns them.
    # Belt2 sits at world x=-0.48 (mirrors belt1's ~0.65 m offset from
    # arm1 base) so the place target stays well inside UR5's practical
    # reach envelope.
    # NOTE: ConveyorBeltPlugin advertises a single /conveyor/control
    # service. With two belts sharing the SDF, gz_transport binds the
    # service to whichever belt spawns first (belt1). This is intentional:
    # arm1 only ever needs to stop belt1 for the grasp; belt2 must keep
    # running to carry placed cubes away.
    conveyor_belt2_spawn = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-file",
            os.path.join(package_path, "urdf", "conveyor_belt", "model.sdf"),
            "-name",
            "conveyor_belt2",
            "-x",
            "-0.48",
            "-y",
            "2.3",
            "-z",
            "0.08",
            "-Y",
            "3.14159",
            "-unpause",
            "--ros-args",
            "--log-level",
            LOG_LEVEL,
        ],
        output="screen",
    )
    ld.add_action(conveyor_belt2_spawn)

    # --- ARM1 (UR5) spawn ----------------------------------------------------
    arm1_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, "arm.launch.py")
        ),
        launch_arguments={
            "arm_name": "arm1",
            "x_pos": "0.18",
            "y_pos": "3.0",
            "z_pos": "0.01",
            "yaw": "0.0",
            "pedestal_height": "0.16",
            "use_sim_time": use_sim_time,
            "launch_stack": launch_stack,
        }.items(),
    )
    ld.add_action(arm1_launch_cmd)

    # --- Controllers + RViz --------------------------------------------------
    cube_controller = Node(
        package="rvc",
        executable="cube_controller.py",
        output="screen",
        parameters=[{"use_sim_time": True}],
        arguments=["--ros-args", "--log-level", LOG_LEVEL],
    )

    arm1_controller = Node(
        package="rvc",
        executable="arm1_controller.py",
        output="screen",
        namespace="/arm1",
        parameters=[{"use_sim_time": True, "verbose_conveyor": False}],
        arguments=["--ros-args", "--log-level", LOG_LEVEL],
    )

    # map → world static TF: keeps the arm1 chain anchored to a single
    # navigation-style frame for RViz/MoveIt.
    static_tf_map_world = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_tf_publisher_map_world",
        arguments=[
            "--x",
            "0.0",
            "--y",
            "0.0",
            "--z",
            "0.0",
            "--yaw",
            "0.0",
            "--roll",
            "0",
            "--pitch",
            "0",
            "--frame-id",
            "map",
            "--child-frame-id",
            "world",
        ],
        parameters=[{"use_sim_time": True}],
        output="screen",
    )

    arm1_rviz_file = os.path.join(package_path, "rviz", "arm1_view.rviz")
    arm1_rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        namespace="/arm1",
        output="log",
        arguments=["-d", arm1_rviz_file, "--ros-args", "--log-level", LOG_LEVEL],
    )

    # Spawns gripper_controller via controller_manager once the arm stack is up.
    # PID gains are declared in params/gripper_controller.yaml and loaded at
    # startup via --param-file, removing the need for runtime `ros2 param set` calls.
    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "gripper_controller",
            "-c", "/arm1/controller_manager",
            "--param-file",
            str(Path(package_path) / "params" / "gripper_controller.yaml"),
        ],
        output="screen",
    )

    # Set position_proportional_gain on gz_ros_control for responsive finger/mimic
    # tracking under GazeboSimSystem. Placed here (launch-managed ExecuteProcess)
    # rather than in arm1_controller.py so startup configuration stays in the
    # launch layer. Delayed with the same TimerAction as the rest of the arm stack
    # to ensure gz_ros_control is up before the param set fires.
    gz_ros_control_gain = ExecuteProcess(
        cmd=[
            "ros2", "param", "set",
            "/arm1/gz_ros_control",
            "position_proportional_gain",
            "50.0",
        ],
        output="screen",
    )

    arm_controllers_launch = TimerAction(
        period=10.0,
        actions=[
            static_tf_map_world,
            gz_ros_control_gain,
            gripper_controller_spawner,
            arm1_controller,
            arm1_rviz_node,
        ],
    )

    # Wait for arm1's joint states + parameter service before spawning cubes,
    # so the controller's pick state machine is ready when the first cube
    # arrives at the intercept zone.
    cube_controller_wait = ExecuteProcess(
        cmd=[
            "bash",
            "-c",
            'timeout 30 bash -c "until ros2 topic echo'
            " /arm1/joint_states --once >/dev/null 2>&1 &&"
            " ros2 service list | grep -q"
            " /arm1/ARM1Controller/get_parameters;"
            ' do sleep 0.5; done" &&'
            ' echo "ARM1 ready - starting cube controller"',
        ],
        output="screen",
    )

    cube_controller_launch = RegisterEventHandler(
        OnProcessExit(
            target_action=cube_controller_wait,
            on_exit=[
                LogInfo(msg="Starting cube controller - ARM1 verified operational"),
                cube_controller,
            ],
        )
    )

    ld.add_action(arm_controllers_launch)
    ld.add_action(TimerAction(period=10.0, actions=[cube_controller_wait]))
    ld.add_action(cube_controller_launch)

    return ld
