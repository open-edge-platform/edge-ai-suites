<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® Apriltag Benchmark - Intel Port

This folder contains a self-contained setup for running the Apriltag benchmark on Intel systems, following the same structure as the other benchmark intel_port folders.

Complete runnable paths with setup scripts in this repository:
- isaac_ros_centerpose_benchmark_intel_port/README.md
- isaac_ros_apriltag_benchmark_intel_port/README.md

## Contents

- setup_apriltag_intel.sh - One-command environment setup
- isaac_ros_apriltag_intel.py - Apriltag benchmark launch_test script

## Quickstart

Run setup:

```bash
cd /path/to/run-competitive-benchmarks-main/isaac_ros_apriltag_benchmark_intel_port
chmod +x setup_apriltag_intel.sh
./setup_apriltag_intel.sh
```

The setup script will:
1. Install required ROS packages
2. Fetch isaac_ros_benchmark and ros2_benchmark sources
3. Install the Apriltag benchmark script into the benchmark repo
4. Download r2b_dataset files into ros2_benchmark assets
5. Print the exact launch_test command

## Run Manually

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
export ISAAC_ROS_WS=~/ros2_ws
export R2B_PUBLISHER_UPPER_FPS=80
export R2B_PLAYBACK_BUFFER_SIZE=80
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_apriltag_benchmark/scripts/isaac_ros_apriltag_intel.py
```

## Tunable Environment Variables

- R2B_PUBLISHER_UPPER_FPS (default 80)
- R2B_PUBLISHER_LOWER_FPS (default 10)
- R2B_PLAYBACK_BUFFER_SIZE (default 80)
- APRILTAG_FAMILY (default 36h11)
- APRILTAG_SIZE_METERS (default 0.162)

## Integrity And Reproducibility Variables

- ISAAC_ROS_BENCHMARK_REF (default pinned commit)
- ROS2_BENCHMARK_REF (default pinned commit)
- R2B_METADATA_SHA256 (default set; metadata.yaml is verified by default)
- R2B_STORAGE_SHA256 (default empty; r2b_storage_0.db3 verification is skipped unless set)

If you want integrity verification for the DB file, set R2B_STORAGE_SHA256 before running setup:

```bash
export R2B_STORAGE_SHA256=<expected_sha256_for_r2b_storage_0.db3>
./setup_apriltag_intel.sh
```
