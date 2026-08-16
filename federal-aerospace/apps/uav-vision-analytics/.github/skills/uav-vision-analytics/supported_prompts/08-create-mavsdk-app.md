<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Create a MAVSDK-based Application

## Three-camera integration (nadir / forward / rear)

```
Create a full end-to-end UAV vision analytics application in ./my-mavsdk-stack/
using the uav-vision-analytics skill.

Deployment mode: mavsdk (integrates with uav-mission-compute-sdk)
Video source: gazebo-rtsp (RTSP from SDK at rtsp://host.docker.internal:8554/uav-1/*)
Inference device: all (nadir=CPU, forward=GPU, rear=NPU)
Model: yolov8n-visdrone
UAV ID: uav-1
Output directory: ./my-mavsdk-stack/

Generate:
- docker-compose-mavsdk.yml (single DLSPS container)
- configs/config-mavsdk.json with nadir_camera_rtsp_cpu, forward_camera_rtsp_gpu, rear_camera_rtsp_npu pipelines
- gvapython/telemetry-overlay-mavsdk.py (MQTT-based telemetry)
- scripts/mavsdk_pipeline_manager.py (MQTT armed trigger + ffprobe RTSP pre-flight probe)
- Makefile with mavsdk-up/down, start-rtsp targets
- .env template
- tests/ pytest suite

Note: uav-mission-compute-sdk must be running before starting this stack.
Verify all completion criteria before declaring success.
```

## Single-camera, CPU only

```
Create a minimal MAVSDK UAV vision analytics stack in ./uav-mavsdk-nadir/
with a single nadir camera pipeline (CPU).
Deployment mode: mavsdk. Video source: gazebo-rtsp.
RTSP source: rtsp://host.docker.internal:8554/uav-1/nadir.
Device: CPU. UAV ID: uav-1.
Include docker-compose-mavsdk.yml, config.json, pipeline manager, Makefile, and .env.
```

## Custom UAV ID

```
Create a MAVSDK UAV vision analytics stack in ./uav-fleet-stack/
for UAV ID "uav-3". The MQTT telemetry topic will be uav/uav-3/telemetry/status.
Deployment mode: mavsdk. Video source: gazebo-rtsp. Device: all.
All three camera pipelines (nadir/CPU, forward/GPU, rear/NPU) should use
rtsp://host.docker.internal:8554/uav-3/* as RTSP sources.
Generate all required files including Makefile and tests.
```
