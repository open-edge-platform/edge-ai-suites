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

# Kill any leftover ROS nodes from a previous run
ros2 daemon stop 2>/dev/null || true
killall -9 adbscan_sub_w_gesture_audio 2>/dev/null || true
pkill -9 -f gesture_recognition_node.py 2>/dev/null || true
pkill -9 -f speech_recognition_node.py 2>/dev/null || true
pkill -9 -f traj_and_img_publisher_node 2>/dev/null || true
pkill -9 -f audio_publisher_node.py 2>/dev/null || true
pkill -9 -f text_to_speech_node.py 2>/dev/null || true
sleep 2
ros2 daemon start 2>/dev/null || true

export TURTLEBOT3_MODEL=waffle

RVIZ_CONFIG="$(ros2 pkg prefix followme_turtlebot3_gazebo)/share/followme_turtlebot3_gazebo/rviz/followme_lidar.rviz"
TTS_PARAMS="$(ros2 pkg prefix text_to_speech_pkg)/share/text_to_speech_pkg/config/text_to_speech_config.yaml"

echo "=========================================="
echo "RealSense Follow-Me Demo (Gesture + Audio)"
echo "=========================================="
echo "Step 1/4: Starting text-to-speech node..."
ros2 run text_to_speech_pkg text_to_speech_node.py \
    --ros-args --params-file "${TTS_PARAMS}" &
sleep 10

echo "Step 2/4: Launching Gazebo world + bridges (depth camera model)..."
ros2 launch followme_turtlebot3_gazebo rs_shared.launch.py &

echo "Waiting 15s for Gazebo to initialize..."
sleep 15

echo "Step 3/4: Launching ADBSCAN + gesture + audio nodes..."
ros2 launch followme_turtlebot3_gazebo rs_gesture_audio.launch.py &

echo "Step 4/4: Opening RViz..."
echo "=========================================="
rviz2 -d "${RVIZ_CONFIG}"

