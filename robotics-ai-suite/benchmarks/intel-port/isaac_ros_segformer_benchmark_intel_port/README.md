<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® SegFormer Benchmark - Intel Port

This folder contains a complete, self-contained setup for running the SegFormer semantic segmentation benchmark on Intel CPU/iGPU systems using OpenVINO.

## Contents

- **setup_segformer_intel.sh** — One-command setup script
- **isaac_ros_segformer_intel.py** — Benchmark test script
- **plugin_scaffold/** — Minimal Intel SegmentationOpenVINONode plugin
  - `segmentation_openvino_node.hpp` — Plugin header
  - `segmentation_openvino_node.cpp` — Plugin implementation (publishes segmentation Image)
  - `isaac_ros_benchmark.CMakeLists.txt` — Intel-compatible CMake
  - `isaac_ros_benchmark.package.xml` — Trimmed dependencies

## Quickstart

```bash
cd /path/to/this/folder
./setup_segformer_intel.sh
```

One command handles all setup: installs deps → fetches repos → adds plugin → patches CMake → downloads dataset → builds → prints run command.

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
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_segformer_benchmark/scripts/isaac_ros_segformer_intel.py
```

## Results

Benchmark outputs are saved to `/tmp/r2b-log-*.json`. Extract metrics with:

```bash
cat /tmp/r2b-log-*.json | python3 -m json.tool
```

## Tuning

Control benchmark behavior with environment variables:

- `OV_DEVICE` — Device: `"CPU"` (default), `"GPU"`, `"AUTO:GPU,CPU"`
- `OV_NUM_INFER_THREADS` — Thread count (0 = auto, default)
- `R2B_PUBLISHER_UPPER_FPS` — Data rate (default: 80)
- `R2B_PLAYBACK_BUFFER_SIZE` — Message buffer (default: 100)

## Scope

The plugin is a minimal scaffold that publishes segmentation output (`sensor_msgs/Image`) for benchmarking. It is **not** a full SegFormer semantic segmentation implementation. For accuracy testing, integrate the actual OpenVINO segmentation model.

## Dataset

Downloaded automatically from NVIDIA® NGC:
- https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/
- Total size: ~2.9 GB
