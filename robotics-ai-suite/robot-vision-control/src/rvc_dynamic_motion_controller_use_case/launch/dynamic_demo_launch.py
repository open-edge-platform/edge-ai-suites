# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

from launch import LaunchContext, LaunchDescription
import launch.actions
#import launch.actions.LogInfo
import launch.substitutions
import launch_ros.actions
import os
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch.actions import LogInfo
from launch.actions import IncludeLaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import SetLaunchConfiguration
from launch.actions import (DeclareLaunchArgument, EmitEvent, ExecuteProcess,
                            LogInfo, RegisterEventHandler, TimerAction)
from launch.conditions import IfCondition
from launch.event_handlers import (OnExecutionComplete, OnProcessExit,
                                OnProcessIO, OnProcessStart, OnShutdown)
from launch.events import Shutdown
from launch.substitutions import (EnvironmentVariable, FindExecutable,
                                LaunchConfiguration, LocalSubstitution,
                                PythonExpression)

from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch.actions import GroupAction
from launch_ros.actions import PushRosNamespace, SetRemap

from ament_index_python.packages import get_package_share_directory
from pprint import pprint

from launch_ros.actions import Node


import ast
from launch_ros.substitutions import FindPackageShare
import yaml
from ament_index_python.packages import get_package_share_directory
from launch.conditions import UnlessCondition

import sys
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)
from launch.actions import OpaqueFunction

packageName = "rvc_dynamic_motion_controller_use_case"

def load_yaml(package_path, file_path):
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path) as file:
            return yaml.safe_load(file)
    except OSError:  # parent of IOError, OSError *and* WindowsError where available
        print("FATAL: File not found: " + absolute_file_path )
        return None


