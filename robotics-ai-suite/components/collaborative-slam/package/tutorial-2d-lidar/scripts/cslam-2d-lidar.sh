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

cd "$( dirname "$0" )" || exit

BAGS_DIR=/opt/ros/humble/share/bagfiles
INSTALL_DIR=/opt/ros/humble/share/collab-slam

# Include pre-script which handles clean shutdown of all background processes
. $INSTALL_DIR/pre.sh

# Launch the robot tracker
ros2 launch univloc_tracker tracker.launch.py ID:=0 queue_size:=0 publish_tf:=false rviz:=true gui:=false log_level:=warning camera_setup:=RGBD use_lidar:=true &
pid1=$!

# Launch the robot bag
ros2 bag play $BAGS_DIR/2d-lidar &
pid2=$!

echo $pid1 $pid2 > /tmp/cslam.pid

# Wait for CTRL-C to be pressed
tail -f /dev/null
