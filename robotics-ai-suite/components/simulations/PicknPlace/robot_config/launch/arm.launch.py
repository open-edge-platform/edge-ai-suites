#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

# Description: Helper launch file to spawn UR5 ARM in Gazebo separated by namespace
# Example usage:
#    arm1_launch_cmd = IncludeLaunchDescription(
#           PythonLaunchDescriptionSource(
#           os.path.join(robot_config_launch_dir, 'arm.launch.py')),
#           launch_arguments={ 'arm_name': 'arm1',
#                           'x_pos': '2.0',
#                           'y_pos': '2.0',
#                           'z_pos': '0.01',
#                           'yaw': '0.0',
#                           'pedestal_height': '0.16',
#                           'use_sim_time': 'true',
#                           'launch_stack': 'true',
#                           'wait_on': 'service /spawn_entity'
#                          }.items()
#                        )
#    ld.add_action(arm1_launch_cmd)

import os
import yaml
import xacro

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml

LOG_LEVEL = 'info'

def generate_launch_description():

    declare_pedestal_height = DeclareLaunchArgument('pedestal_height', default_value='0.16',
                                         description='Default pedestal height')
    
    # Use OpaqueFunction to create actions during launch file parse time.
    # Otherwise multiple call to this launch file will result in overriding previous launch configuration dictionary values.

    return LaunchDescription([
        declare_pedestal_height,
        OpaqueFunction(function = launch_setup),
        ])

