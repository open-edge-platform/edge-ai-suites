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
Author: yujie.wang@intel.com
'''

import os
import sys
import argparse

from launch import LaunchDescription, LaunchService
from launch.actions import ExecuteProcess, EmitEvent
from launch.events import Shutdown
from launch_testing.legacy import LaunchTestService
from ament_index_python.packages import get_package_prefix
from launch.actions.timer_action import TimerAction


def args_parse(default_bagfile_dir):
    parser = argparse.ArgumentParser(description="Automatically test map merge feature")
    parser.add_argument("-b", "--bagfile_dir", type=str, dest="bagfile_dir",
                        help="The directory which stores two bags used for map merge", default=default_bagfile_dir)
    parser.add_argument("-e", "--exefile_dir", type=str, dest="exefile_dir",
                        help="The directory which stores the test_map_merge_exe", default="./")
    args = parser.parse_args()

    bagfile_dir = os.path.realpath(args.bagfile_dir)

    # bag1_path = os.path.join(bagfile_dir, "map_merge", "run1")
    # if not os.path.isfile(os.path.join(bag1_path, "rosbag2_2022_05_06-13_14_51_0.db3")):
    #     sys.exit('can not find rosbag2_2022_05_06-13_14_51_0.db3 bag file in "{}"'.format(bag1_path))
    # bag2_path = os.path.join(bagfile_dir, "map_merge", "run2")
    # if not os.path.isfile(os.path.join(bag2_path, "rosbag2_2022_05_06-13_24_13_0.db3")):
    #     sys.exit('can not find rosbag2_2022_05_06-13_24_13_0.db3 bag file in "{}"'.format(bag2_path))

    bag1_path = os.path.join(bagfile_dir, "robot1")
    if not os.path.isfile(os.path.join(bag1_path, "rosbag2_2022_02_22-16_59_26_0.db3")):
        sys.exit('can not find rosbag2_2022_02_22-16_59_26_0.db3 bag file in "{}"'.format(bag1_path))
    bag2_path = os.path.join(bagfile_dir, "robot2")
    if not os.path.isfile(os.path.join(bag2_path, "rosbag2_2022_02_22-16_56_35_0.db3")):
        sys.exit('can not find rosbag2_2022_02_22-16_56_35_0.db3 bag file in "{}"'.format(bag2_path))

    exefile_dir = os.path.realpath(args.exefile_dir)
    exefile_path = os.path.join(exefile_dir, "test_map_merge_exe")
    if not os.path.isfile(exefile_path):
        sys.exit('can not find test_map_merge_exe in "{}"'.format(exefile_dir))

    args_dict = dict()
    args_dict.update({"BAG1": bag1_path})
    args_dict.update({"BAG2": bag2_path})
    args_dict.update({"EXE": exefile_path})

    return args_dict


def main():
    # Use environment variable as default value of .bag file directory
    if "BAGFILE_DIR" in os.environ:
        default_bagfile_dir = os.getenv("BAGFILE_DIR")
    else:
        default_bagfile_dir = os.getenv("HOME")
    args_dict = args_parse(default_bagfile_dir)


    # Never use shell if uses shutdown to kill the process
    tracker1 = ExecuteProcess(
        cmd=["ros2", "launch", "univloc_tracker", "tracker.launch.py", "publish_tf:=false", "queue_size:=0", "ID:=0", "gui:=false", "rviz:=false", "use_odom:=false"],
        name='tracker1',
        output='screen',
        shell=False
    )

    tracker2 = ExecuteProcess(
        cmd=["ros2", "launch", "univloc_tracker", "tracker.launch.py", "camera:=camera1", "publish_tf:=false", "queue_size:=0", "ID:=1", "gui:=false", "rviz:=false", "use_odom:=false"],
        name='tracker2',
        output='screen',
        shell=False
    )

    # Not using ros2 launch since it will always return 0 even the process crashs
    server_path = os.path.join(get_package_prefix('univloc_server'), 'lib/univloc_server/univloc_server')
    server = ExecuteProcess(
        cmd=[server_path, "--ros-args", "-r", "__node:=univloc_server", "-p", "grid_size:=0.2"],
        name='server',
        output='screen',
        additional_env={'SPDLOG_LEVEL': 'warning'},
        shell=False
    )

    # Never use shell otherwise return code is shell output
    test = ExecuteProcess(
        cmd=[args_dict["EXE"]],
        output='screen',
        shell = False,
        on_exit = EmitEvent(event=Shutdown())
    )

    rosbag1 = ExecuteProcess(
        cmd=["ros2", "bag", "play", args_dict["BAG1"], "--topics", "/camera/aligned_depth_to_color/camera_info", "/camera/aligned_depth_to_color/image_raw", "/camera/color/camera_info", "/camera/color/image_raw", "/tf_static"],
        output='screen',
        shell=False
    )
    wait_to_play_bag1 = TimerAction(period=4.0, actions=[rosbag1])

    rosbag2 = ExecuteProcess(
        cmd=["ros2", "bag", "play", args_dict["BAG2"], "--remap", "/camera/aligned_depth_to_color/camera_info:=/camera1/aligned_depth_to_color/camera_info", "/camera/aligned_depth_to_color/image_raw:=/camera1/aligned_depth_to_color/image_raw", "/camera/color/camera_info:=/camera1/color/camera_info", "/camera/color/image_raw:=/camera1/color/image_raw"],
        output='screen',
        shell=False
    )
    wait_to_play_bag2 = TimerAction(period=6.0, actions=[rosbag2])

    ld = LaunchDescription([])

    lts = LaunchTestService()
    lts.add_test_action(ld, server)
    lts.add_test_action(ld, tracker1)
    lts.add_test_action(ld, tracker2)
    lts.add_test_action(ld, wait_to_play_bag1)
    lts.add_test_action(ld, wait_to_play_bag2)
    lts.add_test_action(ld, test)

    ls = LaunchService()
    ls.include_launch_description(ld)

    separator = "-" * 100
    print(separator)
    print("Start running map merge test")

    # If any of the test fails, the return will be non-zero
    ret = lts.run(ls)
    print('LaunchTestService return code is ', ret)

    if ret:
        print('\nTest failed!')
    else:
        print('\nTest successful!')

    print(separator)

    return ret


if __name__ == '__main__':
    sys.exit(main())
