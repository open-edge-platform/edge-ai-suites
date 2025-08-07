# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
import os

import launch
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration 
from ament_index_python.packages import get_package_share_directory
from launch.actions.timer_action import TimerAction

def generate_segway_description():
    ld_list = [
        Node(
            package='segwayrmp',
            executable='SmartCar',
            output='screen'
        )
    ]

    return ld_list
 

def generate_tracker_description():
    tracker_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(
                'univloc_tracker'), 'launch/tracker.launch.py')
        ),
        launch_arguments={
	    'use_odom': LaunchConfiguration('use_odom'),
	    'odom_tf_query_timeout': LaunchConfiguration('odom_tf_query_timeout'),
	    'odom_buffer_query_timeout': LaunchConfiguration('odom_buffer_query_timeout'),
            'baselink_frame': LaunchConfiguration('baselink_frame'),
	    'image_frame': LaunchConfiguration('image_frame'),
            'camera': LaunchConfiguration('camera'),
            'camera_setup': LaunchConfiguration('camera_setup'),
            'get_camera_extrin_from_tf': LaunchConfiguration('get_camera_extrin_from_tf'),
            'camera_extrin_query_timeout': LaunchConfiguration('camera_extrin_query_timeout'),
            'publish_tf': LaunchConfiguration('publish_tf'),
            'pub_tf_child_frame': LaunchConfiguration('pub_tf_child_frame'),
            'pub_tf_parent_frame': LaunchConfiguration('pub_tf_parent_frame'),
            'queue_size': LaunchConfiguration('queue_size'),
            'rviz': LaunchConfiguration('tracker_rviz'),
            'gui': LaunchConfiguration('gui'),
            'log_level': LaunchConfiguration('tracker_log_level'),
            'camera_fps': LaunchConfiguration('camera_fps')
        }.items()
    )

    ld_list = [
        DeclareLaunchArgument(
            name='use_odom',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='odom_tf_query_timeout',
            default_value='25.0'
        ),
        DeclareLaunchArgument(
            name='odom_buffer_query_timeout',
            default_value='25.0'
        ),
        DeclareLaunchArgument(
            name='baselink_frame',
            default_value='base_link'
        ),
        DeclareLaunchArgument(
            name='image_frame',
            default_value='camera_color_optical_frame'
        ),
        DeclareLaunchArgument(
            name='camera',
            default_value='camera'
        ),
        DeclareLaunchArgument(
            name='camera_setup',
            default_value='RGBD'
        ),
        DeclareLaunchArgument(
            name='get_camera_extrin_from_tf',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='camera_extrin_query_timeout',
            default_value='10.0'
        ),
        DeclareLaunchArgument(
            name='publish_tf',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='pub_tf_child_frame',
            default_value='odom'
        ),
        DeclareLaunchArgument(
            name='pub_tf_parent_frame',
            default_value='map'
        ),
        DeclareLaunchArgument(
            name='queue_size',
            default_value='1'
        ),
        DeclareLaunchArgument(
            name='tracker_rviz',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='gui',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='tracker_log_level',
            default_value='warning'
        ),
        # Please change the value of camera_fps that represents the real FPS of input camera images, the default value is 30.0 if you don't specify it
        DeclareLaunchArgument(
            name='camera_fps',
            default_value='30.0'
        ),
        # Delay 5 seconds to launch tracker node after realsense node and server node
        TimerAction(period=5.0, actions=[tracker_launch])
    ]

    return ld_list


def generate_server_description():
    ld_list = [
        DeclareLaunchArgument(
            name='fix_scale',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='server_rviz',
            default_value='false'
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_server'), 'launch/server.launch.py')
            ),
            launch_arguments={
                'fix_scale': LaunchConfiguration('fix_scale'),
                'rviz': LaunchConfiguration('server_rviz')
            }.items()
        )
    ]

    return ld_list


def generate_realsense_description():
    ld_list = [
        DeclareLaunchArgument(
            name='align_depth',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='device_type',
            default_value='d435'
        ),
        DeclareLaunchArgument(
            name='initial_reset',
            default_value='true'
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'realsense2_camera'), 'launch/rs_launch.py')
            ),
            launch_arguments={
                'align_depth': LaunchConfiguration('align_depth'),
                'device_type': LaunchConfiguration('device_type'),
                'initial_reset': LaunchConfiguration('initial_reset'),
                'log_level': 'info'
            }.items()
        )
    ]

    return ld_list


# Fast mapping does not have all needed parameters exposed.
# Following parameters should be changed in the code and re-compiled:
# "depth_noise_factor": "0.08",
# "robot_radius_around_camera": "0.3"
def generate_fast_mapping_description():
    fast_mapping_node = Node(
        package='fast_mapping',
        executable='fast_mapping_node',
        output='screen',
        remappings=[('/world/map', '/map')],
        parameters=[{
            'zmin': LaunchConfiguration('zmin'),
            'zmax': LaunchConfiguration('zmax'),
            'max_depth_range': LaunchConfiguration('max_depth_range')
        }]
    )

    ld_list = [
        DeclareLaunchArgument(
            name='zmin',
            default_value='0.3'
        ),
        DeclareLaunchArgument(
            name='zmax',
            default_value='0.6'
        ),
        DeclareLaunchArgument(
            name='max_depth_range',
            default_value='1.5'
        ),
        # Delay 10 seconds to launch fast_mapping after realsense node
        TimerAction(period=10.0, actions=[fast_mapping_node])
    ]

    return ld_list


def generate_static_tf_description():
    ld_list = [
        DeclareLaunchArgument(
            name='static_tf_x',
            default_value='0.24'
        ),
        DeclareLaunchArgument(
            name='static_tf_y',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='static_tf_z',
            default_value='0.17'
        ),
        DeclareLaunchArgument(
            name='static_tf_yaw',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='static_tf_pitch',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='static_tf_roll',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='static_tf_use_sim_time',
            default_value='False'
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_camera_tf',
            output='screen',
            # x y z yaw pitch roll frame_id child_frame_id
            arguments=[
                LaunchConfiguration('static_tf_x'),
                LaunchConfiguration('static_tf_y'),
                LaunchConfiguration('static_tf_z'),
                LaunchConfiguration('static_tf_yaw'),
                LaunchConfiguration('static_tf_pitch'),
                LaunchConfiguration('static_tf_roll'),
                'base_link',
                'camera_link'
            ],
            parameters=[{
                'use_sim_time': LaunchConfiguration('static_tf_use_sim_time')
            }]
        )
    ]

    return ld_list


def generate_navigation_description():
    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(
                'nav2_bringup'), 'launch/navigation_launch.py')
        ),
        launch_arguments={
            'params_file': LaunchConfiguration('nav_params_file')
        }.items()
    )

    ld_list = [
        DeclareLaunchArgument(
            name='nav_params_file',
            default_value=''
        ),
        # Delay 15 seconds to launch nav2_bringup after fast_mapping node
        TimerAction(period=15.0, actions=[navigation_launch])
    ]

    return ld_list


def generate_launch_description():
    segway = generate_segway_description()
    slam_tracker = generate_tracker_description()
    slam_server = generate_server_description()
    realsense = generate_realsense_description()
    fast_mapping = generate_fast_mapping_description()
    static_tf = generate_static_tf_description()
    navigation = generate_navigation_description()

    launch_description = segway + slam_tracker + slam_server + realsense + fast_mapping + static_tf + navigation

    return launch.LaunchDescription(launch_description)


if __name__ == '__main__':
    generate_launch_description()