def launch_setup(context, *args, **kwargs):
    robot_demo_main_dir = get_package_share_directory(packageName)
    # UR specific arguments
    #ur_type_arg = LaunchConfiguration( "ur_type", default="ur5e")
    #robot_ip_arg = LaunchConfiguration( "robot_ip", default="10.11.12.99")
    launch_rviz_arg = LaunchConfiguration( "launch_rviz", default="false")
    headless_mode_arg = LaunchConfiguration( "headless_mode", default="false")

    motion_controller_arg = LaunchConfiguration("motion_controller", default="servo")

    controllers_file_path = robot_demo_main_dir + '/config/controllers.yaml'
    controllers_file = LaunchConfiguration("controllers_file", default=controllers_file_path)
    whoAmIConf = LaunchConfiguration("namespace",default="ipc")
    whoAmI_arg = context.perform_substitution(whoAmIConf)

    #totalControllersPresent_arg = LaunchConfiguration( "totalControllersPresent", default="2")
    totalControllersPresent_arg = "2"

    fullnamespacecontrollermanager = "/"+ whoAmI_arg + "/controller_manager"


    ################################################

    ur_type = LaunchConfiguration("ur_type", default="ur5e") 
    #robot_ip = LaunchConfiguration("robot_ip", default="10.11.12.99")

    robot_ip = LaunchConfiguration("robot_ip", default="10.11.12.99")
    safety_limits = LaunchConfiguration("safety_limits")
    safety_pos_margin = LaunchConfiguration("safety_pos_margin")
    safety_k_position = LaunchConfiguration("safety_k_position")
    # General arguments
    runtime_config_package = LaunchConfiguration("runtime_config_package")

    description_package = LaunchConfiguration("description_package")
    description_file = LaunchConfiguration("description_file")
    tf_prefix = LaunchConfiguration("tf_prefix")
    use_fake_hardware = LaunchConfiguration("use_fake_hardware")
    fake_sensor_commands = LaunchConfiguration("fake_sensor_commands")

    print (motion_controller_arg)

    motion_controller_string = context.perform_substitution(motion_controller_arg)

    print(motion_controller_string)

    if (motion_controller_string == "servo"):
        robot_controller =  'forward_position_controller'
        motion_controller_config = { 'motion_controller': 'RVCMotionController::Moveit2ServoMotionController'}
    ##### FOR MOVEIT2:
    #robot_controller =  'forward_position_controller'
    #### OUR LINEAR CONTROLLER:
    elif (motion_controller_string == "linear_controller"):
        robot_controller =  'demo_linear_controller'
        motion_controller_config = { 'motion_controller': 'RVCMotionController::LinearGoalController'}
    else:
        robot_controller = ""
        motion_controller_config = { 'motion_controller': 'RVCMotionController::URPendantGoalController'}

        
    launch_rviz = LaunchConfiguration("launch_rviz")
    use_tool_communication = LaunchConfiguration("use_tool_communication")
    tool_parity = LaunchConfiguration("tool_parity")
    tool_baud_rate = LaunchConfiguration("tool_baud_rate")
    tool_stop_bits = LaunchConfiguration("tool_stop_bits")
    tool_rx_idle_chars = LaunchConfiguration("tool_rx_idle_chars")
    tool_tx_idle_chars = LaunchConfiguration("tool_tx_idle_chars")
    tool_device_name = LaunchConfiguration("tool_device_name")
    tool_tcp_port = LaunchConfiguration("tool_tcp_port")
    tool_voltage = LaunchConfiguration("tool_voltage")
    reverse_ip = LaunchConfiguration("reverse_ip")
    script_command_port = LaunchConfiguration("script_command_port")

    joint_limit_params = PathJoinSubstitution(
        [FindPackageShare(description_package), "config", ur_type, "joint_limits.yaml"]
    )
    kinematics_params = PathJoinSubstitution(
        [FindPackageShare( packageName ),"config",  "thisur5e_kinematics.yaml"]
    )
    physical_params = PathJoinSubstitution(
        [FindPackageShare(description_package), "config", ur_type, "physical_parameters.yaml"]
    )
    visual_params = PathJoinSubstitution(
        [FindPackageShare(description_package), "config", ur_type, "visual_parameters.yaml"]
    )
    script_filename = PathJoinSubstitution(
        [FindPackageShare("ur_robot_driver"), "resources", "ros_control.urscript"]
    )
    input_recipe_filename = PathJoinSubstitution(
        [FindPackageShare("ur_robot_driver"), "resources", "rtde_input_recipe.txt"]
    )
    output_recipe_filename = PathJoinSubstitution(
        [FindPackageShare("ur_robot_driver"), "resources", "rtde_output_recipe.txt"]
    )

    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution([robot_demo_main_dir, "urdf", "composite_u5_robotiq_2f_gripper.xacro" ]),
            " ",
            "packageName:=",
            packageName,
            " ",
            "robot_ip:=",
            robot_ip,
            " ",
            "joint_limit_params:=",
            joint_limit_params,
            " ",
            "kinematics_params:=",
            kinematics_params,
            " ",
            "physical_params:=",
            physical_params,
            " ",
            "visual_params:=",
            visual_params,
            " ",
            "safety_limits:=",
            safety_limits,
            " ",
            "safety_pos_margin:=",
            safety_pos_margin,
            " ",
            "safety_k_position:=",
            safety_k_position,
            " ",
            "name:=",
            ur_type,
            " ",
            "script_filename:=",
            script_filename,
            " ",
            "input_recipe_filename:=",
            input_recipe_filename,
            " ",
            "output_recipe_filename:=",
            output_recipe_filename,
            " ",
            "tf_prefix:=",
            tf_prefix,
            " ",
            "use_fake_hardware:=",
            use_fake_hardware,
            " ",
            "fake_sensor_commands:=",
            fake_sensor_commands,
            " ",
            "headless_mode:=",
            headless_mode_arg,
            " ",
            "use_tool_communication:=",
            use_tool_communication,
            " ",
            "tool_parity:=",
            tool_parity,
            " ",
            "tool_baud_rate:=",
            tool_baud_rate,
            " ",
            "tool_stop_bits:=",
            tool_stop_bits,
            " ",
            "tool_rx_idle_chars:=",
            tool_rx_idle_chars,
            " ",
            "tool_tx_idle_chars:=",
            tool_tx_idle_chars,
            " ",
            "tool_device_name:=",
            tool_device_name,
            " ",
            "tool_tcp_port:=",
            tool_tcp_port,
            " ",
            "tool_voltage:=",
            tool_voltage,
            " ",
            "reverse_ip:=",
            reverse_ip,
            " ",
            "script_command_port:=",
            script_command_port,
            " ",
            "whoAmI:=",
            whoAmI_arg,
            " ",
            "totalControllersPresent:=",
            totalControllersPresent_arg,
            " ",

            
        ]
    )
    robot_description = {"robot_description": robot_description_content}

    robot_controllers = PathJoinSubstitution(
        [FindPackageShare(runtime_config_package), "config", controllers_file]
    )

    ##FIXME: thefile doesnt contain the /** namespace token so it doesnt load the param!
    update_rate_config_file = PathJoinSubstitution(
        [
            FindPackageShare("ur_robot_driver"),
            "config",
            "ur5e_update_rate.yaml",
        ]
    )

    control_node = Node(
        #package="controller_manager",
        #executable="ros2_control_node",
        #parameters=[robot_description, robot_controllers],
        package="ur_robot_driver",
        executable="ur_ros2_control_node",
        parameters=[robot_description, update_rate_config_file, robot_controllers],
        namespace=whoAmI_arg,
        output={
            "stdout": "screen",
            "stderr": "screen",
        },
    )
    dashboard_client_node = Node(
        package="ur_robot_driver",
        executable="dashboard_client",
        name="dashboard_client",
        output="screen",
        emulate_tty=True,
        condition=UnlessCondition(use_fake_hardware),
        parameters=[{"robot_ip": robot_ip}],
        namespace=whoAmI_arg,
    )

    io_and_status_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["io_and_status_controller", "-c", fullnamespacecontrollermanager],
        namespace=fullnamespacecontrollermanager,
    )

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        namespace=whoAmI_arg,
        parameters=[robot_description],
    )

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        #namespace=whoAmI_arg,
        arguments=[
            "joint_state_broadcaster", 
            "--controller-manager", fullnamespacecontrollermanager,
        ],
    )

    robot_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[robot_controller, "-c", fullnamespacecontrollermanager],
    )

    io_and_status_controller = Node(
            package="controller_manager",
            executable="spawner",
            #namespace=whoAmI_arg,
            arguments=[
                "io_and_status_controller",
                "--controller-manager", whoAmI_arg + "/controller_manager",
            ]
    )

    joint_group_velocity_controller = Node(
            package="controller_manager",
            executable="spawner",
            #namespace=whoAmI_arg,
            arguments=[
                "forward_velocity_controller",
                "--controller-manager", whoAmI_arg + "/controller_manager",
                "--inactive",

            ]
    )

    joint_group_position_controller = Node(
            package="controller_manager",
            executable="spawner",
            #namespace=whoAmI_arg,
            arguments=[
                "forward_position_controller",
                "--controller-manager", whoAmI_arg + "/controller_manager",
                #"--inactive",

            ]
    )



    ################################################





    marker_server_node = Node(
            name='marker_server_robot_demo',
            package='marker_server_robot_demo',
            executable='marker_server_robot_demo',
            namespace=whoAmI_arg,
            parameters=[ robot_demo_main_dir + "/config/parameters.yaml" ],

    )

    camera_xacro_path = robot_demo_main_dir + '/cameraurdf/d415camera' + whoAmI_arg + '.xacro'
    camera_robot_state_publisher_node = Node(
            name='camera_robot_state_publisher',

            #dynamic publisher (i.e.: move camera with joypad)
            #package='dario_camera_state_publisher',
            #executable='dario_camera_state_publisher',

            #static published
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=whoAmI_arg,
            parameters=[ 
                {
                    'robot_description': 
                        Command(
                            [
                                'xacro',' ', camera_xacro_path, 
                                ' name:=camera', whoAmI_arg,
                            ]
                        ), 
                    'whoAmI': whoAmI_arg, 
                    'name': 'camera'+whoAmI_arg 
                }
            ],
            #parameters=[ {'robot_description': Command(['xacro',' ', camera_xacro_path]), 'whoAmI': whoAmI_arg }],
            remappings=[ ('robot_description' , 'rs_description' )],
            output='own_log'
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        #output="log",
        arguments=["-d", robot_demo_main_dir + "/config/robot_demo_config.rviz" ],
    )

    gripper_forward_command_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "gripper_forward_command_controller",
            "-t",
            "forward_command_controller/ForwardCommandController",
            "-c",
            fullnamespacecontrollermanager,
        ],
    )

    gripper_sensor_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "gripper_sensor_broadcaster",
            "-t",
            "robotiq_controllers/RobotiqSensorBroadcaster",
            "-c",
            fullnamespacecontrollermanager,
        ],
    )

    joint_trajectory_controller_node = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_trajectory_controller",
            "-t",
            "joint_trajectory_controller/JointTrajectoryController",
            "--controller-manager", whoAmI_arg + "/controller_manager",
        ],
    )

    moveit_config_file = "ur5eAndGripper.srdf"
    robot_description_semantic_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [robot_demo_main_dir, "srdf", moveit_config_file]
            ),
        ]
    )

    robot_description_semantic = {
        "robot_description_semantic": robot_description_semantic_content.perform(context)
    }

    kinematics_yaml = load_yaml(robot_demo_main_dir,"config/kinematics.yaml")
    planning_yaml = load_yaml(robot_demo_main_dir,"config/planning.yaml")
    smoother_yaml = load_yaml(robot_demo_main_dir,"config/smoother.yaml")
    robot_description_kinematics = {"robot_description_kinematics": kinematics_yaml}
    robot_description_planning = {"robot_description_planning": planning_yaml}
    smoother = {"online_signal_smoothing": smoother_yaml}


    pose_tracking_yaml = load_yaml(robot_demo_main_dir,"config/pose_tracking_settings.yaml")
    pose_tracking_params = {"moveit_servo": pose_tracking_yaml}
    servo_yaml = load_yaml(robot_demo_main_dir, "config/ur5_config_pose_tracking.yaml")
    servo_params = {"moveit_servo": servo_yaml}
    low_pass_filter_coeff = {"butterworth_filter_coeff": 40.0}
        
    ## ros2 run robot_demo_main robot_demo_main --ros-args --params-file install/robot_demo_main/share/robot_demo_main/config/waypoints.yaml
    robot_demo_main_node = Node(
            package=packageName,
            executable=packageName,
            #output="screen",
            namespace=whoAmI_arg,
            parameters=[
                motion_controller_config,
                robot_description,
                robot_description_semantic,
                robot_description_kinematics,
                robot_description_planning,
                pose_tracking_params,
                servo_params,
                #smoother,
                low_pass_filter_coeff,
                { "publish_robot_description_semantic": True,
                  "publish_robot_description": True,
                },
                robot_demo_main_dir + "/config/waypoints.yaml",
                robot_demo_main_dir + "/config/parameters.yaml",
                {"robot_ip": robot_ip},
            ],
    )
    nodes_to_start = [
            robot_state_publisher_node,
            #marker_server_node,
            camera_robot_state_publisher_node,
            robot_demo_main_node,
            RegisterEventHandler(
                OnProcessExit(
                    target_action=robot_demo_main_node,
                    on_exit=[
                        LogInfo(msg=(EnvironmentVariable(name='USER'),
                                ' closed the robot_demo_main_node window')),
                        EmitEvent(event=Shutdown(
                            reason='Window closed'))
                    ]
                )
            )
        ]
    if ((motion_controller_string == "servo") or (motion_controller_string == "linear_controller")):
       nodes_to_start.append(io_and_status_controller_spawner) 
       nodes_to_start.append(dashboard_client_node) 
       nodes_to_start.append(control_node) 
       nodes_to_start.append(joint_state_broadcaster_spawner) 
       nodes_to_start.append(robot_controller_spawner) 
       nodes_to_start.append(gripper_forward_command_controller_spawner)
       nodes_to_start.append(joint_trajectory_controller_node)
       nodes_to_start.append(gripper_sensor_broadcaster)
    return nodes_to_start