def launch_setup(context: LaunchContext):

    arm_name = context.launch_configurations['arm_name']
    arm_namespace = '/' + arm_name
    robot_urdf = get_robot_urdf(arm_name, context.launch_configurations['pedestal_height'])

    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    robot_params = {'robot_description': robot_urdf,
                    'use_sim_time': bool(context.launch_configurations['use_sim_time'])}
    
    if 'mode' in context.launch_configurations:
        mode = context.launch_configurations['mode']
    else:
        mode = 'full'
    
    actions=[]
    clear_namespace_after = None

    # If launch request with Full or Gazebo only mode.
    if mode == 'full' or mode == 'gazebo' :
        robot_state_publisher = Node(
            package='robot_state_publisher',
            namespace=arm_namespace,
            executable='robot_state_publisher',
            output='screen',
            remappings=remappings,
            parameters=[robot_params],
            arguments=['--ros-args', '--log-level', 'warn']
        )

        robot_spawn_entity = Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-topic', arm_namespace + '/robot_description',
                '-entity', arm_name,
                '-robot_namespace', arm_namespace,
                '-x', context.launch_configurations['x_pos'],
                '-y', context.launch_configurations['y_pos'],
                '-z', context.launch_configurations['z_pos'],
                '-Y', context.launch_configurations['yaw'],
                '-unpause',
            ],
            output='screen',
        )

        clear_namespace_before = ExecuteProcess(
            cmd=[
                'ros2', 'service', 'call', '/clear_namespace', 'std_srvs/srv/Empty',
            ], output='screen',
        )
        
        robot_spawn_entity_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=clear_namespace_before,
                on_exit=[robot_state_publisher, robot_spawn_entity],
            )
        )

        actions.append(clear_namespace_before)
        actions.append(robot_spawn_entity_event)

        message = """ {
                'header': {
                    'stamp': {
                    'sec': 0,
                    'nanosec': 0
                    },
                    'frame_id': ''
                },
                'joint_names': [
                    'shoulder_pan_joint',
                    'shoulder_lift_joint',
                    'elbow_joint',
                    'wrist_1_joint',
                    'wrist_2_joint',
                    'wrist_3_joint'
                ],
                'points': [
                    {
                    'positions': [0.0, -1.22, 0.59, -0.94, -1.59, 0.0],
                    'velocities': [],
                    'accelerations': [],
                    'effort': [],
                    'time_from_start': {
                        'sec': 1,
                        'nanosec': 0
                    }
                    }
                ]
                }"""

        set_initial_pose = LaunchDescription()

        controller_run_state = 'active'
        if os.environ.get('ROS_DISTRO') == 'foxy':
            controller_run_state = 'start'

            # Set initial joint position for robot.   This step is not needed for Humble
            # Redundant for Humble since in Humble, initial positions are taken from initial_positions.yaml and set by ros2 control plugin
            set_initial_pose = ExecuteProcess(
                cmd=[
                    "ros2",
                    "topic",
                    "pub",
                    "--once",
                    [arm_namespace, "/arm_controller/joint_trajectory"],
                    "trajectory_msgs/msg/JointTrajectory",
                    message,
                ],
                output="screen",
            )

        load_joint_state_controller = ExecuteProcess(
            cmd=[
                'ros2', 'control', 'load_controller', '--set-state',
                controller_run_state, 'joint_state_broadcaster',
                '-c', arm_namespace + '/controller_manager',
            ],
            output='screen',
        )

        load_arm_trajectory_controller = ExecuteProcess(
            cmd=[
                'ros2', 'control', 'load_controller',
                '--set-state', controller_run_state, 'arm_controller',
                '-c', arm_namespace + '/controller_manager',
            ],
            output='screen',
        )

        state_controller_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=robot_spawn_entity,
                on_exit=[load_joint_state_controller],
            )
        )

        actions.append(state_controller_event)

        arm_controller_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_joint_state_controller,
                on_exit=[load_arm_trajectory_controller],
            )
        )
        actions.append(arm_controller_event)

        clear_namespace_after = ExecuteProcess(
                cmd=[
                    'ros2', 'service', 'call', '/clear_namespace', 'std_srvs/srv/Empty',
                ], output='screen',
            )

        clear_namespace_event_after = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=load_arm_trajectory_controller,
            on_exit=[clear_namespace_after, set_initial_pose],
            )
        )        
        actions.append(clear_namespace_event_after)

    else:
        # If stack launch mode, then create empty launch description for rest of actions.
        robot_state_publisher = LaunchDescription()
        robot_spawn_entity = LaunchDescription()
        clear_namespace_before = LaunchDescription()
        robot_spawn_entity_event = LaunchDescription()
        state_controller_event = LaunchDescription()
        arm_controller_event = LaunchDescription()
        clear_namespace_event_after = LaunchDescription()

    # Initialize action with clear name space
    clear_namespace_event_before = clear_namespace_before

    # Create stack node
    if mode == 'full' or mode == 'stack':
        move_group_node = prepare_stack_node(arm_namespace, robot_urdf)
        move_group_node_event = move_group_node
        if mode == 'full':
            move_group_node_event = RegisterEventHandler(
                    event_handler=OnProcessExit(
                        target_action=clear_namespace_after,
                        on_exit=[move_group_node],
                    )
                )
        
        actions.append(move_group_node_event)
    
    # Check if wait_on is provided.  If exist then create a dependency action on it
    if "wait_on" in context.launch_configurations:
        wait_on = context.launch_configurations['wait_on'].split(' ')
        wait_for_action_server = ExecuteProcess(
                cmd=[
                    'ros2', 'run', 'robot_config', 'wait_for_interface.py', wait_on[0],
                    wait_on[1]
                ], output='screen',
            )

        action = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=wait_for_action_server,
                on_exit=actions,
            )
        )

        actions = [wait_for_action_server, action]

    else:
        # Empty action server
        wait_for_action_server = LaunchDescription()

    return actions

