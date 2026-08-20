<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Example: PX4 SITL Simulation — pymavlink, CPU + GPU + NPU, looped video

Build a full end-to-end UAV object detection and telemetry overlay stack in
`./uav-sim-stack/` using the uav-vision-analytics skill.

**Scenario:** Simulate a UAV flight using PX4 SITL. Detect aerial objects in a
looped Gazebo simulation video using YOLOv8n-VisDrone on CPU, GPU, and NPU.
Overlay live MAVLink telemetry (altitude, speed, heading, GPS) on the annotated
RTSP stream. Pipelines start automatically when the UAV arms and stop on disarm.

**Requirements:**
- Deployment mode: `pymavlink` (self-contained with PX4 SITL)
- Video source: `file` (gazebo.avi, looped)
- Inference device: `all` (generate CPU, GPU, and NPU pipeline variants)
- Model: `yolov8n-visdrone` (default)
- Output directory: `./uav-sim-stack/`

Produce:
- `docker-compose-pymavlink.yml` with all required services
- `configs/config-pymavlink.json` with three pipeline variants (cpu, gpu, npu)
- `gvapython/telemetry-overlay-pymavlink.py` overlay script
- `scripts/mavlink_pipeline_manager.py` pipeline manager
- `mavlink-router/main.conf` routing config
- `Makefile` with model, up/down, start-rtsp targets
- `.env` template
- `tests/` pytest suite

Verify against all completion criteria before declaring success.
