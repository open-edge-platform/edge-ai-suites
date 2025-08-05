#!/bin/bash
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

cd "$( dirname "$0" )" || exit

BAGS_DIR=/opt/ros/humble/share/bagfiles
INSTALL_DIR=/opt/ros/humble/share/collab-slam

# Include pre-script which handles clean shutdown of all background processes
. $INSTALL_DIR/pre.sh

# Launch the server
ros2 launch univloc_server server.launch.py rviz:=true &
pid1=$!

# Launch the first robot, Tracker 1
ros2 launch univloc_tracker tracker.launch.py publish_tf:=false queue_size:=0 ID:=0 rviz:=false gui:=false use_odom:=false &
pid2=$!

# Launch the second robot, Tracker 2
ros2 launch univloc_tracker tracker.launch.py camera:=camera1 publish_tf:=false queue_size:=0 ID:=1 rviz:=false gui:=false use_odom:=false &
pid3=$!

# Simulate 2 robots wandering around in a common area using pre-recorded ros2 bag files

# Launch the robot 1 bag
sleep 1
ros2 bag play $BAGS_DIR/robot1 --topics /camera/aligned_depth_to_color/camera_info /camera/aligned_depth_to_color/image_raw /camera/color/camera_info /camera/color/image_raw /tf_static &
pid4=$!

# Launch the robot 2 bag
sleep 4
ros2 bag play -r 0.8 $BAGS_DIR/robot2 --remap /camera/aligned_depth_to_color/camera_info:=/camera1/aligned_depth_to_color/camera_info /camera/aligned_depth_to_color/image_raw:=/camera1/aligned_depth_to_color/image_raw /camera/color/camera_info:=/camera1/color/camera_info /camera/color/image_raw:=/camera1/color/image_raw --topics /camera/aligned_depth_to_color/camera_info /camera/aligned_depth_to_color/image_raw /camera/color/camera_info /camera/color/image_raw /tf_static &
pid5=$!

echo $pid1 $pid2 $pid3 $pid4 $pid5 > /tmp/cslam.pid

# Wait for CTRL-C to be pressed
tail -f /dev/null
