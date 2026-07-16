<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® DNN Image Encoder Benchmark - Intel Port

This folder contains a standalone Intel benchmark script:
- `isaac_ros_dnn_image_encoder_intel.py`

It benchmarks image resize/encode path using `image_proc::ResizeNode` in a ROS2 benchmark graph.

## Requirements
- ROS 2 Jazzy
- `ros2_benchmark`
- `image_proc`
- Dataset at:
  `src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage`

## Setup

### 1) Create workspace and download benchmark sources

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_benchmark.git
git clone https://github.com/NVIDIA-ISAAC-ROS/ros2_benchmark.git
```

### 2) Copy the standalone script

```bash
cp /path/to/this/folder/isaac_ros_dnn_image_encoder_intel.py \
  ~/ros2_ws/src/isaac_ros_benchmark/benchmarks/isaac_ros_dnn_image_encoder_benchmark/scripts/
```

### 3) Install dependencies

```bash
sudo apt update
sudo apt install -y \
  python3-colcon-common-extensions \
  ros-jazzy-image-proc \
  ros-jazzy-launch-testing \
  ros-jazzy-launch-testing-ament-cmake
```

### 4) Build

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
```

### 5) Prepare dataset

Place the r2b dataset under:

`~/ros2_ws/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage`

### 6) Run benchmark

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ISAAC_ROS_WS=~/ros2_ws

launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_dnn_image_encoder_benchmark/scripts/isaac_ros_dnn_image_encoder_intel.py
```

### 7) Collect result

```bash
cp /tmp/r2b-log-*.json ~/ros2_ws/src/isaac_ros_benchmark/results/
```
