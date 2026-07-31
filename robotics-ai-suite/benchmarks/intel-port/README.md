<!--
Copyright (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Run Competitive Benchmarks (Intel Port)

This repository contains Intel-focused benchmark ports for multiple ISAAC ROS® pipelines.
Each benchmark is organized in its own folder with self-contained scripts and setup notes.

## Included Benchmarks

- `isaac_ros_apriltag_benchmark_intel_port`: AprilTag detection benchmark.
- `isaac_ros_centerpose_benchmark_intel_port`: CenterPose benchmark.
- `isaac_ros_detectnet_benchmark_intel_port`: DetectNet benchmark.
- `isaac_ros_dnn_image_encoder_benchmark_intel_port`: DNN image encoder benchmark.
- `isaac_ros_dope_benchmark_intel_port`: DOPE benchmark.
- `isaac_ros_rtdetr_benchmark_intel_port`: RT-DETR benchmark.
- `isaac_ros_segformer_benchmark_intel_port`: SegFormer benchmark.

## How To Use

1. Change into a benchmark folder.
2. Read that folder's `README.md` for benchmark-specific instructions.
3. If available, run the local setup script (`setup_<benchmark>_intel.sh`).
4. Run the benchmark Python launcher in that folder.

## Typical Workflow

```bash
cd isaac_ros_apriltag_benchmark_intel_port
./setup_apriltag_intel.sh
python3 isaac_ros_apriltag_intel.py
```

## Notes

- Setup and runtime options can differ by benchmark.
- Use each folder README as the source of truth for dependencies, environment variables, and launch details.
