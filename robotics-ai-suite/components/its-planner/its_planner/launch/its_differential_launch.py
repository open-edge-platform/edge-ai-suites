# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource


def get_ros_distro():
    """Gets the ROS 2 distribution name"""
    return os.environ.get('ROS_DISTRO', 'humble')


def generate_launch_description():
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    its_planner_dir = get_package_share_directory('its_planner')

    # Automatic ROS version detection
    ros_distro = get_ros_distro()

    # File selection based on distribution
    if ros_distro == 'humble':
        params_file = os.path.join(its_planner_dir, 'nav2_params_humble.yaml')
        bt_xml_file = os.path.join(its_planner_dir, 'navigate_w_recovery_humble.xml')
    else:  # jazzy or newer distributions
        params_file = os.path.join(its_planner_dir, 'nav2_params_jazzy.yaml')
        bt_xml_file = os.path.join(its_planner_dir, 'navigate_w_recovery_jazzy.xml')

    print(f"ROS Distro: {ros_distro}")
    print(f"Params file: {params_file}")
    print(f"Params file exists: {os.path.exists(params_file)}")
    print(f"BT XML file: {bt_xml_file}")
    print(f"BT XML file exists: {os.path.exists(bt_xml_file)}")

    set_log_level = SetEnvironmentVariable(
        'RCUTILS_LOGGING_SEVERITY_THRESHOLD', 'INFO'
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'tb3_simulation_launch.py')
        ),
        launch_arguments={
            'headless': 'False',
            'use_sim_time': 'true',
            'params_file': params_file,
            'default_bt_xml_filename': bt_xml_file,
        }.items()
    )

    return LaunchDescription([
        set_log_level,
        nav2_launch
    ])