def prepare_stack_node(namespace, robot_urdf, robot_type='ur5', use_sim_time=True):

    package_path = get_package_share_directory('robot_config')
    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    robot_description = {"robot_description": robot_urdf}

    kinematics_yaml = load_yaml(
        package_path, "config/ur/" + robot_type + "/kinematics.yaml"
    )

    robot_description_semantic_config = load_file(
        package_path, "config/ur/" + robot_type + "/robot.srdf"
    )
    robot_description_semantic = {
        "robot_description_semantic": robot_description_semantic_config
    }

    # Planning Functionality
    ompl_planning_pipeline_config = {
        "ompl": {
            "planning_plugin": "ompl_interface/OMPLPlanner",
            "request_adapters": "default_planner_request_adapters/AddTimeOptimalParameterization default_planner_request_adapters/FixWorkspaceBounds default_planner_request_adapters/FixStartStateBounds default_planner_request_adapters/FixStartStateCollision default_planner_request_adapters/FixStartStatePathConstraints",
            "start_state_max_bounds_error": 0.1,
        },
    }

    ompl_planning_yaml = load_yaml(
        package_path, "config/ur/" + robot_type + "/ompl_planning.yaml"
    )

    ompl_planning_pipeline_config["ompl"].update(ompl_planning_yaml)

    joint_limits_yaml = load_yaml(
        package_path, "config/ur/" + robot_type + "/joint_limits_planning.yaml"
    )

    joint_limits = {"robot_description_planning": joint_limits_yaml}

    # Trajectory Execution Functionality
    moveit_simple_controllers_yaml = load_yaml(
        package_path,
        "config/ur/" + robot_type + "/moveit_controller_manager.yaml"
    )

    moveit_controllers = {
        "moveit_simple_controller_manager": moveit_simple_controllers_yaml,
        "moveit_controller_manager":
        "moveit_simple_controller_manager/MoveItSimpleControllerManager",
    }

    trajectory_execution = {
        "moveit_manage_controllers": True,
        "trajectory_execution.allowed_execution_duration_scaling": 1.2,
        "trajectory_execution.allowed_goal_duration_margin": 0.5,
        "trajectory_execution.allowed_start_tolerance": 0.01,
        "trajectory_execution.execution_duration_monitoring": True,
        "trajectory_execution.controller_connection_timeout": 30.0,
    }

    planning_scene_monitor_parameters = {
        "publish_planning_scene": True,
        "publish_geometry_updates": True,
        "publish_state_updates": True,
        "publish_transforms_updates": True,
        "publish_transforms_updates": True, 
        "publish_robot_description": True, 
        "publish_robot_description_semantic": True,
        "default_planning_pipeline": "ESTkConfigDefault",
        "use_sim_time": use_sim_time,
    }

    pipeline_names = {"pipeline_names": ["ompl"]}

    planning_pipelines = {
        "planning_pipelines": pipeline_names,
        "default_planning_pipeline": "ompl",
    }

    # https://industrial-training-master.readthedocs.io/en/foxy/_source/session3/ros2/3-Build-a-MoveIt-Package.html
    # Start the actual move_group node/action server
    robot_move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        namespace=namespace,
        output="screen",
        parameters=[
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            ompl_planning_pipeline_config,
            trajectory_execution,
            moveit_controllers,
            planning_scene_monitor_parameters,
            joint_limits,
            planning_pipelines,
            {"planning_plugin": "ompl", "use_sim_time": use_sim_time},
        ],
        remappings=remappings,
        arguments=["--ros-args", "--log-level", LOG_LEVEL],
    )

    return robot_move_group_node

def load_file(package_path, file_path):

    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return file.read()
    except EnvironmentError:
        return None

def load_yaml(package_path, file_path):

    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except EnvironmentError:
        return None

def get_robot_urdf(arm_name, pedestal_height):
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    robot_type = 'ur5'
    package_path = get_package_share_directory('robot_config')
    param_substitutions = {'use_sim_time': use_sim_time}
    configured_params = RewrittenYaml(
        source_file=package_path + '/config/ur/' + robot_type + '/ros_controllers_robot.yaml',
        root_key=arm_name,
        param_rewrites=param_substitutions,
        convert_types=True,
    )

    context = LaunchContext()
    controller_paramfile = configured_params.perform(context)

    xacro_path = os.path.join(package_path, 'urdf', 'ur', 'ur5', 'ur_urdf.xacro')

    robot_doc = xacro.process_file(
        xacro_path,
        mappings={
            'name': arm_name,
            'namespace': '/' + arm_name,
            'sim_gazebo': '1',
            'simulation_controllers': controller_paramfile,
            'safety_limits': 'true',
            'prefix': '',
            'pedestal_height': pedestal_height,
        },
    )

    robot_urdf = robot_doc.toprettyxml(indent='  ')
    return robot_urdf
