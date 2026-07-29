<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® DOPE Benchmark - Intel Port

This folder contains a complete, self-contained setup for running the DOPE (6D pose estimation) benchmark on Intel CPU/iGPU systems using OpenVINO.

## Contents

- **setup_dope_intel.sh** — One-command setup script  
- **isaac_ros_dope_intel.py** — Benchmark test script
- **plugin_scaffold/** — Minimal Intel DopeOpenVINONode plugin
  - `dope_openvino_node.hpp` — Plugin header
  - `dope_openvino_node.cpp` — Plugin implementation (publishes Detection3DArray)
  - `isaac_ros_benchmark.CMakeLists.txt` — Intel-compatible CMake
  - `isaac_ros_benchmark.package.xml` — Trimmed dependencies

## Quickstart

```bash
cd /path/to/this/folder
./setup_dope_intel.sh
```

Automatically configures environment, downloads dependencies, builds packages, and prints run command.

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
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_dope_benchmark/scripts/isaac_ros_dope_intel.py
```

## Results

Results are saved to `/tmp/r2b-log-*.json`:

```bash
cat /tmp/r2b-log-*.json | python3 -m json.tool
```

## Environment Tuning

- `OV_DEVICE` — Device: `"CPU"` (default), `"GPU"`, `"AUTO:GPU,CPU"`
- `OV_NUM_INFER_THREADS` — Thread count (0 = auto, default)
- `R2B_PUBLISHER_UPPER_FPS` — Data publication rate (default: 80)
- `R2B_PLAYBACK_BUFFER_SIZE` — Message buffer size (default: 100)

## Scope

The plugin is a minimal scaffold that publishes `vision_msgs/Detection3DArray` for benchmarking. It is **not** a full DOPE pose inference implementation. For accuracy testing, add actual OpenVINO pose estimation logic.

## Dataset

Downloaded from NVIDIA® NGC via setup script:
- https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/
