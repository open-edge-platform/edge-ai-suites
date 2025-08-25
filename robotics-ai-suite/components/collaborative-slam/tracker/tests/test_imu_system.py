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

'''
Author: han.yin@intel.com
'''

import os
import sys
import argparse

from launch import LaunchDescription, LaunchService
from launch.actions import ExecuteProcess, TimerAction, DeclareLaunchArgument, SetLaunchConfiguration, \
                           IncludeLaunchDescription, EmitEvent, RegisterEventHandler
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource

from ament_index_python.packages import get_package_share_directory

def args_parse(default_bagfile_dir):
    parser = argparse.ArgumentParser(description="Automatically test functionality of IMU system")
    parser.add_argument("-b", "--bagfile_dir", type=str, dest="bagfile_dir",
                        help="The directory which stores the .db3 bag file", default=default_bagfile_dir)
    parser.add_argument("-e", "--exefile_dir", type=str, dest="exefile_dir",
                        help="The directory which stores the test_image_transport exe", default="./")
    parser.add_argument("-t", "--bad_imu_threshold", type=int, dest="bad_imu_threshold",
                        help="The threshold of bad imu status published by tracker to pass the test", default=0)
    # parser.add_argument("-p", "--ros1_path", type=str, dest="ros1_path",
    #                     help="The installation path of the ROS1", default="/opt/ros/noetic")
    args = parser.parse_args()

    bagfile_dir = os.path.realpath(args.bagfile_dir)
    if not os.path.isdir(bagfile_dir):
        sys.exit('cannot find bagfile in "{}"'.format(bagfile_dir))

    exefile_dir = os.path.realpath(args.exefile_dir)
    exefile_path = os.path.join(exefile_dir, "test_imu_system")
    if not os.path.isfile(exefile_path):
        sys.exit('can not find test_image_transport exe in "{}"'.format(exefile_dir))

    # ros1_install_path = os.path.realpath(args.ros1_path)
    # if not os.path.isdir(ros1_install_path):
    #     sys.exit('"{}" is not a directory'.format(ros1_install_path))

    args_dict = dict()
    args_dict.update({"BAG": bagfile_dir})
    args_dict.update({"EXE": exefile_dir})
    args_dict.update({"THRESHOLD": args.bad_imu_threshold})
    # args_dict.update({"ROS1PATH": ros1_install_path})

    return args_dict


def generate_launch_description():
    ld = LaunchDescription([
        DeclareLaunchArgument(
            name='ID',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='queue_size',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='publish_tf',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='rviz',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='gui',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='log_level',
            default_value='warning'
        ),
        DeclareLaunchArgument(
            name='get_camera_extrin_from_tf',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='camera_setup',
            default_value='Monocular_Inertial'
        ),
        DeclareLaunchArgument(
            name='clean_keyframe',
            default_value='true'
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_tracker'), 'launch/euroc_mono.launch.py')
            ),
            launch_arguments={
                'ID': LaunchConfiguration('ID'),
                'queue_size': LaunchConfiguration('queue_size'),
                'publish_tf': LaunchConfiguration('publish_tf'),
                'rviz': LaunchConfiguration('rviz'),
                'gui': LaunchConfiguration('gui'),
                'log_level': LaunchConfiguration('log_level'),
                'get_camera_extrin_from_tf': LaunchConfiguration('get_camera_extrin_from_tf'),
                'camera_setup': LaunchConfiguration('camera_setup'),
                'clean_keyframe': LaunchConfiguration('clean_keyframe')
            }.items()
        )
    ])

    return ld


# def generate_ros1_env(ros1_path):
#     subprocess_env = os.environ.copy()
#     subprocess_env.update({"ROS_PACKAGE_PATH": os.path.join(ros1_path, "share")})
#     subprocess_env.update({"ROS_ETC_DIR": os.path.join(ros1_path, "etc/ros")})
#     subprocess_env.update({"ROS_MASTER_URI": "http://localhost:11311"})
#     subprocess_env.update({"ROS_LOCALHOST_ONLY": "0"})
#     subprocess_env.update({"ROS_ROOT": os.path.join(ros1_path, "share/ros")})
#     ld_path = subprocess_env["LD_LIBRARY_PATH"] + ":" + os.path.join(ros1_path, "lib")
#     subprocess_env.update({"LD_LIBRARY_PATH": ld_path})

#     return subprocess_env

# Global variable used in the monitor process callback funtion to store the exit code
monitor_ret = 0

def main():
    ret = 0
    # Use environment variable as default value of .bag file directory
    if "BAGFILE_DIR" in os.environ:
        default_bagfile_dir = os.getenv("BAGFILE_DIR")
    else:
        default_bagfile_dir = os.getenv("HOME")
    args_dict = args_parse(default_bagfile_dir)

    # Generate tracker node launch description
    ld = generate_launch_description()

    # Generate tracker monitor execute process
    program_cmd = ["./test_imu_system"]
    ros_prefix = ["--ros-args", "-p"]
    threshold_param = "bad_imu_threshold:=" + str(args_dict["THRESHOLD"])
    tracker_monitor_cmd = program_cmd + ros_prefix
    tracker_monitor_cmd.append(threshold_param)
    monitor_process = ExecuteProcess(
        cmd = tracker_monitor_cmd,
        cwd = args_dict["EXE"],
        shell = False,
        output = 'screen'
    )

    # Generate server node execute process
    launch_file_cmd = ["ros2", "launch", "univloc_server", "server.launch.py"]
    launch_params = ["fix_scale:=true", "rviz:=false", "correct_loop:=false"]
    server_cmd = launch_file_cmd + launch_params
    server_process = ExecuteProcess(
        cmd = server_cmd,
        output = 'screen',
        additional_env = {'SPDLOG_LEVEL': 'warning'},
        shell = False,
        sigterm_timeout = '20'
    )

    # Generate playback execute process
    # playback_env = generate_ros1_env(args_dict["ROS1PATH"])
    playback_cmd = ["ros2", "bag", "play", args_dict["BAG"]]
    wait_to_shutdown = TimerAction(period=5.0, actions=[EmitEvent(event=Shutdown())])
    playback_process = ExecuteProcess(
        cmd = playback_cmd,
        shell = True,
        # env = playback_env,
        output = 'screen',
        on_exit = wait_to_shutdown
    )
    wait_to_play = TimerAction(period=5.0, actions=[playback_process])

    # Define event handler to process tracker monitor return code
    def on_monitor_process_exit(event, context):
        global monitor_ret
        monitor_ret = event.returncode

    process_exit_handler = OnProcessExit(target_action = monitor_process, on_exit = on_monitor_process_exit)

    # Group tracker node, tracker monitor and playback execute process to launch service
    ld.add_action(server_process)
    ld.add_action(monitor_process)
    ld.add_action(wait_to_play)
    ld.add_action(RegisterEventHandler(process_exit_handler))
    ls_group = LaunchService()
    ls_group.include_launch_description(ld)

    separator = "-" * 100
    print(separator)
    print("Start running IMU functionality test")

    ret = ls_group.run()

    print("LaunchService return code: {}".format(ret))
    print("Monitor process exit code: {}".format(monitor_ret))
    if ret or monitor_ret:
        print("\nTest failed")
    else:
        print("\nTest successful")

    print(separator)

    return (ret if ret else monitor_ret)


if __name__ == "__main__":
    sys.exit(main())
