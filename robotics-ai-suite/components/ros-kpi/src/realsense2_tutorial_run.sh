#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# realsense2_tutorial_run.sh — Thin wrapper around benchmark_runner.sh for the
# realsense2_tutorial scenario.
#
# All CLI options are forwarded to benchmark_runner.sh unchanged.
# To customise the launch command, camera_type, bag topics, stop condition,
# or any other scenario behaviour, edit config/realsense2_tutorial_run.yaml
# instead of this file.
#
# Before running, use the realsense2_tutorial package's scripts/find_cameras.sh
# to check whether a USB or GMSL D457 camera is connected, and pass
# camera_type:=gmsl via config/realsense2_tutorial_run.yaml's launch.args if
# needed (default is camera_type:=usb).
#
# The scenario is launched via:
#   ros2 launch realsense2_tutorial realsense2_tutorial.launch.py
# which starts the RealSense camera driver and rviz2 together.
#
# Usage:
#   bash src/realsense2_tutorial_run.sh [--timeout SECS] [--record] [--plot] [--output-parent DIR]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
exec "$SCRIPT_DIR/benchmark_runner.sh" \
  --run-config "$REPO_ROOT/config/realsense2_tutorial_run.yaml" \
  "$@"
