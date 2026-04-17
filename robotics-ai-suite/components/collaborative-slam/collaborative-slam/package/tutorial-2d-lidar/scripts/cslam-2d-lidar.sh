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

# Set paths based on detected distro
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

echo "Starting collab-slam with ROS $ROS_DISTRO..."

# Launch the robot tracker
ros2 launch univloc_tracker tracker.launch.py ID:=0 queue_size:=0 publish_tf:=false rviz:=true gui:=false log_level:=warning camera_setup:=RGBD use_lidar:=true &
pid1=$!

# Launch the robot bag
ros2 bag play $BAGS_DIR/2d-lidar &
pid2=$!

echo $pid1 $pid2 > /tmp/cslam.pid
echo "Started processes with PIDs: $pid1 $pid2"

# Wait for CTRL-C to be pressed
echo "Press CTRL-C to stop..."
tail -f /dev/null
