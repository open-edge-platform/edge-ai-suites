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
    test_exec_arg = os.getenv('TEST_EXEC_ARG')
    test_exec = os.getenv('TEST_EXECUTABLE')
    ld = LaunchDescription()
    ref_maps_bag_path = ''

    if test_exec_arg is not None:
        ref_maps_bag_path = os.path.join(base_path, 'ros2bag_ref', test_exec_arg)
    if not os.path.isfile(ref_maps_bag_path):
        print('\nTesting against ros2 bag file from path: ' + ref_maps_bag_path + '\n')
    # no else

    # ros2 bag file play
    bag_file_path = os.path.join(base_path, 'ros2bag')
    print('\nExecuting ros2 bag file from path: ' + bag_file_path + '\n')
    ros2bag_play = ExecuteProcess(cmd=['ros2', 'bag', 'play', 'ros2bag'], cwd=base_path)

    # fast_mapping_node
    fm_node_exec = launch_ros.actions.Node(
        package='fast_mapping',
        executable=['fast_mapping_node'],
        name='fast_mapping',
        output='screen',
        parameters=[{'use_sim_time': False}],
    )

    fm_test_exec = launch_ros.actions.Node(
        package='fast_mapping',
        executable=[test_exec],
        name='fast_mapping_test',
        arguments=[ref_maps_bag_path],
        output='screen',
    )

    lts = LaunchTestService()
    ld.add_action(fm_node_exec)
    ld.add_action(ros2bag_play)
    lts.add_test_action(ld, fm_test_exec)
    ls = LaunchService(argv=argv)
    ls.include_launch_description(ld)
    return lts.run(ls)


if __name__ == '__main__':
    sys.exit(main())
