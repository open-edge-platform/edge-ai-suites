#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

current_dir=$(dirname "$(realpath ${BASH_SOURCE[0]})")

source /opt/ros/humble/setup.bash
source ../../install/setup.bash
export TURTLEBOT3_MODEL=waffle
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models

if [ "$1" = "localization" ]; then
 ros2 launch collab_localization.launch.py remap_map_id:='/univloc_server/map'  default_bt_xml_filename:=/${current_dir}/../its_planner/navigate_w_recovery.xml
elif [ "$1" = "mapping" ]; then
 ros2 launch collab_mapping.launch.py remap_map_id:='/univloc_tracker_0/map'
fi

