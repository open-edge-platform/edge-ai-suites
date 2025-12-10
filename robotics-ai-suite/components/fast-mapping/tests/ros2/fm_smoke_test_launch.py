#!/usr/bin/env python3

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0
"""Runs ROS2 bag file play and fast_mapping test to ensure that output is published correctly."""

import os
import sys

import launch_ros.actions
from launch_testing.legacy import LaunchTestService
from launch.actions import ExecuteProcess

from launch import LaunchDescription
from launch import LaunchService


def main(argv=sys.argv[1:]):
    """Main function to run the test."""
    base_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, 'ros2')
    )
    test_exec = os.getenv('TEST_EXECUTABLE')

    # ros2 bag file play
    bag_file_path = os.path.join(base_path, 'ros2bag')

    print('\nPlaying ROS2 bag file : ' + bag_file_path + '\n')
    ros2bag_play = ExecuteProcess(cmd=['ros2', 'bag', 'play', 'ros2bag'], cwd=base_path)

    # FastMapping Node
    fm_node_exec = launch_ros.actions.Node(
        package='fast_mapping',
        executable='fast_mapping_node',
        name='fast_mapping_node',
        output='screen',
    )

    # Start the test executable
    test_action = ExecuteProcess(cmd=[test_exec], name='smoke_tester', output='screen')

    ld = LaunchDescription()
    ld.add_action(ros2bag_play)
    ld.add_action(fm_node_exec)

    lts = LaunchTestService()
    lts.add_test_action(ld, test_action)

    ls = LaunchService(argv=argv)
    ls.include_launch_description(ld)
    return lts.run(ls)


# pylint: disable=duplicate-code
if __name__ == '__main__':
    sys.exit(main())
