<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Example: UAVSDK Integration — Three-Camera Nadir/Forward/Rear Detection

Build an end-to-end UAV vision analytics stack in `./uav-uavsdk-stack/` using
the uav-vision-analytics skill.

**Scenario:** Integrate with the `uav-mission-compute-sdk` project which is
already running. Three cameras (nadir downward, forward-facing, rear-facing)
stream RTSP video from the Gazebo simulation. Detect aerial objects on CPU
(nadir), GPU (forward), and NPU (rear). Overlay UAVSDK telemetry data on each
annotated stream. Automatically start all three pipelines when the UAV arms
(after probing each RTSP source with ffprobe) and stop them on disarm.

**Requirements:**
- Deployment mode: `uavsdk`
- Video source: `gazebo-rtsp` (RTSP from SDK: `rtsp://host.docker.internal:8554/uav-1/nadir`, `/forward`, `/rear`)
- Inference device: `all` (nadir=CPU, forward=GPU, rear=NPU)
- Model: `yolov8n-visdrone`
- Output directory: `./uav-uavsdk-stack/`
- UAV ID: `uav-1`

Produce:
- `docker-compose-uavsdk.yml` (single DLSPS container)
- `configs/config-uavsdk.json` with three camera pipeline variants
- `gvapython/telemetry-overlay-uavsdk.py` MQTT-based overlay
- `scripts/uavsdk_pipeline_manager.py` with ffprobe RTSP probing
- `Makefile` with uavsdk-up/down, start-rtsp targets
- `.env` template
- `tests/` pytest suite

**Prerequisite check:** Confirm `uav-mission-compute-sdk` is running before
generating the UAVSDK stack. If not confirmed, display the prerequisite message.

Verify against all completion criteria before declaring success.
