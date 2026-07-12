#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Intel Corporation

# This script builds .deb files for the rvc application package.
# The shared robot_config and gazebo_plugins packages live under
# PicknPlace/ and are built by PicknPlace/gen_deb.sh.

cd rvc || exit
DEB_BUILD_OPTIONS="nocheck" dpkg-buildpackage -us -uc -b -tc -d
cd ..

# Cleanup extra files
rm -f ./*.buildinfo
rm -f ./*.changes
rm -f ./*.ddeb

# Running demo Instructions
# RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ros2 launch rvc rvc.launch.py
