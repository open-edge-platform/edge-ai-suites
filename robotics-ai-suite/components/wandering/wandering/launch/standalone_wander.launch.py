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

import launch
import launch.actions
import launch.substitutions
import launch_ros.actions
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # ================== Camera =========================
    tf_node = launch_ros.actions.Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='camera_tf',
            arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'camera_link'],
            parameters=[{'use_sim_time': False}]
    )
    realsense2_dir = get_package_share_directory('realsense2_camera')
    realsense_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                realsense2_dir + '/launch/rs_launch.py'),
        launch_arguments={'align_depth.enable': 'true'}.items()
    )
    # ================== Object detection ==================
    od_launch = launch_ros.actions.Node(
            name='object_detection', package='object_detection',
            executable='object_detection_node', output='screen')
    # ================== RTABMAP ===========================
    rtabmap_dir = get_package_share_directory('rtabmap_ros')
    rtabmap_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                rtabmap_dir + '/launch/realsense_d400.launch.py')
    )

    wandering_node = launch_ros.actions.Node(
            package='wandering_app', executable='wandering', output='screen')
    return launch.LaunchDescription([
        tf_node,
        realsense_launch,
        od_launch,
        rtabmap_launch,
        wandering_node
    ])
