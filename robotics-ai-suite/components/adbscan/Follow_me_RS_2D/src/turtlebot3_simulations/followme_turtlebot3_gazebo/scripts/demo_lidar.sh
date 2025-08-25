#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

source /opt/ros/humble/setup.bash 
sudo killall -9 gazebo gzserver gzclient
export TURTLEBOT3_MODEL=waffle
ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_lidar_v2.launch.py &
rviz2 -d /opt/ros/humble/share/followme_turtlebot3_gazebo/rviz/followme_lidar.rviz