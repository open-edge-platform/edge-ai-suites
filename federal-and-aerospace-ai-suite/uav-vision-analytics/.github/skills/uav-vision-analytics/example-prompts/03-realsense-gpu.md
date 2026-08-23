<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Example: Intel RealSense Camera — GPU Inference, RTSP Output

Build an end-to-end UAV vision analytics stack in `./uav-realsense-stack/`
using the uav-vision-analytics skill.

**Scenario:** A UAV companion computer is connected to an Intel RealSense depth
camera (RGB stream via v4l2). Detect aerial objects on GPU from the live
RealSense video feed. Overlay live MAVLink telemetry. Serve the annotated
stream as RTSP for consumption by QGroundControl or ffplay. PX4 SITL provides
the simulated flight controller.

**Requirements:**
- Deployment mode: `pymavlink`
- Video source: `realsense` (v4l2src `/dev/video0`, 640×480 BGR)
- Inference device: `GPU`
- Model: `yolov8n-visdrone`
- Output directory: `./uav-realsense-stack/`

Produce:
- `docker-compose-pymavlink.yml` with all required services
- `configs/config-realsense.json` with a RealSense GPU pipeline
- `gvapython/telemetry-overlay-pymavlink.py` overlay
- `scripts/mavlink_pipeline_manager.py`
- `mavlink-router/main.conf`
- `Makefile` with model, up/down, start-rtsp targets
- `.env` template
- `tests/` pytest suite

Note: RealSense device must be physically connected and accessible as
`/dev/video0` on the host. The compose file must mount the device and
include the appropriate `group_add` GID for the video group.

Verify against all completion criteria before declaring success.
