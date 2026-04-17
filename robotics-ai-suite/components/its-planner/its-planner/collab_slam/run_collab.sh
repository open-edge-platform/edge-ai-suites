#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

current_dir=$(dirname "$(realpath "${BASH_SOURCE[0]}")")

# Auto-detect ROS distribution instead of hardcoding
if [ -n "$ROS_DISTRO" ]; then
    echo "Using ROS distribution: $ROS_DISTRO"
    source /opt/ros/"$ROS_DISTRO"/setup.bash
else
    echo "ROS_DISTRO not set, attempting to detect..."
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        echo "Found Jazzy, using it"
        source /opt/ros/jazzy/setup.bash
    elif [ -f "/opt/ros/humble/setup.bash" ]; then
        echo "Found Humble, using it"  
        source /opt/ros/humble/setup.bash
    else
        echo "Error: No ROS installation found!"
        exit 1
    fi
fi

# Source workspace - use absolute path to avoid directory dependency issues
workspace_dir="$(realpath "${current_dir}"/../..)"
source "${workspace_dir}"/install/setup.bash

export TURTLEBOT3_MODEL=waffle

# Set Gazebo model path (variable name differs between distributions)
if [ "$ROS_DISTRO" = "jazzy" ]; then
    export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:/opt/ros/"$ROS_DISTRO"/share/turtlebot3_gazebo/models
else
    export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/"$ROS_DISTRO"/share/turtlebot3_gazebo/models
fi

if [ "$1" = "localization" ]; then
    echo "Starting collaborative localization..."
    cd "${current_dir}" || exit  # Ensure we're in the right directory for launch files
    ros2 launch collab_localization.launch.py remap_map_id:='/univloc_server/map' default_bt_xml_filename:="${workspace_dir}"/its_planner/navigate_w_recovery_"${ROS_DISTRO}".xml
elif [ "$1" = "mapping" ]; then
    echo "Starting collaborative mapping..."
    # Use proper ROS2 launch - TODO: move launch files to installed package  
    cd "${current_dir}" || exit  # Ensure we're in the right directory for launch files
    ros2 launch collab_mapping.launch.py remap_map_id:='/univloc_tracker_0/map'
else
    echo "Usage: $0 {localization|mapping}"
    echo "  localization - Start collaborative localization"
    echo "  mapping      - Start collaborative mapping"
    exit 1
fi

