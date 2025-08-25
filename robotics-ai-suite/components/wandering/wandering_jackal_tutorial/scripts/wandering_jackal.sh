#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
INSTALL_DIR="$(dirname "${SCRIPT_DIR}")"
NAV2_PARAM_FILE="${INSTALL_DIR}"/params/jackal_nav.param.yaml

# Go to script directory
cd "${SCRIPT_DIR}" || exit

# Verify that ROS_DISTRO is set and not empty
if [ -z "${ROS_DISTRO}" ]; then
    echo "ROS_DISTRO is not set or empty. Please source the ROS distro's setup script first."
    exit 1
fi

# Check that the Clearpath Robot metapackage is installed.
PKG_NAME=ros-humble-clearpath-robot
PKG_INSTALLED=$(dpkg -s "${PKG_NAME}" 2> /dev/null | grep -c "install ok installed")
if [ "${PKG_INSTALLED}" -ne 1 ]; then
    echo "Package $PKG_NAME is not installed."
    echo "Add the Clearpath Package Server to your APT database and"
    echo "install the Clearpath Robot metapackage as described in the"
    echo "Clearpath Robotics documentation:"
    echo "https://docs.clearpathrobotics.com/docs/ros/installation/robot/"
    exit 1
fi

# Identify the namespace of the Clearpath camera. This is either
# - /sensors/camera_0/camera (if ros-humble-realsense2-camera version is 4.55) or
# - /sensors/camera_0 (if ros-humble-realsense2-camera version is 4.54).
CAMERA_TOPIC=$(ros2 topic list | grep "/depth/image_rect_raw$")
DELIMITER="/depth/image_rect_raw"
CAMERA_NAMESPACE="${CAMERA_TOPIC%$DELIMITER*}"
if [ "${CAMERA_NAMESPACE}" = "/sensors/camera_0/camera" ]; then
    RTABMAP_LAUNCH_FILE="rtabmap_jackal.launch.py"
    RVIZ2_CONFIG_FILE="${INSTALL_DIR}"/rviz/nav2_wandering_view.rviz
elif [ "${CAMERA_NAMESPACE}" = "/sensors/camera_0" ]; then
    RTABMAP_LAUNCH_FILE="rtabmap_jackal.rs454.launch.py"
    RVIZ2_CONFIG_FILE="${INSTALL_DIR}"/rviz/nav2_wandering_view.rs454.rviz
else
    echo "Camera namespace is not valid: ${CAMERA_NAMESPACE}"
    echo "Please check your Intel RealSense Camera configuration."
    exit 1
fi

# Run the pre-script which handles clean shutdown of all background processes
. "${SCRIPT_DIR}"/pre.sh

# Run the depthimage_to_laserscan_node. Include the appropriate link name into
# the output_frame. For Clearpath robots, the link is "camera_0_depth_frame".
ros2 run depthimage_to_laserscan depthimage_to_laserscan_node --ros-args \
         --remap depth:=${CAMERA_NAMESPACE}/depth/image_rect_raw \
         --remap depth_camera_info:=${CAMERA_NAMESPACE}/depth/camera_info \
         -p scan_time:=0.033 -p range_min:=0.1 -p range_max:=2.5 \
         -p output_frame:=camera_0_depth_frame &
pid="$!"

ros2 launch wandering_jackal_tutorial "${RTABMAP_LAUNCH_FILE}" localization:=false &
pid="$pid $!"

sleep 2
# Launch the IMU Madgwick Filter Interface
ros2 run imu_filter_madgwick imu_filter_madgwick_node --ros-args \
         -p remove_gravity_vector:=true -p use_mag:=false -p publish_tf:=false \
         --remap /imu/data_raw:=/sensors/imu_0/data_raw &
pid="$pid $!"

#ros2 launch nav2_bringup rviz_launch.py &
ros2 launch nav2_bringup rviz_launch.py rviz_config:="${RVIZ2_CONFIG_FILE}" &
pid="$pid $!"

ros2 launch nav2_bringup navigation_launch.py params_file:="${NAV2_PARAM_FILE}" &
pid="$pid $!"

sleep 2

ros2 run wandering_app wandering --ros-args --params-file "${NAV2_PARAM_FILE}" &
pid="$pid $!"

echo "${pid}" > /tmp/wandering_jackal.pid

# Wait for Ctrl-C
echo "Press Ctrl-C to stop..."
wait
