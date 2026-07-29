#!/usr/bin/env python3

# Copyright (C) 2023 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

import unittest

import launch

import launch_ros.actions

import launch_testing
import launch_testing.actions
import launch_testing.asserts
import launch_testing.tools

import pytest

robot_radius_args = [
    ('N/A'),
    (4),
    (-0.5),
    (12.0),
]


def get_test_node(robot_radius):
    return launch_ros.actions.Node(
        package='wandering_app',
        executable='wandering',
        parameters=[{'robot_radius': robot_radius}],
        additional_env={'PYTHONUNBUFFERED': '1'},
        output='screen',
    )


@pytest.mark.launch_test
@launch_testing.parametrize('robot_radius', robot_radius_args)
def generate_test_description(robot_radius):
    return launch.LaunchDescription(
        [launch_testing.util.KeepAliveProc(), launch_testing.actions.ReadyToTest()]
    )


invalid_param_timeout = 5


class TestWanderingInvalidParam(unittest.TestCase):
    def test_invalid_param(self, launch_service, proc_info, proc_output, robot_radius):
        proc_action = get_test_node(robot_radius)

        with launch_testing.tools.launch_process(
            launch_service, proc_action, proc_info, proc_output
        ):
            proc_info.assertWaitForStartup(process=proc_action, timeout=invalid_param_timeout)

            if type(robot_radius) is float:
                proc_output.assertWaitFor(
                    'Robot radius set to:',
                    process=proc_action,
                    timeout=invalid_param_timeout,
                    stream='stderr'
                )
                proc_output.assertWaitFor(
                    'Robot radius has invalid value!',
                    process=proc_action,
                    timeout=invalid_param_timeout,
                    stream='stderr',
                )
            else:
                proc_output.assertWaitFor(
                    'Failed to run WanderingWrapper.',
                    process=proc_action,
                    timeout=invalid_param_timeout,
                    stream='stderr',
                )
