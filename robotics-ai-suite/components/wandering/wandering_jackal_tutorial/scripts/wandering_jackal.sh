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

# Clearpath robot namespace — override via environment if needed
export ROBOT_NAMESPACE="${ROBOT_NAMESPACE:-/j100_0123}"

# Go to script directory
cd "${SCRIPT_DIR}" || exit

# Verify that ROS_DISTRO is set and not empty
if [ -z "${ROS_DISTRO}" ]; then
    echo "ROS_DISTRO is not set or empty. Please source the ROS distro's setup script first."
    exit 1
fi

# Source Clearpath setup for RMW and other environment variables
if [ -f /etc/clearpath/setup.bash ]; then
    # shellcheck source=/dev/null
    . /etc/clearpath/setup.bash
else
    echo "WARNING: /etc/clearpath/setup.bash not found. ROS_DOMAIN_ID may be wrong."
fi

# Always read ROS_DOMAIN_ID from robot.yaml (source of truth).
# setup.bash is auto-generated from robot.yaml but can be manually edited,
# so we override it here to ensure we match the robot's domain.
ROBOT_YAML="/etc/clearpath/robot.yaml"
if [ -f "${ROBOT_YAML}" ]; then
    CLEARPATH_DOMAIN_ID=$(grep "domain_id:" "${ROBOT_YAML}" | head -1 | awk '{print $2}')
    if [ -n "${CLEARPATH_DOMAIN_ID}" ]; then
        export ROS_DOMAIN_ID="${CLEARPATH_DOMAIN_ID}"
    fi
fi
echo "Using ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"

# Source the local install overlay so our built package takes precedence over /opt/ros
LOCAL_SETUP="${INSTALL_DIR}/install/local_setup.bash"
if [ -f "${LOCAL_SETUP}" ]; then
    # shellcheck source=/dev/null
    . "${LOCAL_SETUP}"
else
    echo "WARNING: Local install overlay not found at ${LOCAL_SETUP}. Run 'colcon build' first."
fi

# Check that the Clearpath Robot metapackage is installed.
# Identify the namespace of the Clearpath camera. This is either
# - /sensors/camera_0/camera (if ros-humble-realsense2-camera version is 4.55) or
# - /sensors/camera_0 (if ros-humble-realsense2-camera version is 4.54).
CAMERA_TOPIC=$(ros2 topic list | grep "/depth/image$")
DELIMITER="/depth/image"
CAMERA_NAMESPACE="${CAMERA_TOPIC%$DELIMITER*}"
echo "${CAMERA_NAMESPACE}"
if [ "${CAMERA_NAMESPACE}" = "${ROBOT_NAMESPACE}/sensors/camera_0/" ]; then
    RTABMAP_LAUNCH_FILE="rtabmap_jackal.launch.py"
    RVIZ2_CONFIG_FILE="${INSTALL_DIR}"/rviz/nav2_wandering_view.rviz
elif [ "${CAMERA_NAMESPACE}" = "${ROBOT_NAMESPACE}/sensors/camera_0" ]; then
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
# Note: clearpath remaps depth/image_rect_raw -> depth/image, so use depth/image.
ros2 run depthimage_to_laserscan depthimage_to_laserscan_node --ros-args \
         --remap depth:=${CAMERA_NAMESPACE}/depth/image \
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
         --remap /imu/data_raw:=${ROBOT_NAMESPACE}/sensors/imu_0/data_raw &
pid="$pid $!"

#ros2 launch nav2_bringup rviz_launch.py &
#ros2 launch nav2_bringup rviz_launch.py rviz_config:="${RVIZ2_CONFIG_FILE}" &
#pid="$pid $!"

ros2 launch wandering_jackal_tutorial navigation_jackal.launch.py params_file:="${NAV2_PARAM_FILE}" log_level:=info &
pid="$pid $!"

sleep 2

ros2 run wandering_app wandering --ros-args --params-file "${NAV2_PARAM_FILE}" \
         -r /tf:=${ROBOT_NAMESPACE}/tf \
         -r /tf_static:=${ROBOT_NAMESPACE}/tf_static &
pid="$pid $!"

echo "${pid}" > /tmp/wandering_jackal.pid

# Wait for Ctrl-C
echo "Press Ctrl-C to stop..."
wait
