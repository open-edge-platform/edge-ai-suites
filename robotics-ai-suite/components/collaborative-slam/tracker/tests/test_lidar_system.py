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
from launch_testing.legacy import LaunchTestService

from ament_index_python.packages import get_package_share_directory
from ament_index_python.packages import get_package_prefix

def args_parse(default_bagfile_dir):
    parser = argparse.ArgumentParser(description="Automatically test tracker lidar feature")
    parser.add_argument("-b", "--bagfile_dir", type=str, dest="bagfile_dir",
                        help="The directory which stores the .db3 bag file", default=default_bagfile_dir)
    parser.add_argument("-e", "--exefile_dir", type=str, dest="exefile_dir",
                        help="The directory which stores the test_lidar_system exe", default="./")
    parser.add_argument("-tp", "--lidar_pose_failure_threshold", type=int, dest="lidar_pose_failure_threshold",
                        help="The failure pose threshold of lidar based tracking", default=15)
    parser.add_argument("-tf", "--lidar_feature_failure_threshold", type=int, dest="lidar_feature_failure_threshold",
                        help="The failure lidar feature threshold", default=150)
    args = parser.parse_args()

    bagfile_dir = os.path.realpath(args.bagfile_dir)
    if not os.path.isdir(bagfile_dir):
        sys.exit('cannot find bagfile in "{}"'.format(bagfile_dir))

    exefile_dir = os.path.realpath(args.exefile_dir)
    exefile_path = os.path.join(exefile_dir, "test_lidar_system")
    if not os.path.isfile(exefile_path):
        sys.exit('cannot find test_lidar_system exe in "{}"'.format(exefile_dir))

    args_dict = dict()
    args_dict.update({"BAG": bagfile_dir})
    args_dict.update({"EXE": exefile_dir})
    args_dict.update({"THRESHOLD_POSE": args.lidar_pose_failure_threshold})
    args_dict.update({"THRESHOLD_FEATURE": args.lidar_feature_failure_threshold})

    return args_dict

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

    ld = LaunchDescription([])
    lts = LaunchTestService()

    # Not using ros2 launch since it will always return 0 even the process crashs
    tracker_path = os.path.join(get_package_prefix('univloc_tracker'), 'lib/univloc_tracker/univloc_tracker_ros')
    lidar_extrin = "tf_base_lidar:=" + str([0.0, 0.0, 0.16, 0.0, 0.0, 0.0, 0.0])
    tracker = ExecuteProcess(
        cmd=[tracker_path, "--ros-args", "-r", "__node:=univloc_tracker_0", "-p", "queue_size:=0", "-p",
             "publish_tf:=false", "-p", "rviz:=false", "-p", "gui:=false", "-p", "log_level:=warning",
             "-p", "use_lidar:=true", "-p", lidar_extrin, "-p", "depth_threshold:=40.0"],
        name='tracker',
        output='screen',
        shell=False
    )

    # Generate tracker monitor execute process
    program_cmd = ["./test_lidar_system"]
    ros_prefix = ["--ros-args", "-p"]
    threshold_pose_param = "lidar_pose_failure_threshold:=" + str(args_dict["THRESHOLD_POSE"])
    threshold_feature_param = "lidar_feature_failure_threshold:=" + str(args_dict["THRESHOLD_FEATURE"])
    tracker_monitor_cmd = program_cmd + ros_prefix
    tracker_monitor_cmd.append(threshold_pose_param)
    ros_param = ["-p"]
    tracker_monitor_cmd += ros_param
    tracker_monitor_cmd.append(threshold_feature_param)
    monitor_process = ExecuteProcess(
        cmd = tracker_monitor_cmd,
        cwd = args_dict["EXE"],
        shell = False,
        output = 'screen'
    )

    # Generate playback execute process
    # playback_env = generate_ros1_env(args_dict["ROS1PATH"])
    playback_cmd = ["ros2", "bag", "play", args_dict["BAG"]]
    playback_process = ExecuteProcess(
        cmd = playback_cmd,
        shell = True,
        output = 'screen',
        on_exit = EmitEvent(event=Shutdown())
    )
    wait_to_play = TimerAction(period=5.0, actions=[playback_process])

    # Define event handler to process tracker monitor return code
    def on_monitor_process_exit(event, context):
        global monitor_ret
        monitor_ret = event.returncode

    process_exit_handler = OnProcessExit(target_action = monitor_process, on_exit = on_monitor_process_exit)

    # Group tracker node, tracker monitor and playback execute process to launch service
    lts.add_test_action(ld, tracker)
    lts.add_test_action(ld, monitor_process)
    lts.add_test_action(ld, wait_to_play)
    lts.add_test_action(ld, RegisterEventHandler(process_exit_handler))

    ls_group = LaunchService()
    ls_group.include_launch_description(ld)

    separator = "-" * 100
    print(separator)
    print("Start running tracker lidar test")

    ret = lts.run(ls_group)

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
