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
Author: weigunag.han@intel.com
'''

import os
import sys
import argparse

from launch import LaunchDescription, LaunchService
from launch.actions import ExecuteProcess, TimerAction, EmitEvent, RegisterEventHandler
from launch.events import Shutdown
from launch.event_handlers import OnProcessExit
from ament_index_python.packages import get_package_prefix
from launch_testing.legacy import LaunchTestService


def args_parse(default_bagfile_dir):
    parser = argparse.ArgumentParser(
        description="Automatically test remapping feature")
    parser.add_argument("-b", "--bagfile_dir", type=str, dest="bagfile_dir",
                        help="The directory which stores the .db3 file", default=default_bagfile_dir)
    parser.add_argument("-p", "--pose_threshold", type=int, dest="pose_threshold",
                        help="The threshold of published pose by tracker to pass the test", default=0)
    parser.add_argument("-k", "--keyframes_threshold", type=int, dest="keyframes_threshold",
                        help="The threshold of keyframes constructed within remapping region ", default=0)
    parser.add_argument("-o", "--octree_threshold", type=int, dest="octree_threshold",
                        help="The threshold of voxels constructed within remapping region", default=0)
    parser.add_argument("-e", "--exefile_dir", type=str, dest="exefile_dir",
                        help="The directory which stores the test_remapping_exe", default="./")
    parser.add_argument("-r", "--remapping_region", type=str, dest="remapping_region",
                        help="The four vertexes of remapping region, [P1.x, P1.y, ... , P4.x, P4.y], must be in clockwise or anti-clockwise order", default="[0.0]")

    args = parser.parse_args()

    bagfile_dir = os.path.realpath(args.bagfile_dir)
    if not os.path.isdir(bagfile_dir):
        sys.exit('cannot find bagfile in "{}"'.format(bagfile_dir))

    loaded_map_path = os.path.join(bagfile_dir, "../cslam-unit-test/remapping/")
    if not os.path.isfile(os.path.join(loaded_map_path, "octree.bin")):
        sys.exit('can not find octree.bin file in "{}"'.format(
            loaded_map_path))
    if not os.path.isfile(os.path.join(loaded_map_path, "map.msg")):
        sys.exit('can not find map.msg file in "{}"'.format(
            loaded_map_path))

    exefile_dir = os.path.realpath(args.exefile_dir)
    exefile_path = os.path.join(exefile_dir, "test_remapping_exe")
    if not os.path.isfile(exefile_path):
        sys.exit('can not find test_remapping_exe in "{}"'.format(exefile_dir))

    args_dict = dict()
    args_dict.update({"BAG": bagfile_dir})
    args_dict.update({"LOADEDMAP": loaded_map_path})
    args_dict.update({"EXE": exefile_dir})
    args_dict.update({"POSE_THRESHOLD": args.pose_threshold})
    args_dict.update({"KEYFRAMES_THRESHOLD": args.keyframes_threshold})
    args_dict.update({"VOXELS_THRESHOLD": args.octree_threshold})
    args_dict.update({"REMAPPING_REGION": args.remapping_region})

    return args_dict


def main():
    # Use environment variable as default value of .bag file directory
    if "BAGFILE_DIR" in os.environ:
        default_bagfile_dir = os.getenv("BAGFILE_DIR")
    else:
        default_bagfile_dir = os.getenv("HOME")
    args_dict = args_parse(default_bagfile_dir)

    octree_load_path = "octree_load_path:=" + \
        args_dict["LOADEDMAP"] + "octree.bin"
    load_map_path = "load_map_path:=" + \
        args_dict["LOADEDMAP"] + "map.msg"

    remapping_region_temp = args_dict["REMAPPING_REGION"][1:-1].split(",")
    if (len(remapping_region_temp) != 8):
        print("The remapping region consists of four vertexes, so the size of this parameter should be 8. The current size is %d, please check the input!" % (
            len(remapping_region_temp)))
        sys.exit(1)

    remapping_region = "server_remapping_region:=" + args_dict["REMAPPING_REGION"]

    # Never use shell if uses shutdown to kill the process
    tracker = ExecuteProcess(
        cmd=["ros2", "launch", "univloc_tracker", "tracker.launch.py", "queue_size:=0", "gui:=false", "publish_tf:=false", "slam_mode:=remapping", "log_level:=warning", "camera:=camera1", "baselink_frame:=base_link1",
             "image_frame:=camera1_color_optical_frame", "use_odom:=true", "odom_frame:=odom1", "odom_tf_query_timeout:=50.0", "enable_fast_mapping:=true", octree_load_path, "ID:=0", "rviz:=false", "camera_fps:=15.0"],
        name='tracker',
        output='screen',
        shell=False
    )

    # Not using ros2 launch since it will always return 0 even the process crashs
    server_path = os.path.join(get_package_prefix(
        'univloc_server'), 'lib/univloc_server/univloc_server')
    server = ExecuteProcess(
        cmd=[server_path, "--ros-args", "-r", "__node:=univloc_server", "-p", "server_mode:=remapping", "-p", load_map_path, "-p",
             "log_level:=info", "-p", remapping_region, "-p", "rviz:=false", "-p", "correct_loop:=false"],
        name='server',
        output='screen',
        additional_env={'SPDLOG_LEVEL': 'warning'},
        shell=False
    )

    # Generate tracker monitor execute process
    tracker_monitor_cmd = ["./test_remapping_exe"] + ["--ros-args"] + \
        ["-p"] + ["pose_threshold:=" + str(args_dict["POSE_THRESHOLD"])] + \
        ["-p"] + ["keyframes_threshold:=" + str(args_dict["KEYFRAMES_THRESHOLD"])] + \
        ["-p"] + ["voxels_threshold:=" + str(args_dict["VOXELS_THRESHOLD"])] + \
        ["-p"] + ["remapping_region:=" + str(args_dict["REMAPPING_REGION"])]

    test = ExecuteProcess(
        cmd=tracker_monitor_cmd,
        cwd=args_dict["EXE"],
        output='screen',
        shell=False
    )

    wait_to_shutdown = TimerAction(
        period=5.0, actions=[EmitEvent(event=Shutdown())])
    rosbag = ExecuteProcess(
        cmd=["ros2", "bag", "play", args_dict["BAG"]],
        output='screen',
        shell=True,
        on_exit=wait_to_shutdown
    )

    wait_to_play_bag = TimerAction(period=4.0, actions=[rosbag])

    def on_monitor_process_exit(event, context):
        global monitor_ret
        monitor_ret = event.returncode

    process_exit_handler = OnProcessExit(
        target_action=test, on_exit=on_monitor_process_exit)

    # Group tracker node, server node, tracker monitor and playback execute process to launch service
    ld = LaunchDescription([])
    lts = LaunchTestService()
    lts.add_test_action(ld, test)
    lts.add_test_action(ld, server)
    lts.add_test_action(ld, tracker)
    lts.add_test_action(ld, wait_to_play_bag)

    ld.add_action(RegisterEventHandler(process_exit_handler))

    ls = LaunchService()
    ls.include_launch_description(ld)

    separator = "-" * 100
    print(separator)
    print("Start running reampping test")

    # If any of the test fails, the return will be non-zero
    ret = lts.run(ls)

    print("LaunchService return code: {}".format(ret))
    print("Monitor process exit code: {}".format(monitor_ret))

    if ret or monitor_ret:
        print('\nTest failed!')
    else:
        print('\nTest successful!')

    print(separator)

    return ret


if __name__ == "__main__":
    sys.exit(main())
