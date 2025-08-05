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
from launch.conditions import IfCondition

# added
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription, SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import PushRosNamespace

image_topic_ = '/intel_realsense_r200_depth/image_raw'
depth_topic_ = '/intel_realsense_r200_depth/depth/image_raw'
camera_info_topic_ = '/intel_realsense_r200_depth/camera_info'

bringup_dir = get_package_share_directory('nav2_bringup_collab')

def generate_turtlebot_sim_description():

    tb3_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'nav2_bringup_collab'), 'launch/tb3_simulation_launch.py')
            ),
        launch_arguments={'rviz_config_file' : LaunchConfiguration('rviz_config_file')}.items()
    )
    
    ld_list = [DeclareLaunchArgument(
            name='rviz_config_file',
            default_value=os.path.join(bringup_dir, 'rviz/nav2_localization_view.rviz')
        ),
        TimerAction(period=5.0, actions=[tb3_launch])]

    return ld_list

def generate_server_description():
    server_launch = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(
                    'univloc_server'), 'launch/server.launch.py')
            ),
            launch_arguments={
                'fix_scale': LaunchConfiguration('fix_scale'),
                'rviz': LaunchConfiguration('server_rviz'),
                'save_map_path': LaunchConfiguration('save_map_path'),
                'save_traj_folder': LaunchConfiguration('save_traj_folder'),
                'load_map_path': LaunchConfiguration('load_map_path'),
                'server_mode': LaunchConfiguration('server_mode'),
                'image_topic': LaunchConfiguration('image_topic'),
                'depth_topic': LaunchConfiguration('depth_topic'),
                'camera_info_topic': LaunchConfiguration('camera_info_topic'),
            }.items()
        )

    ld_list = [
        DeclareLaunchArgument(
            name='fix_scale',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='server_rviz',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='save_map_path',
            default_value='""'
        ),
        DeclareLaunchArgument(
            name='save_traj_folder',
            default_value='""'
        ),
        DeclareLaunchArgument(
            name='load_map_path',
            default_value='"./map/map.msg"'
        ),
        DeclareLaunchArgument(
            name='server_mode',
            default_value='localization'
        ),
        TimerAction(period=2.0, actions=[server_launch])
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
            'map_frame': LaunchConfiguration('map_frame'),
            'pub_tf_child_frame': LaunchConfiguration('pub_tf_child_frame'),
            'queue_size': LaunchConfiguration('queue_size'),
            'rviz': LaunchConfiguration('tracker_rviz'),
            'gui': LaunchConfiguration('gui'),
            'log_level': LaunchConfiguration('tracker_log_level'),
	    'traj_store_path': LaunchConfiguration('traj_store_path'),
	    'octree_store_path': LaunchConfiguration('octree_store_path'),
	    'enable_fast_mapping': LaunchConfiguration('enable_fast_mapping'),
	    'zmin': LaunchConfiguration('zmin'),
	    'zmax': LaunchConfiguration('zmax'),
            'depth_max_range': LaunchConfiguration('depth_max_range'),
            'octree_load_path': LaunchConfiguration('octree_load_path'),
            'odom_frame': LaunchConfiguration('odom_frame'),
            'image_topic': LaunchConfiguration('image_topic'),
            'depth_topic': LaunchConfiguration('depth_topic'),
            'camera_info_topic': LaunchConfiguration('camera_info_topic'),
            'slam_mode': LaunchConfiguration('slam_mode'),
            'depthmap_factor': LaunchConfiguration('depthmap_factor'),
              
        }.items()
    )
    ld_list = [
        DeclareLaunchArgument(
            name='use_odom',
            default_value='true'
        ),
        DeclareLaunchArgument(
            name='odom_tf_query_timeout',
            default_value='50.0'
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
            default_value='camera_rgb_optical_frame'
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
            default_value='true'
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
            name='map_frame',
            default_value='map-0'
        ),
        DeclareLaunchArgument(
            name='pub_tf_child_frame',
            default_value='odom'
        ),
        DeclareLaunchArgument(
            name='queue_size',
            default_value='0'
        ),
        DeclareLaunchArgument(
            name='tracker_rviz',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='gui',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='tracker_log_level',
            default_value='info'
        ),
        DeclareLaunchArgument(
            name='enable_fast_mapping',
            default_value='false'
        ),
        DeclareLaunchArgument(
            name='zmin',
            default_value='0.3'
        ),
        DeclareLaunchArgument(
            name='zmax',
            default_value='0.6'
        ),
        DeclareLaunchArgument(
            name='depth_max_range',
            default_value='2.5'
        ),
        DeclareLaunchArgument(
            name='octree_store_path',
            default_value='""'
        ),
        DeclareLaunchArgument(
            name='traj_store_path',
            default_value='"./traj/"'
        ),
        DeclareLaunchArgument(
            name='octree_load_path',
            default_value='"./map/octree.bin"'
        ),
        DeclareLaunchArgument(
            name='odom_frame',
            default_value='odom'
        ),
        DeclareLaunchArgument(
            name='slam_mode',
            default_value='localization'
        ),
        DeclareLaunchArgument(
            name='image_topic',
            default_value=image_topic_
        ),
        DeclareLaunchArgument(
            name='depth_topic',
            default_value=depth_topic_
        ),
        DeclareLaunchArgument(
            name='camera_info_topic',
            default_value=camera_info_topic_
        ),
        DeclareLaunchArgument(
            name='depthmap_factor',
            default_value='1.0'
        ),
        # Delay to launch tracker node after and server node
        TimerAction(period=2.0, actions=[tracker_launch])
    ]

    return ld_list       

def generate_launch_description():
    tracker = generate_tracker_description()
    server = generate_server_description()
    turtlebot3_sim = generate_turtlebot_sim_description()
    launch_description = tracker + server + turtlebot3_sim
    return launch.LaunchDescription(launch_description)

if __name__ == '__main__':
    generate_launch_description()

