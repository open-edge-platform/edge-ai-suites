#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Smoke test for collaborative SLAM system.
This module contains integration tests for the collaborative SLAM tracker system,
specifically testing image transport functionality with ROS2 bag playback.
The test launches a tracker node, plays back recorded data from a ROS2 bag file,
and monitors the system behavior to ensure proper functionality.
Environment Variables:
    BAGFILE_DIR (str): Directory containing the ROS2 bag files for testing.
                       Defaults to user's home directory if not set.
    EXEFILE_DIR (str): Directory containing test executables.
                       Defaults to current directory if not set.
Test Flow:
    1. Generates launch description with tracker configuration
    2. Starts test_image_transport process to observe system behavior
    3. Plays back ROS2 bag file with recorded sensor data
    4. Validates that all processes complete successfully
    5. Asserts proper return codes and completion status
The test is designed to run as part of a pytest suite and validates the
collaborative SLAM system's ability to process image data correctly.
"""

import os
import time
import pytest

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


ros_distro = os.environ.get("ROS_DISTRO")
if not ros_distro:
    pytest.fail("ROS_DISTRO environment variable is not set.")

DEFAULT_BAGFILE_DIR = f'/opt/ros/{ros_distro}/share/bagfiles/cslam-unit-test/demo-mapping'
DEFAULT_EXEFILE_DIR = f'/opt/ros/{ros_distro}/share/univloc_tracker/tests/smoke_test'


def generate_launch_description(enable_raw_transport):
    """Generate launch description for collaborative SLAM tracker."""
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


def _create_monitor_process(exefile_dir, pose_threshold, monitor_result):
    """Helper to create monitor process and callback."""
    monitor_cmd = [
        './test_image_transport',
        '--ros-args', '-p', f'pose_threshold:={pose_threshold}'
    ]

    def monitor_callback(event, _):
        monitor_result['returncode'] = event.returncode
        monitor_result['completed'] = True

    monitor_process = ExecuteProcess(
        cmd=monitor_cmd,
        cwd=exefile_dir,
        shell=False,
        output='screen'
    )
    return monitor_process, monitor_callback


def _create_playback_process(bagfile_dir):
    """Helper to create playback process and shutdown timer."""
    # pylint: disable=duplicate-code
    playback_cmd = ['ros2', 'bag', 'play', bagfile_dir]
    wait_to_shutdown = TimerAction(period=5.0, actions=[EmitEvent(event=Shutdown())])
    playback_process = ExecuteProcess(
        cmd=playback_cmd,
        shell=True,
        output='screen',
        on_exit=wait_to_shutdown,
    )
    wait_to_play = TimerAction(period=5.0, actions=[playback_process])
    return playback_process, wait_to_play


@pytest.mark.parametrize("bagfile_dir,exefile_dir,raw_transport,pose_threshold", [
        (os.getenv('BAGFILE_DIR', DEFAULT_BAGFILE_DIR),
         os.getenv('EXEFILE_DIR', DEFAULT_EXEFILE_DIR),
         'false',
         550)
    ])
def test_image_transport(bagfile_dir, exefile_dir, raw_transport, pose_threshold):
    """Test tracker image transport functionality."""

    ld = generate_launch_description(raw_transport)

    monitor_result = {'returncode': None, 'completed': False}
    monitor_process, monitor_callback = _create_monitor_process(
        exefile_dir, pose_threshold, monitor_result)
    _, wait_to_play = _create_playback_process(bagfile_dir)

    process_exit_handler = OnProcessExit(
        target_action=monitor_process, on_exit=monitor_callback
    )

    ld.add_action(monitor_process)
    ld.add_action(wait_to_play)
    ld.add_action(RegisterEventHandler(process_exit_handler))

    ls = LaunchService()
    ls.include_launch_description(ld)
    launch_result = ls.run()

    timeout = 35  # seconds
    start_time = time.time()
    while not monitor_result['completed'] and (time.time() - start_time) < timeout:
        time.sleep(0.1)

    assert monitor_result['completed'], "Monitor process did not complete within timeout"
    assert launch_result == 0, f"Launch service failed with return code: {launch_result}"
    assert monitor_result['returncode'] == 0, (
        f"Monitor process failed with return code: {monitor_result['returncode']}"
    )
