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

import launch
import launch_ros.actions

import yaml

dir_path = os.path.dirname(os.path.realpath(__file__))


def generate_launch_description():

    params_file = os.path.join(dir_path, '..', 'param', 'aaeon_node_params.yaml')
    with open(params_file, 'r') as f:
        params = yaml.safe_load(f)['aaeon_ros_node']['ros__parameters']
    aaeon_ros_node = launch_ros.actions.Node(
                                             package='ros2_amr_interface',
                                             executable='amr_interface_node',
                                             name='amr',
                                             output='both',
                                             parameters=[params],
                                             remappings=[
                                                 ('/amr/cmd_vel', '/cmd_vel')
                                             ]
    )

    return launch.LaunchDescription([aaeon_ros_node])
