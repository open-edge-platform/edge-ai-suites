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
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LOG_LEVEL = 'info'


def generate_launch_description():
    declare_arm_name = DeclareLaunchArgument(
        'arm_name', default_value='arm1', description='Name of the arm robot'
    )

    declare_x_pos = DeclareLaunchArgument(
        'x_pos', default_value='0.0', description='X position for arm spawn'
    )

    declare_y_pos = DeclareLaunchArgument(
        'y_pos', default_value='0.0', description='Y position for arm spawn'
    )

    declare_z_pos = DeclareLaunchArgument(
        'z_pos', default_value='0.01', description='Z position for arm spawn'
    )

    declare_yaw = DeclareLaunchArgument(
        'yaw', default_value='0.0', description='Yaw orientation for arm spawn'
    )

    declare_pedestal_height = DeclareLaunchArgument(
        'pedestal_height', default_value='0.8', description='Default pedestal height'
    )

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true', description='Use simulator time'
    )

    declare_mode = DeclareLaunchArgument(
        'mode', default_value='full', description='Launch mode: full, gazebo, or stack'
    )

    # Use OpaqueFunction to create actions during launch file parse time.
    # Otherwise multiple call to this launch file will result
    # in overriding previous launch configuration dictionary values.

    return LaunchDescription(
        [
            declare_arm_name,
            declare_x_pos,
            declare_y_pos,
            declare_z_pos,
            declare_yaw,
            declare_pedestal_height,
            declare_use_sim_time,
            declare_mode,
            OpaqueFunction(function=launch_setup),
        ]
    )


