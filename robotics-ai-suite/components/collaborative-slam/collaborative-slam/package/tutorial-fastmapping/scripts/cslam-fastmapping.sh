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
RVIZ_FIL=$INSTALL_DIR/tutorial-fastmapping/collab_slam_fm.rviz

# Check if directories and files exist
if [ ! -d "$BAGS_DIR" ]; then
    echo "Error: Bags directory not found: $BAGS_DIR"
    exit 1
fi

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: Install directory not found: $INSTALL_DIR"
    exit 1
fi

if [ ! -f "$RVIZ_FIL" ]; then
    echo "Error: RViz config file not found: $RVIZ_FIL"
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

# Launch the robot tracker
ros2 launch univloc_tracker collab_slam_nav.launch.py use_odom:=true server_rviz:=false enable_fast_mapping:=true zmin:=0.2 zmax:=0.5 &
pid1=$!

# Launch rviz
sleep 2
rviz2 -d $RVIZ_FIL &
pid2=$!

# Launch the robot bag
ros2 bag play $BAGS_DIR/robot1 &
pid3=$!

echo $pid1 $pid2 $pid3 > /tmp/cslam.pid

# Wait for CTRL-C to be pressed
tail -f /dev/null
