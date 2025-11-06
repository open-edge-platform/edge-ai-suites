#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import os
import sys


from launch import LaunchDescription
from launch import LaunchService
from launch.actions import ExecuteProcess
import launch_ros.actions
from launch_testing.legacy import LaunchTestService


def main(argv=sys.argv[1:]):
    base_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, 'ros2')
    )
    test_exec = os.getenv('TEST_EXECUTABLE')

    # ros2 bag file play
    bag_file_path = os.path.join(base_path, 'ros2bag')

    print('\nPlaying ROS2 bag file : ' + bag_file_path + '\n')
    ros2bag_play = ExecuteProcess(cmd=['ros2', 'bag', 'play', 'ros2bag'], cwd=base_path)

    # Test Executable
    fm_test_exec = launch_ros.actions.Node(
        package='fast_mapping',
        executable=[test_exec],
        name='fast_mapping_test',
        output='screen',
        parameters=[{'depth_topic_1': '1-8312-0931209'}],
    )

    ld = LaunchDescription()
    ld.add_action(ros2bag_play)

    lts = LaunchTestService()
    lts.add_test_action(ld, fm_test_exec)

    ls = LaunchService(argv=argv)
    ls.include_launch_description(ld)
    return lts.run(ls)


if __name__ == '__main__':
    sys.exit(main())