def launch_setup(context: LaunchContext):
    arm_name = context.launch_configurations['arm_name']
    arm_namespace = '/' + arm_name
    robot_urdf = get_robot_urdf(
        arm_name,
        context.launch_configurations['pedestal_height'],
        context.launch_configurations.get('x_pos', '0.0'),
        context.launch_configurations.get('y_pos', '0.0'),
        context.launch_configurations.get('z_pos', '0.0'),
        context.launch_configurations.get('yaw', '0.0'),
    )

    # Convert use_sim_time string to boolean
    use_sim_time_bool = context.launch_configurations['use_sim_time'].lower() == 'true'

    robot_params = {
        'robot_description': robot_urdf,
        'use_sim_time': use_sim_time_bool,
    }

    if 'mode' in context.launch_configurations:
        mode = context.launch_configurations['mode']
    else:
        mode = 'full'

    actions = []

    # If launch request with Full or Gazebo only mode.
    if mode == 'full' or mode == 'gazebo':
        robot_state_publisher = Node(
            package='robot_state_publisher',
            namespace=arm_namespace,
            executable='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_urdf,
                'use_sim_time': use_sim_time_bool,
                'publish_frequency': 50.0,  # Reasonable publishing rate
            }],
            arguments=['--ros-args', '--log-level', 'warn'],
        )

        robot_spawn_entity = Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[
                '-string', robot_urdf,
                '-name', arm_name,
                # ❌ REMOVED: x, y, z, Y spawn coordinates
                # Gazebo spawn coordinates create world→base_link directly,
                # bypassing URDF's world→pedestal→base_link chain.
                # Instead, world_joint in URDF handles positioning.
            ],
            output='screen',
        )

        # Start robot state publisher immediately
        actions.append(robot_state_publisher)
        # Start robot spawn entity immediately (no delay needed with -string approach)
        actions.append(robot_spawn_entity)

        message = """ {
                'header': {
                    'stamp': {
                    'sec': 0,
                    'nanosec': 0
                    },
                    'frame_id': ''
                },
                'joint_names': [
                    '""" + arm_name + """/shoulder_pan_joint',
                    '""" + arm_name + """/shoulder_lift_joint',
                    '""" + arm_name + """/elbow_joint',
                    '""" + arm_name + """/wrist_1_joint',
                    '""" + arm_name + """/wrist_2_joint',
                    '""" + arm_name + """/wrist_3_joint'
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

        controller_run_state = 'active'
        if os.environ.get('ROS_DISTRO') == 'foxy':
            controller_run_state = 'start'

        # Set initial joint position for robot - needed for all ROS distros
        set_initial_pose = ExecuteProcess(
            cmd=[
                'ros2',
                'topic',
                'pub',
                '--once',
                arm_namespace + '/arm_controller/joint_trajectory',
                'trajectory_msgs/msg/JointTrajectory',
                message,
            ],
            output='screen',
        )

        load_joint_state_controller = ExecuteProcess(
            cmd=[
                'bash', '-c',
                'for i in 1 2 3 4 5; do '
                '  ros2 run controller_manager spawner '
                '  joint_state_broadcaster '
                '  -c ' + arm_namespace + '/controller_manager && break; '
                '  echo "joint_state_broadcaster spawn attempt $i failed, retrying in 3s..."; '
                '  sleep 3; '
                'done',
            ],
            output='screen',
        )

        load_arm_trajectory_controller = ExecuteProcess(
            cmd=[
                'bash', '-c',
                'for i in 1 2 3 4 5; do '
                '  ros2 run controller_manager spawner '
                '  arm_controller '
                '  -c ' + arm_namespace + '/controller_manager && break; '
                '  echo "arm_controller spawn attempt $i failed, retrying in 3s..."; '
                '  sleep 3; '
                'done',
            ],
            output='screen',
        )

        load_gripper_controller = ExecuteProcess(
            cmd=[
                'bash', '-c',
                'for i in 1 2 3 4 5; do '
                '  ros2 run controller_manager spawner gripper_controller '
                '  -c ' + arm_namespace + '/controller_manager && break; '
                '  echo "gripper_controller spawn attempt $i failed, retrying in 3s..."; '
                '  sleep 3; '
                'done',
            ],
            output='screen',
        )

        # Wait for controllers to be active before starting MoveIt
        wait_for_controllers = ExecuteProcess(
            cmd=[
                'ros2',
                'control',
                'list_controllers',
                '--controller-manager',
                arm_namespace + '/controller_manager',
                '--verbose'
            ],
            output='screen',
        )

        state_controller_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=robot_spawn_entity,
                on_exit=[
                    TimerAction(
                        period=10.0,  # Wait 10 seconds for gz_ros2_control to fully initialize
                        actions=[load_joint_state_controller]
                    )
                ],
            )
        )

        actions.append(state_controller_event)

        arm_controller_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_joint_state_controller,
                on_exit=[
                    TimerAction(
                        period=3.0,  # Wait 3 seconds after joint_state_broadcaster loads
                        actions=[load_arm_trajectory_controller]
                    )
                ],
            )
        )
        actions.append(arm_controller_event)

        gripper_controller_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_arm_trajectory_controller,
                on_exit=[
                    TimerAction(
                        # Wait 5s after arm_controller loads
                        period=5.0,
                        actions=[load_gripper_controller]
                    )
                ],
            )
        )
        actions.append(gripper_controller_event)

        event_after = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_gripper_controller,
                on_exit=[set_initial_pose],
            )
        )
        actions.append(event_after)

    else:
        # If stack launch mode, then create empty launch description for rest of actions.
        robot_state_publisher = LaunchDescription()
        robot_spawn_entity = LaunchDescription()
        robot_spawn_entity_event = LaunchDescription()
        state_controller_event = LaunchDescription()
        arm_controller_event = LaunchDescription()
        event_after = LaunchDescription()

    # Create stack node
    if mode == 'full' or mode == 'stack':
        move_group_node = prepare_stack_node(arm_namespace, robot_urdf, arm_name=arm_name)
        if mode == 'full':
            # Wait for arm trajectory controller before starting move_group
            move_group_node_event = RegisterEventHandler(
                event_handler=OnProcessExit(
                    target_action=load_arm_trajectory_controller,
                    on_exit=[move_group_node],
                )
            )
        else:
            move_group_node_event = move_group_node

        actions.append(move_group_node_event)

    # Check if wait_on is provided.  If exist then create a dependency action on it
    if 'wait_on' in context.launch_configurations:
        wait_on = context.launch_configurations['wait_on'].split(' ')
        wait_for_action_server = ExecuteProcess(
            cmd=['ros2', 'run', 'robot_config', 'wait_for_interface.py', wait_on[0], wait_on[1]],
            output='screen',
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

    # Add Gazebo Bridge nodes
    if mode == 'full' or mode == 'gazebo':
        # Joint states bridge
        gz_ros_bridge_joint_states = Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            arguments=[
                f'{arm_namespace}/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
            ],
            output='screen',
        )

        # NOTE: Gripper is now controlled via ros2_control with effort interface
        # No need for DetachableJoint bridge - using friction-based grasping

        # Add bridge nodes to actions
        actions.extend([
            gz_ros_bridge_joint_states
        ])

    return actions


def prepare_stack_node(
    namespace, robot_urdf, robot_type='ur5', use_sim_time=True, arm_name='arm1'
):
    package_path = get_package_share_directory('robot_config')

    # Use namespaced robot_description parameter
    robot_description = {'robot_description': robot_urdf}

    kinematics_yaml = load_yaml(package_path, 'config/ur/' + robot_type + '/kinematics.yaml')
    robot_description_kinematics = {'robot_description_kinematics': kinematics_yaml}

    robot_description_semantic_config = load_file(
        package_path, 'config/ur/' + robot_type + '/robot.srdf'
    )

    # Add arm prefix to joint and link names in SRDF for multi-robot support
    prefix = arm_name + '/'

    # Prefix all link names in collision exemptions
    link_names = [
        'base_link_inertia', 'pedestal', 'shoulder_link', 'upper_arm_link',
        'forearm_link', 'wrist_1_link', 'wrist_2_link', 'wrist_3_link', 'ee_link',
        'gripper_base', 'left_finger', 'right_finger',
        'vacuum_gripper1', 'vacuum_gripper2', 'vacuum_gripper_base'
    ]

    for link_name in link_names:
        robot_description_semantic_config = robot_description_semantic_config.replace(
            f'link1="{link_name}"', f'link1="{prefix}{link_name}"'
        ).replace(
            f'link2="{link_name}"', f'link2="{prefix}{link_name}"'
        )

    # Prefix joint names
    robot_description_semantic_config = robot_description_semantic_config.replace(
        'name="elbow_joint"', f'name="{prefix}elbow_joint"'
    ).replace(
        'name="shoulder_pan_joint"', f'name="{prefix}shoulder_pan_joint"'
    ).replace(
        'name="shoulder_lift_joint"', f'name="{prefix}shoulder_lift_joint"'
    ).replace(
        'name="wrist_1_joint"', f'name="{prefix}wrist_1_joint"'
    ).replace(
        'name="wrist_2_joint"', f'name="{prefix}wrist_2_joint"'
    ).replace(
        'name="wrist_3_joint"', f'name="{prefix}wrist_3_joint"'
    ).replace(
        'child_link="base_link"', f'child_link="{prefix}base_link"'
    )

    robot_description_semantic = {'robot_description_semantic': robot_description_semantic_config}

    # Load OMPL planning configuration from YAML
    ompl_planning_yaml = load_yaml(
        package_path, 'config/ur/' + robot_type + '/ompl_planning.yaml'
    )

    # Create properly formatted OMPL config
    ompl_planning_pipeline_config = {
        'ompl': {
            'planning_plugins': ['ompl_interface/OMPLPlanner'],
            'request_adapters': [
                'default_planning_request_adapters/ResolveConstraintFrames',
                'default_planning_request_adapters/ValidateWorkspaceBounds',
                'default_planning_request_adapters/CheckStartStateBounds',
                'default_planning_request_adapters/CheckStartStateCollision',
            ],
            'response_adapters': [
                'default_planning_response_adapters/AddTimeOptimalParameterization',
                'default_planning_response_adapters/ValidateSolution',
                'default_planning_response_adapters/DisplayMotionPath',
            ],
            'start_state_max_bounds_error': 0.1,
        },
    }

    ompl_planning_yaml = load_yaml(package_path, 'config/ur/' + robot_type + '/ompl_planning.yaml')

    ompl_planning_pipeline_config['ompl'].update(ompl_planning_yaml)

    joint_limits_yaml = load_yaml(
        package_path, 'config/ur/' + robot_type + '/joint_limits_planning.yaml'
    )

    # Add arm prefix to joint names in joint_limits for multi-robot support
    prefix = arm_name + '/'
    prefixed_joint_limits = {'joint_limits': {}}
    for joint_name, limits in joint_limits_yaml['joint_limits'].items():
        prefixed_joint_limits['joint_limits'][prefix + joint_name] = limits

    joint_limits = {'robot_description_planning': prefixed_joint_limits}

    # Trajectory Execution Functionality
    controller_manager_config_name = (
        'moveit_controller_manager_' + arm_name.replace('/', '') + '.yaml'
    )
    moveit_simple_controllers_yaml = load_yaml(
        package_path, 'config/ur/' + robot_type + '/' + controller_manager_config_name
    )

    moveit_controllers = {
        'moveit_simple_controller_manager': moveit_simple_controllers_yaml,
        'moveit_controller_manager': (
            'moveit_simple_controller_manager'
            '/MoveItSimpleControllerManager'
        ),
    }

    trajectory_execution = {
        'moveit_manage_controllers': True,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.01,
        'trajectory_execution.execution_duration_monitoring': True,
        'trajectory_execution.controller_connection_timeout': 30.0,
    }

    planning_scene_monitor_parameters = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
        'publish_robot_description': True,
        'publish_robot_description_semantic': True,
        'default_planning_pipeline': 'ompl',
        'use_sim_time': use_sim_time,
        'publish_octomap_updates': False,
    }

    planning_pipelines = {
        'planning_pipelines': ['ompl'],
        'default_planning_pipeline': 'ompl',
    }

    # https://industrial-training-master.readthedocs.io/en/foxy/_source/session3/ros2/3-Build-a-MoveIt-Package.html
    # Start the actual move_group node/action server

    robot_move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        namespace=namespace,
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            robot_description_kinematics,
            ompl_planning_pipeline_config,
            trajectory_execution,
            moveit_controllers,
            planning_scene_monitor_parameters,
            joint_limits,
            planning_pipelines,
            {'planning_plugins': ['ompl_interface/OMPLPlanner'], 'use_sim_time': use_sim_time},
        ],
        arguments=['--ros-args', '--log-level', LOG_LEVEL],
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


def get_robot_urdf(arm_name, pedestal_height, x_pos='0.0', y_pos='0.0', z_pos='0.0', yaw='0.0'):
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    robot_type = 'ur5'
    package_path = get_package_share_directory('robot_config')

    # Generate controller config with prefixed joint names
    prefix = arm_name + '/'
    controller_config = {
        'controller_manager': {
            'ros__parameters': {
                'update_rate': 100,
                'use_sim_time': True,
                'arm_controller': {
                    'type': 'joint_trajectory_controller/JointTrajectoryController'
                },
                'gripper_controller': {
                    'type': 'joint_trajectory_controller/JointTrajectoryController'
                },
                'joint_state_broadcaster': {
                    'type': 'joint_state_broadcaster/JointStateBroadcaster'
                }
            }
        },
        'arm_controller': {
            'ros__parameters': {
                'joints': [
                    f'{prefix}shoulder_pan_joint',
                    f'{prefix}shoulder_lift_joint',
                    f'{prefix}elbow_joint',
                    f'{prefix}wrist_1_joint',
                    f'{prefix}wrist_2_joint',
                    f'{prefix}wrist_3_joint'
                ],
                'command_interfaces': ['position', 'velocity'],
                'state_interfaces': ['position', 'velocity'],
                'state_publish_rate': 100.0,
                'action_monitor_rate': 20.0,
                'allow_partial_joints_goal': False,
                'constraints': {
                    'stopped_velocity_tolerance': 0.0,
                    'goal_time': 0.0,
                    f'{prefix}shoulder_pan_joint': {'trajectory': 0.25, 'goal': 0.1},
                    f'{prefix}shoulder_lift_joint': {'trajectory': 0.25, 'goal': 0.1},
                    f'{prefix}elbow_joint': {'trajectory': 0.25, 'goal': 0.1},
                    f'{prefix}wrist_1_joint': {'trajectory': 0.25, 'goal': 0.1},
                    f'{prefix}wrist_2_joint': {'trajectory': 0.25, 'goal': 0.1},
                    f'{prefix}wrist_3_joint': {'trajectory': 0.25, 'goal': 0.1}
                },
                'use_sim_time': True
            }
        },
        'gripper_controller': {
            'ros__parameters': {
                'joints': [f'{prefix}left_finger_joint'],
                'command_interfaces': ['position', 'velocity'],
                'state_interfaces': ['position', 'velocity'],
                'state_publish_rate': 100.0,
                'action_monitor_rate': 20.0,
                'allow_partial_joints_goal': False,
                'constraints': {
                    'stopped_velocity_tolerance': 0.0,
                    'goal_time': 0.0,
                },
                'use_sim_time': True
            }
        }
    }

    # Build YAML with two top-level entries:
    # 1. /**  — wildcard that applies position_proportional_gain to ALL nodes
    #    (ensures gz_ros_control node picks it up regardless of namespace matching)
    # 2. arm_name — controller-specific params under the arm's namespace
    import tempfile
    import yaml
    yaml_content = {
        '/**': {
            'ros__parameters': {
                'position_proportional_gain': 50.0,
            }
        },
        arm_name: controller_config,
    }
    temp_controller_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(yaml_content, temp_controller_file, default_flow_style=False)
    controller_paramfile = temp_controller_file.name
    temp_controller_file.close()

    xacro_path = os.path.join(package_path, 'urdf', 'ur', 'ur5', 'ur_urdf.xacro')

    robot_doc = xacro.process_file(
        xacro_path,
        mappings={
            'name': arm_name,
            'namespace': '/' + arm_name,
            'sim_gazebo': '1',
            'simulation_controllers': controller_paramfile,
            'safety_limits': 'true',
            'prefix': arm_name + '/',
            'pedestal_height': str(pedestal_height),
            'use_gripper': 'true',
            'spawn_x': str(x_pos),
            'spawn_y': str(y_pos),
            'spawn_z': str(z_pos),
            'spawn_yaw': str(yaw),
        },
    )

    robot_urdf = robot_doc.toprettyxml(indent='  ')
    return robot_urdf
