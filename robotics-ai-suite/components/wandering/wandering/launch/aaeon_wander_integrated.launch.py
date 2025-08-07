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
import launch.actions
import launch.substitutions
import launch_ros.actions
from launch.actions.timer_action import TimerAction
from ament_index_python.packages import get_package_share_directory

dir_path = os.path.dirname(os.path.realpath(__file__))
camera_front_tf = ['0.09', '0', '0.16', '0', '0', '0']
CURRENT_CAMERA_TF = camera_front_tf

low_res_config = {
        'depth_module.profile': '848,480,15',
        'rgb_camera.profile': '848,480,15',
        'enable_infra1': 'true',
        'align_depth.enable': 'true',
        'enable_sync': 'true',
        'init_reset': 'true'
        }


def generate_launch_description():

    # ================ AAEON node ====================
    aaeon_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                dir_path + '/aaeon_sl_node_launch.py')
    )

    # ================== Camera =========================
    tf_node = launch_ros.actions.Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='camera_tf',
            arguments=[CURRENT_CAMERA_TF[0], CURRENT_CAMERA_TF[1], CURRENT_CAMERA_TF[2],
                       CURRENT_CAMERA_TF[3], CURRENT_CAMERA_TF[4], CURRENT_CAMERA_TF[5],
                       'base_link', 'camera_link'],
            parameters=[{'use_sim_time': False}]
    )
    param_config = os.path.join(dir_path, '..', 'param', 'depth_scan.yaml')
    depth_scan_node = launch_ros.actions.Node(
            package='depthimage_to_laserscan',
            executable='depthimage_to_laserscan_node',
            name='depthimage_to_laserscan_node',
            remappings=[('depth', '/camera/depth/image_rect_raw'),
                        ('depth_camera_info', '/camera/depth/camera_info')],
            parameters=[param_config])

    realsense2_dir = get_package_share_directory('realsense2_camera')
    realsense_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                realsense2_dir + '/launch/rs_launch.py'),
        launch_arguments=low_res_config.items()
    )

    # ================== Wandering node ===============
    wandering_node = launch_ros.actions.Node(
            package='wandering_app', executable='wandering', output='screen')

    # ====================IntegratedNav ================
    param_file_path = os.path.join(dir_path, "..", "param", "aaeon_nav.param.yaml")
    integrated_launch = launch.actions.IncludeLaunchDescription(
        launch.launch_description_sources.PythonLaunchDescriptionSource(
                dir_path + '/integrated_navigation.launch.py'),
        launch_arguments={'navigation_param_file': param_file_path}.items()
    )

    # ================== Node startup timings ===============
    launch_wander_after_timer = TimerAction(period=15.0, actions=[wandering_node])
    launch_integrated_navigation = TimerAction(period=3.0, actions=[integrated_launch])

    return launch.LaunchDescription([
        aaeon_launch,
        tf_node,
        realsense_launch,
        depth_scan_node,
        launch_integrated_navigation,
        launch_wander_after_timer
    ])
