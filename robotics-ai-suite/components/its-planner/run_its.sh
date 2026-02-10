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

print_usage() {
  printf "Usage: %s [-d]\n" "$0"
  printf "  -d   Use Ackermann (Dubins) params\n"
}

yaml_file="nav2_params_${ROS_DISTRO}.yaml"
bt_xml_file="navigate_w_recovery_${ROS_DISTRO}.xml"

while getopts 'dh' flag; do
  case "${flag}" in
    d) yaml_file="nav2_params_dubins_${ROS_DISTRO}.yaml" ;;
    h) print_usage ; exit 0 ;;
    *) print_usage ; exit 1 ;;
  esac
done

source "${current_dir}"/install/setup.bash

export TURTLEBOT3_MODEL=waffle

# Set Gazebo model path (variable name differs between distributions)
if [ "$ROS_DISTRO" = "jazzy" ]; then
    export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:/opt/ros/"$ROS_DISTRO"/share/turtlebot3_gazebo/models
else
    export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/"$ROS_DISTRO"/share/turtlebot3_gazebo/models
fi

ros2 launch nav2_bringup tb3_simulation_launch.py \
  headless:=False \
  params_file:="${current_dir}/its_planner/${yaml_file}" \
  default_bt_xml_filename:="${current_dir}/its_planner/${bt_xml_file}"
