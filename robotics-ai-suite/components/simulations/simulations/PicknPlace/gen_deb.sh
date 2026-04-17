#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

# This script build .deb files for each ros2 package.

cd robot_config || exit
DEB_BUILD_OPTIONS="nocheck" dpkg-buildpackage -us -uc -b -tc -d
cd ..

cd gazebo_plugins || exit
DEB_BUILD_OPTIONS="nocheck" dpkg-buildpackage -us -uc -b -tc -d
cd ..

cd picknplace || exit
DEB_BUILD_OPTIONS="nocheck" dpkg-buildpackage -us -uc -b -tc -d
cd ..

# Cleanup extra files
rm ./*.buildinfo
rm ./*.changes
rm ./*.ddeb


# Running demo Instructions

# install deb files from current directory.  Remove maxdepth if .deb files are in subdirectory
# find . -maxdepth 1 -name '*.deb' | xargs -i{} apt-get --fix-broken install -y {}

# Demo works well (stable) with cyclonedds.  Stability issues with default fastdds
# To use cyclonedds, include export command before launching demo
# RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ros2 launch picknplace warehouse.launch.py
