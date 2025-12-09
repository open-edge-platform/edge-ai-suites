#!/bin/bash

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

cd "$( dirname "$0" )" || exit

# Detect ROS distro
if [ -z "$ROS_DISTRO" ]; then
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        export ROS_DISTRO="jazzy"
    elif [ -f "/opt/ros/humble/setup.bash" ]; then
        export ROS_DISTRO="humble"
    else
        echo "Error: No supported ROS distro found (humble/jazzy)"
        exit 1
    fi
fi

echo "Using ROS distro: $ROS_DISTRO"

BAGS_DIR=/opt/ros/$ROS_DISTRO/share/bagfiles
INSTALL_DIR=/opt/ros/$ROS_DISTRO/share/collab-slam

# Check if directories exist
if [ ! -d "$BAGS_DIR" ]; then
    echo "Error: Bags directory not found: $BAGS_DIR"
    exit 1
fi

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: Install directory not found: $INSTALL_DIR"
    exit 1
fi

# Include pre-script which handles clean shutdown of all background processes
if [ -f "$INSTALL_DIR/pre.sh" ]; then
    . $INSTALL_DIR/pre.sh
else
    echo "Warning: pre.sh not found in $INSTALL_DIR"
fi

# Source ROS setup
echo "Sourcing ROS $ROS_DISTRO setup..."
source /opt/ros/$ROS_DISTRO/setup.bash

echo "Launch files with ROS $ROS_DISTRO..."


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
