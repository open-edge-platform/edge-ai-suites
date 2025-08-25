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

# Launch robot localization
ros2 run robot_localization ukf_node --ros-args --params-file $INSTALL_DIR/tutorial-multi-camera/ukf_config_two_camera.yaml &
pid1=$!

# Publish static TF for extrinsic matrices
#
# the following two static_transform_publisher can be deleted if already published somewhere else
# please change the TF frame names and values according to your setup
# alternatively, you can publish the static transform from base_link to each <camera>_link and
# RealSense camera will publish the static transform from <camera>_link to <camera>_color_optical_frame
ros2 run tf2_ros static_transform_publisher -0.283 0.028 0.368 -0.509 -0.503 0.485 0.502 base_link d455_front_color_optical_frame --ros-args -p use_sim_time:=true &
pid2=$!
ros2 run tf2_ros static_transform_publisher 0.213 -0.038 0.354 -0.495 0.509 -0.508 0.488 base_link d455_rear_color_optical_frame --ros-args -p use_sim_time:=true &
pid3=$!

# Launch two trackers for two cameras streams
#
# change "camera" and "image_frame" as necessary according to your setup
ros2 launch univloc_tracker tracker.launch.py ID:=0 queue_size:=0 gui:=false publish_tf:=false camera:=d455_front rviz:=true need_covariance:=true &
pid4=$!
ros2 launch univloc_tracker tracker.launch.py ID:=2 queue_size:=0 gui:=false publish_tf:=false camera:=d455_rear rviz:=true need_covariance:=true &
pid5=$!

# Save trajectory outputs from trackers and Kalman Filter
#
# the trajectories will be stored and then analyzed using cslam-multi-camera-traj-compare.py
sleep 2
ros2 topic echo /univloc_tracker_0/kf_pose > /tmp/tracker0.txt &
pid6=$!
ros2 topic echo /univloc_tracker_2/kf_pose > /tmp/tracker2.txt &
pid7=$!
ros2 topic echo /odometry/filtered > /tmp/kf_robot.txt &
pid8=$!

# Play ROS2 bag
#
# robot localization package cannot properly handle ROS bags, see details in https://github.com/ros2/rosbag2/issues/299 (no issue using real robot)
# so we need to use a separate python script to change the timestamp of msgs to current time to avoid the issue
python3 $INSTALL_DIR/tutorial-multi-camera/play_rosbag_ros2.py $BAGS_DIR/multi-camera use_sim_time=0 keep_time=0 &
pid9=$!
sleep 2
pid10=$(pgrep -f "/usr/bin/python3 -c from ros2cli.daemon.daemonize" | head -n 1)

echo "$pid1" "$pid2" "$pid3" "$pid4" "$pid5" "$pid6" "$pid7" "$pid8" "$pid9" "$pid10" > /tmp/cslam.pid

# Wait for CTRL-C to be pressed
tail -f /dev/null
