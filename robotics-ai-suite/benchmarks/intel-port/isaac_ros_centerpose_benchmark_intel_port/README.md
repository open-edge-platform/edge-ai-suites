<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® CenterPose Benchmark - Intel Port

This folder now includes a complete Intel-friendly setup path that works on a clean machine without requiring an NVIDIA® GPU.

Complete runnable paths with setup scripts in this repository:
- isaac_ros_centerpose_benchmark_intel_port/README.md
- isaac_ros_apriltag_benchmark_intel_port/README.md

## Included Files

- `isaac_ros_centerpose_intel.py`: CenterPose benchmark script
- `setup_centerpose_intel.sh`: one-command setup (downloads sources, patches/builds workspace, downloads dataset)
- `plugin_scaffold/*`: minimal `CenterPoseOpenVINONode` plugin files needed by the script
- `OPENVINO_OPTIMIZATION.md`: runtime tuning knobs

## Important Scope Note

The scaffolded plugin included here makes the benchmark pipeline runnable and measurable on Intel CPU/iGPU systems.
It publishes `vision_msgs/Detection3DArray` outputs for throughput/latency benchmarking, but it is not a full accuracy-focused CenterPose inference implementation.

## Prerequisites

- Ubuntu 24.04 (recommended) or 22.04
- ROS 2 Jazzy installed at `/opt/ros/jazzy` (or set `ROS_DISTRO` to your distro)
- `sudo` access for package installation

## Quickstart (Recommended)

From this folder:

```bash
chmod +x setup_centerpose_intel.sh
./setup_centerpose_intel.sh
```

Optional custom workspace path:

```bash
./setup_centerpose_intel.sh /path/to/ros2_ws
```

The script handles:

1. Installing required apt and pip dependencies
2. Fetching `isaac_ros_benchmark` and `ros2_benchmark` (uses `git` when available, archive download otherwise)
3. Installing this benchmark script and plugin scaffold into the workspace
4. Patching `ros2_benchmark` CMake files for environments without `isaac_ros_common`
5. Downloading `r2b_storage` dataset files from NGC into:
   `~/ros2_ws/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage`
6. Building required packages with `colcon`
7. Printing the exact run command

## Manual Run Command

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ISAAC_ROS_WS=~/ros2_ws

# Optional tuning
export OV_DEVICE=CPU
export OV_NUM_INFER_THREADS=8
export R2B_PUBLISHER_UPPER_FPS=80
export R2B_PLAYBACK_BUFFER_SIZE=100

launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_centerpose_benchmark/scripts/isaac_ros_centerpose_intel.py
```

## Results

Benchmark reports are written to:

- terminal output
- `/tmp/r2b-log-*.json`

Archive results:

```bash
mkdir -p ~/ros2_ws/src/isaac_ros_benchmark/results
cp /tmp/r2b-log-*.json ~/ros2_ws/src/isaac_ros_benchmark/results/
```

## Dataset Source Links Used by Setup Script

- `https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/metadata.yaml`
- `https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/r2b_storage_0.db3`

