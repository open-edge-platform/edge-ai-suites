#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Test module for tracker image transport functionality.

This module provides automated testing for the collaborative SLAM tracker's
image transport feature. It launches a tracker node with configurable parameters,
plays back recorded ROS2 bag files, and monitors the system to validate that
the tracker correctly processes and publishes pose information.

The test uses a monitor process to count published poses and validates against
a configurable threshold to ensure the tracker is functioning properly with
different image transport modes (raw vs compressed).
"""

import os
import sys
import argparse

from launch import LaunchDescription, LaunchService
from launch.actions import (
    ExecuteProcess,
    TimerAction,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    EmitEvent,
    RegisterEventHandler,
)
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource

from ament_index_python.packages import get_package_share_directory


def args_parse(default_bagfile_dir):
    """
    Parse command line arguments for the image transport test.

    Args:
        default_bagfile_dir (str): Default directory for bag files

    Returns:
        dict: Dictionary containing parsed arguments (BAG, EXE, RAW, THRESHOLD)
    """
    parser = argparse.ArgumentParser(
        description='Automatically test tracker image transport feature'
    )
    parser.add_argument(
        '-b',
        '--bagfile_dir',
        type=str,
        dest='bagfile_dir',
        help='The directory which stores the .db3 bag file',
        default=default_bagfile_dir,
    )
    parser.add_argument(
        '-e',
        '--exefile_dir',
        type=str,
        dest='exefile_dir',
        help='The directory which stores the test_image_transport exe',
        default='./',
    )
    parser.add_argument(
        '-r',
        '--raw_transport',
        type=str,
        dest='raw_transport',
        help='Whether to use raw image transport',
        default='true',
        choices=['true', 'false'],
    )
    parser.add_argument(
        '-t',
        '--pose_threshold',
        type=int,
        dest='pose_threshold',
        help='The threshold of published pose by tracker to pass the test',
        default=0,
    )
    # parser.add_argument("-p", "--ros1_path", type=str, dest="ros1_path",
    #                     help="The installation path of the ROS1", default="/opt/ros/noetic")
    args = parser.parse_args()

    bagfile_dir = os.path.realpath(args.bagfile_dir)
    if not os.path.isdir(bagfile_dir):
        sys.exit(f'cannot find bagfile in "{bagfile_dir}"')

    exefile_dir = os.path.realpath(args.exefile_dir)
    exefile_path = os.path.join(exefile_dir, 'test_image_transport')
    if not os.path.isfile(exefile_path):
        sys.exit(f'can not find test_image_transport exe in "{exefile_dir}"')

    # ros1_install_path = os.path.realpath(args.ros1_path)
    # if not os.path.isdir(ros1_install_path):
    #     sys.exit('"{}" is not a directory'.format(ros1_install_path))

    args_dict = {
        'BAG': bagfile_dir,
        'EXE': exefile_dir,
        'RAW': args.raw_transport,
        'THRESHOLD': args.pose_threshold,
    }
    # args_dict.update({"ROS1PATH": ros1_install_path})

    return args_dict


def generate_launch_description(enable_raw_transport):
    """
    Generate launch description for the tracker with image transport configuration.

    Args:
        enable_raw_transport (str): Whether to enable raw image transport ('true' or 'false')

    Returns:
        LaunchDescription: Configured launch description for the tracker
    """
    # pylint: disable=duplicate-code
    ld = LaunchDescription(
        [
            DeclareLaunchArgument(name='ID', default_value='0'),
            DeclareLaunchArgument(name='queue_size', default_value='0'),
            DeclareLaunchArgument(name='publish_tf', default_value='false'),
            DeclareLaunchArgument(name='rviz', default_value='false'),
            DeclareLaunchArgument(name='gui', default_value='false'),
            DeclareLaunchArgument(name='log_level', default_value='warning'),
            DeclareLaunchArgument(name='get_camera_extrin_from_tf', default_value='true'),
            DeclareLaunchArgument(name='raw_transport', default_value=enable_raw_transport),
            DeclareLaunchArgument(
                name='camera_info_topic', default_value='data_throttled_camera_info'
            ),
            DeclareLaunchArgument(name='image_topic', default_value='data_throttled_image'),
            DeclareLaunchArgument(name='depth_topic', default_value='data_throttled_image_depth'),
            DeclareLaunchArgument(name='image_frame', default_value='openni_rgb_optical_frame'),
            DeclareLaunchArgument(name='camera_fps', default_value='8.0'),
            DeclareLaunchArgument(name='num_lost_frames_to_reset', default_value='5'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory('univloc_tracker'), 'launch/tracker.launch.py'
                    )
                ),
                launch_arguments={
                    'ID': LaunchConfiguration('ID'),
                    'queue_size': LaunchConfiguration('queue_size'),
                    'publish_tf': LaunchConfiguration('publish_tf'),
                    'rviz': LaunchConfiguration('rviz'),
                    'gui': LaunchConfiguration('gui'),
                    'log_level': LaunchConfiguration('log_level'),
                    'get_camera_extrin_from_tf': LaunchConfiguration('get_camera_extrin_from_tf'),
                    'raw_transport': LaunchConfiguration('raw_transport'),
                    'camera_info_topic': LaunchConfiguration('camera_info_topic'),
                    'image_topic': LaunchConfiguration('image_topic'),
                    'depth_topic': LaunchConfiguration('depth_topic'),
                    'image_frame': LaunchConfiguration('image_frame'),
                    'camera_fps': LaunchConfiguration('camera_fps'),
                    'num_lost_frames_to_reset': LaunchConfiguration('num_lost_frames_to_reset'),
                }.items(),
            ),
        ]
    )

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

# Global variable used in the monitor process callback function to store the exit code
MONITOR_RET = 0


def main():
    """
    Main function to run the tracker image transport test.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # pylint: disable=too-many-locals
    ret = 0
    # Use environment variable as default value of .bag file directory
    if 'BAGFILE_DIR' in os.environ:
        default_bagfile_dir = os.getenv('BAGFILE_DIR')
    else:
        default_bagfile_dir = os.getenv('HOME')
    args_dict = args_parse(default_bagfile_dir)

    # Generate tracker node launch description
    ld = generate_launch_description(args_dict['RAW'])

    # Generate tracker monitor execute process
    program_cmd = ['./test_image_transport']
    ros_prefix = ['--ros-args', '-p']
    threshold_param = 'pose_threshold:=' + str(args_dict['THRESHOLD'])
    tracker_monitor_cmd = program_cmd + ros_prefix
    tracker_monitor_cmd.append(threshold_param)
    monitor_process = ExecuteProcess(
        cmd=tracker_monitor_cmd, cwd=args_dict['EXE'], shell=False, output='screen'
    )

    # Generate playback execute process
    # playback_env = generate_ros1_env(args_dict["ROS1PATH"])
    # pylint: disable=duplicate-code
    playback_cmd = ['ros2', 'bag', 'play', args_dict['BAG']]
    wait_to_shutdown = TimerAction(period=5.0, actions=[EmitEvent(event=Shutdown())])
    playback_process = ExecuteProcess(
        cmd=playback_cmd,
        shell=True,
        # env = playback_env,
        output='screen',
        on_exit=wait_to_shutdown,
    )
    wait_to_play = TimerAction(period=5.0, actions=[playback_process])

    # Define event handler to process tracker monitor return code
    def on_monitor_process_exit(event, _context):
        """Callback to capture monitor process exit code."""
        global MONITOR_RET  # pylint: disable=global-statement
        MONITOR_RET = event.returncode

    process_exit_handler = OnProcessExit(
        target_action=monitor_process, on_exit=on_monitor_process_exit
    )

    # Group tracker node, tracker monitor and playback execute process to launch service
    ld.add_action(monitor_process)
    ld.add_action(wait_to_play)
    ld.add_action(RegisterEventHandler(process_exit_handler))
    ls_group = LaunchService()
    ls_group.include_launch_description(ld)

    separator = '-' * 100
    print(separator)
    print('Start running tracker image transport test')

    ret = ls_group.run()

    print(f'LaunchService return code: {ret}')
    print(f'Monitor process exit code: {MONITOR_RET}')
    if ret or MONITOR_RET:
        print('\nTest failed')
    else:
        print('\nTest successful')

    print(separator)

    return ret if ret else MONITOR_RET


if __name__ == '__main__':
    sys.exit(main())
