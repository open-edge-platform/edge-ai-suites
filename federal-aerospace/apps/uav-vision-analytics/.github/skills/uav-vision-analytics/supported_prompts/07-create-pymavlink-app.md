<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Create a pymavlink-based Application

## Self-contained simulation stack (all devices)

```
Create a full end-to-end UAV vision analytics application in ./my-uav-stack/
using the uav-vision-analytics skill.

Deployment mode: pymavlink (self-contained with PX4 SITL)
Video source: file (looped gazebo.avi)
Inference device: all (generate CPU, GPU, and NPU pipeline variants)
Model: yolov8n-visdrone
Output directory: ./my-uav-stack/

Generate:
- docker-compose-pymavlink.yml with all services (DLSPS, broker, px4, mavlink-router, metrics-manager)
- configs/config-pymavlink.json with uav_object_detection_cpu/gpu/npu pipelines
- gvapython/telemetry-overlay-pymavlink.py overlay script
- scripts/mavlink_pipeline_manager.py (--sink rtsp)
- mavlink-router/main.conf
- Makefile with model, pymav-up/down, start-rtsp targets
- .env template
- tests/ pytest suite

Verify all completion criteria before declaring success.
```

## CPU-only, custom overlay name

```
Create a UAV vision analytics pymavlink stack in ./uav-cpu-only/.
Deployment mode: pymavlink. Video source: file. Device: CPU only.
Model: yolov8n-visdrone. Overlay name label: "Mission-Alpha-CPU".
Generate only the CPU pipeline variant (uav_object_detection_cpu).
Include Makefile, .env, and basic pytest tests.
```

## With RealSense camera source

```
Create a UAV vision analytics pymavlink stack in ./uav-realsense-stack/
that uses an Intel RealSense camera (v4l2src /dev/video0) as the video source.
Deployment mode: pymavlink. Device: GPU.
Generate the uav_realsense_gpu pipeline in config.json with v4l2src
source element (640x480 BGR, 30fps). Include all standard services,
Makefile, .env, and tests.
```