def generate_launch_description():

    robot_demo_main_dir = get_package_share_directory(packageName)

    declared_arguments = []
    # UR specific arguments
    declared_arguments.append(
        DeclareLaunchArgument("motion_controller", default_value="servo", description="controller/motion controller types. values linear_controller, servo.")
    )

    declared_arguments.append(
        DeclareLaunchArgument("ur_type", default_value="ur5e", description="Type/series of used UR robot.")
    )
    robot_ip_yaml = load_yaml(robot_demo_main_dir, "config/robot_ip.yaml")
    declared_arguments.append(
        DeclareLaunchArgument( 
            "robot_ip", 
            description="IP address by which the robot can be reached.",
            default_value=robot_ip_yaml
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "safety_limits",
            default_value="true",
            description="Enables the safety limits controller if true.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "safety_pos_margin",
            default_value="0.15",
            description="The margin to lower and upper limits in the safety controller.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "safety_k_position",
            default_value="20",
            description="k-position factor in the safety controller.",
        )
    )
    # General arguments
    declared_arguments.append(
        DeclareLaunchArgument(
            "runtime_config_package",
            default_value="ur_bringup",
            description='Package with the controller\'s configuration in "config" folder. \
        Usually the argument is not set, it enables use of a custom setup.',
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "description_package",
            default_value="ur_description",
            description="Description package with robot URDF/XACRO files. Usually the argument \
        is not set, it enables use of a custom description.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tf_prefix",
            default_value='""',
            description="Prefix of the joint names, useful for \
        multi-robot setup. If changed than also joint names in the controllers' configuration \
        have to be updated.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "use_fake_hardware",
            default_value="false",
            description="Start robot with fake hardware mirroring command to its states.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "fake_sensor_commands",
            default_value="false",
            description="Enable fake command interfaces for sensors used for simple simulations. \
            Used only if 'use_fake_hardware' parameter is true.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "whoAmI", 
            default_value="0",
            description="Unique IPC ID, starts from 0, increasing "
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "totalControllersPresent", 
            default_value="2",
            description="total amount of IPC controlling the robot at the same time"
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument(
            "description_file",
            default_value="ur.urdf.xacro",
            description="URDF/XACRO description file with the robot.",
        )
    )    

    declared_arguments.append(
        DeclareLaunchArgument(
            "use_tool_communication",
            default_value="false",
            description="Only available for e series!",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_parity",
            default_value="0",
            description="Parity configuration for serial communication. Only effective, if \
            use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_baud_rate",
            default_value="115200",
            description="Baud rate configuration for serial communication. Only effective, if \
            use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_stop_bits",
            default_value="1",
            description="Stop bits configuration for serial communication. Only effective, if \
            use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_rx_idle_chars",
            default_value="1.5",
            description="RX idle chars configuration for serial communication. Only effective, \
            if use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_tx_idle_chars",
            default_value="3.5",
            description="TX idle chars configuration for serial communication. Only effective, \
            if use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_device_name",
            default_value="/tmp/ttyUR",
            description="File descriptor that will be generated for the tool communication device. \
            The user has be be allowed to write to this location. \
            Only effective, if use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_tcp_port",
            default_value="54321",
            description="Remote port that will be used for bridging the tool's serial device. \
            Only effective, if use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_voltage",
            default_value="0",  # 0 being a conservative value that won't destroy anything
            description="Tool voltage that will be setup.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "reverse_ip",
            default_value="0.0.0.0",
            description="IP that will be used for the robot controller to communicate back to the driver.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "script_command_port",
            default_value="50004",
            description="Port that will be opened to forward script commands from the driver to the robot",
        )
    )
    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)] )
