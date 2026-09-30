#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# adbscan_run.sh — Thin wrapper around benchmark_runner.sh for the adbscan scenario.
#
# All CLI options are forwarded to benchmark_runner.sh unchanged.
# To customise the launch command, bag topics, stop condition, or any other
# scenario behaviour, edit config/adbscan_run.yaml instead of this file.
#
# The scenario is launched via:
#   ros2 launch adbscan_ros2 play_demo_lidar_launch.py
# which starts adbscan_sub_node, and ros2 bag play of the bundled
# pointcloud bag (/opt/ros/jazzy/share/bagfiles/laser-pointcloud/) together.
#
# Usage:
#   bash src/adbscan_run.sh [--timeout SECS] [--plot] [--output-parent DIR]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
exec "$SCRIPT_DIR/benchmark_runner.sh" \
  --run-config "$REPO_ROOT/config/adbscan_run.yaml" \
  "$@"
