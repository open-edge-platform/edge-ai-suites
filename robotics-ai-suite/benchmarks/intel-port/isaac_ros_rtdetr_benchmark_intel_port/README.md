<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® RT-DETR Benchmark - Intel Port

This folder contains a complete, self-contained setup for running the RT-DETR (Real-Time DETR) object detection benchmark on Intel CPU/iGPU systems using OpenVINO.

## Contents

- **setup_rtdetr_intel.sh** — One-command setup script
- **isaac_ros_rtdetr_intel.py** — Benchmark test script
- **plugin_scaffold/** — Minimal Intel RtDetrOpenVINONode plugin
  - `rtdetr_openvino_node.hpp` — Plugin header
  - `rtdetr_openvino_node.cpp` — Plugin implementation (publishes Detection2DArray)
  - `isaac_ros_benchmark.CMakeLists.txt` — Intel-compatible CMake
  - `isaac_ros_benchmark.package.xml` — Trimmed dependencies

## Quickstart

```bash
cd /path/to/this/folder
./setup_rtdetr_intel.sh
```

Fully automated setup: dependencies → repos → plugin → patches → dataset → build → run command.

## Manual Run

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ISAAC_ROS_WS=~/ros2_ws
export OV_DEVICE=CPU
export OV_NUM_INFER_THREADS=8
export R2B_PUBLISHER_UPPER_FPS=80
export R2B_PLAYBACK_BUFFER_SIZE=100
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_rtdetr_benchmark/scripts/isaac_ros_rtdetr_intel.py
```

## Results

Benchmark results are output to `/tmp/r2b-log-*.json`. View with:

```bash
cat /tmp/r2b-log-*.json | python3 -m json.tool
```

## Tuning Parameters

- `OV_DEVICE` — Inference device: `"CPU"` (default), `"GPU"`, `"AUTO:GPU,CPU"`
- `OV_NUM_INFER_THREADS` — Inference thread count (0 = auto)
- `R2B_PUBLISHER_UPPER_FPS` — Publisher rate limit (default: 80)
- `R2B_PLAYBACK_BUFFER_SIZE` — Message playback buffer (default: 100)

## Scope & Limitations

This plugin is a minimal scaffold for benchmarking throughput and latency. It publishes `vision_msgs/Detection2DArray` for each frame. It is **not** a production RT-DETR inference implementation. For accuracy evaluation, integrate the actual OpenVINO model.

## Dataset

Automatically downloaded from NVIDIA® NGC:
- Source: https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/
- Size: ~2.9 GB
