<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Isaac ROS® DetectNet Benchmark - Intel Port

This folder contains a complete, self-contained setup for running the DetectNet (PeopleNet) benchmark on Intel CPU/iGPU systems using OpenVINO.

## Contents

- **setup_detectnet_intel.sh** — One-command setup script that configures entire environment
- **isaac_ros_detectnet_intel.py** — Benchmark test script  
- **plugin_scaffold/** — Minimal Intel DetectNetOpenVINONode plugin implementation
  - `detectnet_openvino_node.hpp` — Plugin header
  - `detectnet_openvino_node.cpp` — Plugin implementation (publishes Detection2DArray)
  - `isaac_ros_benchmark.CMakeLists.txt` — Intel-compatible CMake (no CUDA)
  - `isaac_ros_benchmark.package.xml` — Trimmed dependencies

## Quickstart

```bash
cd /path/to/this/folder
./setup_detectnet_intel.sh
```

This script:
1. Installs system dependencies (apt packages)
2. Installs Python runtime libraries (OpenVINO, NumPy, OpenCV)
3. Fetches NVIDIA® source repositories (isaac_ros_benchmark, ros2_benchmark)
4. Installs the Intel DetectNet plugin scaffold
5. Patches CMake to make NVIDIA®-specific dependencies optional
6. Downloads r2b_dataset from NVIDIA® NGC
7. Builds all packages with colcon
8. Prints the exact command to run the benchmark

## Running the Benchmark Manually

After setup completes, the printed command will look like:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ISAAC_ROS_WS=~/ros2_ws
export OV_DEVICE=CPU
export OV_NUM_INFER_THREADS=8
export R2B_PUBLISHER_UPPER_FPS=80
export R2B_PLAYBACK_BUFFER_SIZE=100
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_detectnet_benchmark/scripts/isaac_ros_detectnet_intel.py
```

## Collecting Results

The benchmark outputs JSON metrics to `/tmp/r2b-log-*.json`:

```bash
cat /tmp/r2b-log-*.json | python3 -m json.tool | grep -E "MEAN_FRAME_RATE|CPU_UTILIZATION|MEAN_LATENCY"
```

## Environment Variables for Tuning

The benchmark respects these OpenVINO environment variables:

- `OV_DEVICE` — Device target: `"CPU"` (default), `"GPU"`, `"AUTO:GPU,CPU"`  
- `OV_NUM_INFER_THREADS` — Manual thread count (0 = auto, default)
- `R2B_PUBLISHER_UPPER_FPS` — Data publication rate upper limit (default: 80)
- `R2B_PLAYBACK_BUFFER_SIZE` — Message sync buffer (default: 100)

## Scope & Limitations

The scaffolded plugin included here makes the benchmark pipeline runnable and measurable on Intel CPU/iGPU systems. It publishes `vision_msgs/Detection2DArray` outputs for throughput/latency benchmarking, but it is **not** a full accuracy-focused DetectNet inference implementation. For production accuracy, integrate an actual OpenVINO model.

## Dataset Source

The r2b_dataset is downloaded from NVIDIA® NGC:
- Metadata: https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/metadata.yaml
- Data file (2.9GB): https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/r2b_storage_0.db3

## Troubleshooting

**Build fails with "isaac_ros_common not found"**  
This is expected and handled by the CMake patches. The build continues without the NVIDIA®-only dependency.

**Benchmark script not found**  
Ensure `colcon build` completed successfully and you sourced `install/setup.bash`.

**Import errors in benchmark script**  
Verify `openvino`, `numpy`, and `opencv-python` are installed: `pip3 show openvino`
