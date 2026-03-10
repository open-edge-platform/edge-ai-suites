#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

# Detect ROS2 distribution
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    ROS_DISTRO="jazzy"
    echo "Using ROS2 Jazzy with Gazebo Harmonic"
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    ROS_DISTRO="humble"
    echo "Using ROS2 Humble with Gazebo Fortress"
else
    echo "Error: No supported ROS2 distribution found (humble or jazzy)"
    exit 1
fi

# shellcheck disable=SC1090
source /opt/ros/${ROS_DISTRO}/setup.bash

# Source workspace to get correct package paths
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
if [ -f "${WORKSPACE_DIR}/install/setup.bash" ]; then
    # shellcheck source=/dev/null
    source "${WORKSPACE_DIR}/install/setup.bash"
fi

# Source Gazebo environment for Humble
if [ -f "/usr/share/gazebo/setup.bash" ]; then
    # shellcheck disable=SC1091
    source /usr/share/gazebo/setup.bash
fi

# Kill Gazebo processes based on distribution
if [ "$ROS_DISTRO" = "jazzy" ]; then
    # Gazebo Harmonic (gz sim)
    sudo killall -9 gz ruby
else
    # Gazebo Fortress and older (gazebo classic)
    sudo killall -9 gazebo gzserver gzclient
fi

export TURTLEBOT3_MODEL=waffle

# Get the correct rviz config path from installed workspace
RVIZ_CONFIG="$(ros2 pkg prefix followme_turtlebot3_gazebo)/share/followme_turtlebot3_gazebo/rviz/followme_lidar.rviz"

ros2 launch followme_turtlebot3_gazebo empty_world_followme_w_gesture_lidar_v2.launch.py &
rviz2 -d "${RVIZ_CONFIG}"
