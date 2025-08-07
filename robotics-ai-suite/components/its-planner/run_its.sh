#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

current_dir=$(dirname "$(realpath ${BASH_SOURCE[0]})")
source /opt/ros/humble/setup.bash

if [ ! -d "./build/" ] 
then
    echo "Building ITS-Planner."
    colcon build --packages-select nav2_msgs
    colcon build --packages-select nav2_amcl
    colcon build --packages-select its_planner
    source install/setup.bash
    colcon build --packages-select send_localization
    colcon build --packages-select pose_checker
    colcon build --packages-select benchmarking
fi

print_usage() {
  printf "Usage: ..."
}

yaml_file='nav2_params.yaml'
while getopts 'd' flag; do
  case "${flag}" in
    d) yaml_file='nav2_params_dubins.yaml' ;;
    *) exit 1 ;;
  esac
done

source install/setup.bash 
#export TURTLEBOT3_MODEL=waffle
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models

#ros2 launch nav2_bringup tb3_simulation_launch.py

#ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False

ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/"${current_dir}"/its_planner/${yaml_file} default_bt_xml_filename:=/"${current_dir}"/its_planner/navigate_w_recovery.xml default_bt_xml_filename:=/"${current_dir}"/its_planner

#ros2 launch nav2_bringup tb3_simulation_launch.py params_file:=/"${current_dir}"/its_planner/${yaml_file} default_bt_xml_filename:=/"${current_dir}"/its_planner/navigate_w_recovery.xml map_server:=/home/awm/ati_deliverables/applications.robotics.mobile.its-planner/nav2_bringup/bringup/maps/turtlebot3_house.pgm

#ros2 launch pose_checker.yaml

#ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py

#ros2 launch nav2_bringup tb3_simulation_launch.py slam:=True

