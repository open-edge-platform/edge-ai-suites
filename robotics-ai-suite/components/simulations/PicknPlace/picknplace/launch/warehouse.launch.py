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

# Description: Launch file spawning one AMR and two ARMs to create PicknPlace scenario

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.event_handlers import OnProcessExit
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess, RegisterEventHandler, TimerAction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LOG_LEVEL = 'info'

def generate_launch_description():

    ld = LaunchDescription()

    package_path = get_package_share_directory('picknplace')
    launch_dir = os.path.join(package_path, 'launch')
    robot_config_path = get_package_share_directory('robot_config')
    robot_config_launch_dir = os.path.join(robot_config_path, 'launch')
    
    launch_stack = LaunchConfiguration('launch_stack')
    declare_launch_stack = DeclareLaunchArgument('launch_stack', default_value='true',
                                         description='Enable/Disable Nav2 launch')
    ld.add_action(declare_launch_stack)

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    declare_use_sim_time = DeclareLaunchArgument(
        name='use_sim_time', default_value='true', description='Use simulator time'
    )
    ld.add_action(declare_use_sim_time)

    # Launch Sequence:
    # Gazebo -> [ConveyorBelt, AMR Spawn] -> [ARM1 Spawn] -> [ARM2 Spawn] -> [Cube and ARM1 Controller, Rviz] 
    prev_env=""
    if 'GAZEBO_MODEL_PATH' in os.environ:
       prev_env = os.environ["GAZEBO_MODEL_PATH"] + ":"
    
    env_str = prev_env + os.path.join(package_path, "urdf") + ":" \
            + os.path.join(package_path, "urdf", "objects") + ":" \
            + os.path.join(robot_config_path, "models") + ":" \
            + os.path.join(robot_config_path, "models", "aws_robomaker") + ":" \
            + os.path.join(robot_config_path, "urdf", "ur", "meshes") 
    
    os.environ["GAZEBO_MODEL_PATH"] = env_str
 
    # Gazebo Environment Launch
    gazebo_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'gazebo.launch.py')),
        launch_arguments={ 'use_sim_time': use_sim_time,
                           'world': os.path.join(
                                        package_path,
                                        'worlds',
                                        'warehouse.world',
                                    )
                          }.items()
                        )
    ld.add_action(gazebo_launch_cmd)

    conveyorbelt_spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-file', os.path.join(package_path, 'urdf', 'conveyor_belt', 'model.sdf'),
            '-entity', 'conveyor_belt',
            '-x', '0.83',
            '-y', '2.3',
            '-z', '0.08',
            '-unpause',
            '--ros-args', '--log-level', LOG_LEVEL,
        ],
        output='screen',
    )
    ld.add_action(conveyorbelt_spawn_entity)

    # Initiate AMR spawning after spawn_entity service available.  
    # This is same as launching imediately but since wait_on arguement is required therefore giving spawn_entity by default.
    # AMR Nav2 stack launch will get triggered too

    amr_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'amr.launch.py')),
        launch_arguments={ 'amr_name': 'amr1',
                           'x_pos': '-0.1',
                           'y_pos': '2.5', #'-3.5',
                           'yaw': '3.14159',
                           'use_sim_time': use_sim_time,
                           'launch_stack': launch_stack,
                           'wait_on': 'service /spawn_entity'
                          }.items()
                        )

    ld.add_action(amr_launch_cmd)

    # Using a global map server to serve all AMR's Nav2 stacks.
    map_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'map.launch.py')),
            launch_arguments={ 'use_sim_time': use_sim_time,
                                'map': os.path.join(
                                            package_path,
                                            "maps",
                                            "warehouse",
                                            "map.yaml"
                                        )
                         }.items()
                        )
    ld.add_action(map_launch_cmd)

    # Launch ARM1 only after the AMR is spawned by Gazebo.  
    # This serialization is needed to maintain separate name space.   Current ros2 control implementation utilizes
    # global variables inside gazebo process to convey namespace between controller manager and ros2 controllers activations.  
    # This will create issue for any other spawning done in between. e.g AMR.
    # See discussions.
    # https://github.com/ros-controls/ros2_control/issues/1073
    # https://github.com/ros-controls/ros2_control/pull/1074
    #
    # This technique is to make sure no other spawning in between UR5 spawn and it's controller activations.  Once joint trajectory
    # controller is activated then clear global namespace in gzserver process via custom plugin and then proceed with other model instantiation involving custom ros nodes.
      
    # Spawn ARM1 only after the AMR (Turtlebot3) is fully spawned in gazebo (e.g /amr1/cmd_vel available)

    arm1_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'arm.launch.py')),
        launch_arguments={ 'arm_name': 'arm1',
                           'x_pos': '0.18',
                           'y_pos': '3.0',
                           'z_pos': '0.01',
                           'yaw': '0.0',
                           'pedestal_height': '0.16',
                           'use_sim_time': use_sim_time,
                           'launch_stack': launch_stack,
                           'wait_on': 'topic /amr1/cmd_vel'
                          }.items()
                        )
    ld.add_action(arm1_launch_cmd)
    
    # Spawn ARM2 only after the ARM1 is fully spawned in gazebo (e.g /arm1/arm_controller/follow_joint_trajectory available)
    arm2_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot_config_launch_dir, 'arm.launch.py')),
        launch_arguments={ 'arm_name': 'arm2',
                           'x_pos': '-7.0',
                           'y_pos': '-0.0',
                           'z_pos': '0.01',
                           'yaw': '0.0',
                           'use_sim_time': use_sim_time,
                           'launch_stack': launch_stack,
                           'wait_on': 'action /arm1/arm_controller/follow_joint_trajectory'
                          }.items()
                        )

    ld.add_action(arm2_launch_cmd)
 
    # Launch cube, amr, arm1 & arm2 controllers
    cube_controller = Node(
                package='picknplace',
                executable='cube_controller.py',
                output='screen',
                arguments=[ 
                    '--ros-args', '--log-level', LOG_LEVEL,
                ])
  
    arm1_controller = Node(
                package="picknplace",
                executable='arm1_controller.py',
                output="screen",
                arguments=[
                    "--ros-args", "--log-level", LOG_LEVEL,
                ])

    amr_controller = Node(
                package="picknplace",
                executable='amr_controller.py',
                output="screen",
                namespace='/amr1',
                arguments=[
                    "--ros-args", "--log-level", LOG_LEVEL,
                ])
    
    arm2_controller = Node(
                package="picknplace",
                executable='arm2_controller.py',
                output="screen",
                arguments=[
                    "--ros-args", "--log-level", LOG_LEVEL,
                ])
    
    # Start controllers after ARM2 is fully spawned in gazebo (e.g /arm2/arm_controller/follow_joint_trajectory available)    
    wait_for_action_server = ExecuteProcess(
            cmd=[
                'ros2', 'run', 'robot_config', 'wait_for_interface.py', 'action', '/arm2/arm_controller/follow_joint_trajectory'
            ], output='screen',
        )

    remappings = [("/tf", "tf"), ("/tf_static", "tf_static")]

    amr1_rviz_file = os.path.join(get_package_share_directory('picknplace'), 'rviz', 'amr1_view.rviz')
    amr1_rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        namespace='/amr1',
        output='log',
        remappings=remappings,
        arguments=['-d', amr1_rviz_file,
                   '--ros-args', '--log-level', LOG_LEVEL],
    )

    arm1_rviz_file = os.path.join(get_package_share_directory('picknplace'), 'rviz', 'arm1_view.rviz')
    arm1_rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        namespace='/arm1',
        output='log',
        remappings=remappings,
        arguments=['-d', arm1_rviz_file,
                   '--ros-args', '--log-level', LOG_LEVEL],
    )

    launch_controllers = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=wait_for_action_server,
            on_exit=[cube_controller, arm1_controller, amr_controller, arm2_controller, amr1_rviz_node, arm1_rviz_node],
        )
    )
    ld.add_action(wait_for_action_server)
    ld.add_action(launch_controllers)

    return ld
