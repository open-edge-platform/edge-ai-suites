<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# OpenVINO Optimization Notes for CenterPose (Intel Port)

This benchmark script now supports OpenVINO tuning through environment variables.

## Tunable variables

- OV_DEVICE
  - Default: CPU
  - Example: CPU, GPU, AUTO:GPU,CPU
- OV_NUM_INFER_THREADS
  - Default: 0 (OpenVINO auto)
  - Typical CPU sweep values: 4, 8, 12
- OV_INIT_WAIT_SEC
  - Default: 3.0
  - Increase when model initialization is slow
- R2B_PUBLISHER_UPPER_FPS
  - Default: 120.0
  - Raise for stronger throughput search, lower for stability
- R2B_PUBLISHER_LOWER_FPS
  - Default: 10.0
- R2B_PLAYBACK_BUFFER_SIZE
  - Default: 100
  - Keep <= available synchronized message pairs in your selected bag time range

## Example runs

CPU throughput-oriented run:

OV_DEVICE=CPU \
OV_NUM_INFER_THREADS=8 \
R2B_PUBLISHER_UPPER_FPS=120 \
R2B_PLAYBACK_BUFFER_SIZE=100 \
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_centerpose_benchmark/scripts/isaac_ros_centerpose_intel.py

AUTO device selection run:

OV_DEVICE=AUTO:GPU,CPU \
OV_NUM_INFER_THREADS=0 \
R2B_PUBLISHER_UPPER_FPS=90 \
R2B_PLAYBACK_BUFFER_SIZE=100 \
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_centerpose_benchmark/scripts/isaac_ros_centerpose_intel.py

## Result collection

Benchmark logs are emitted to terminal and JSON under /tmp:

- /tmp/r2b-log-*.json

Copy results into a project folder for comparison between runs.
