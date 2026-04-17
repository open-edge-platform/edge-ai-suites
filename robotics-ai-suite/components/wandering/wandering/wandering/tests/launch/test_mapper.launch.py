#!/usr/bin/env python3

# Copyright (C) 2021 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import os
import sys

from launch import LaunchDescription
from launch import LaunchService
from launch.actions import ExecuteProcess

from launch_testing.legacy import LaunchTestService

dir_path = os.path.dirname(os.path.realpath(__file__))


def main(argv=sys.argv[1:]):
    testExecutable = os.getenv('TEST_EXECUTABLE')

    ld = LaunchDescription([])
    bag_folger = os.path.join(dir_path, '..', 'inputs', 'map_recordings')
    bag_process = ExecuteProcess(cmd=['ros2', 'bag', 'play', bag_folger], output='screen')

    test1_action = ExecuteProcess(
        cmd=[testExecutable], name='test_wandering_mapper', output='screen'
    )

    lts = LaunchTestService()
    lts.add_test_action(ld, bag_process)
    lts.add_test_action(ld, test1_action)
    ls = LaunchService(argv=argv)
    ls.include_launch_description(ld)
    return lts.run(ls)


if __name__ == '__main__':
    sys.exit(main())
