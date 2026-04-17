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
TMP_DIR=/tmp/

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

# Launch the robot tracker
ros2 launch univloc_tracker collab_slam_nav.launch.py slam_mode:=mapping server_mode:=mapping queue_size:=0 publish_tf:=false camera:=camera1 baselink_frame:=base_link1 image_frame:=camera1_color_optical_frame use_odom:=true odom_frame:=odom1 odom_tf_query_timeout:=50.0 tracker_rviz:=true server_rviz:=true enable_fast_mapping:=true octree_store_path:=$TMP_DIR/octree.bin save_map_path:=$TMP_DIR/map.msg &
pid1=$!

# Launch the robot bag
sleep 1
ros2 bag play $BAGS_DIR/extra-features &
pid2=$!

echo $pid1 $pid2 > /tmp/cslam.pid

# Wait for CTRL-C to be pressed
tail -f /dev/null
