#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# fastmapping_run.sh — Thin wrapper around benchmark_runner.sh for the fast-mapping scenario.
#
# All CLI options are forwarded to benchmark_runner.sh unchanged.
# To customise the launch command, bag topics, stop condition, or any other
# scenario behaviour, edit config/fastmapping_run.yaml instead of this file.
#
# The scenario is launched via:
#   ros2 launch fast_mapping fast_mapping.launch.py
# which starts fast_mapping_node, rviz2, and ros2 bag play of the bundled
# spinning bag (/opt/ros/<distro>/share/bagfiles/spinning/) together.
#
# Usage:
#   bash src/fastmapping_run.sh [--timeout SECS] [--plot] [--output-parent DIR]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
exec "$SCRIPT_DIR/benchmark_runner.sh" \
  --run-config "$REPO_ROOT/config/fastmapping_run.yaml" \
  "$@"
