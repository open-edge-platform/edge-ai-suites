<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Supported Skills — UAV Vision Analytics

This document lists all supported skills with a brief description and a link
to the complete example prompts for each. Use the prompts as-is or adapt them
to your specific configuration.

---

## Operational Skills

These skills work with an **existing deployed stack**.

| # | Skill | Description | Prompts |
|---|-------|-------------|---------|
| 1 | **Run Pipeline** | Start/stop inference pipelines — automated via pipeline manager (armed/disarmed trigger) or manually via REST API. Covers CPU, GPU, and NPU variants. | [01-run-pipeline.md](01-run-pipeline.md) |
| 2 | **Benchmarking** | Measure inference FPS per device, run stream density tests to find maximum concurrent pipelines, and query system resource utilisation from metrics-manager. | [02-benchmarking.md](02-benchmarking.md) |
| 3 | **Troubleshooting** | Diagnose pipelines not starting on ARM, missing RTSP streams, GPU/NPU device access failures, model not found errors, and REST API connectivity issues. | [03-troubleshooting.md](03-troubleshooting.md) |
| 4 | **Add / Remove Telemetry Fields** | Add new MAVLink fields (e.g. battery voltage, roll/pitch) to the on-screen overlay, or remove existing fields (e.g. GPS coordinates for privacy). | [04-telemetry-fields.md](04-telemetry-fields.md) |
| 5 | **MAVLink Message Discovery** | Run `mavlink_listener.py` to print all MAVLink messages and their fields from the flight controller — use before adding new telemetry overlay fields. | [05-mavlink-listener.md](05-mavlink-listener.md) |
| 6 | **RealSense Camera** | Start inference on a live Intel RealSense camera feed using the `uav_realsense_{cpu,gpu,npu}` pipelines via the REST API. | [06-realsense.md](06-realsense.md) |

---

## Application Skills

These skills **create a new UAV vision analytics stack** from scratch.

### Create an Application

| # | Skill | Description | Prompts |
|---|-------|-------------|---------|
| 7 | **Create pymavlink App** | Scaffold a self-contained stack with PX4 SITL, mavlink-router, MQTT broker, and DLSPS. Pipelines auto-start on MAVLink ARMED signal. Supports file, RealSense, or RTSP video sources and all device targets. | [07-create-pymavlink-app.md](07-create-pymavlink-app.md) |
| 8 | **Create MAVSDK App** | Scaffold a single-container DLSPS stack that integrates with `uav-mission-compute-sdk`. Pipelines triggered by MQTT armed/disarmed state with RTSP pre-flight probe. Three-camera (nadir/forward/rear) supported. | [08-create-mavsdk-app.md](08-create-mavsdk-app.md) |

### Pipeline Source Choice

| # | Skill | Source Element | Use When | Prompts |
|---|-------|---------------|---------|---------|
| 9 | **File-based Pipeline** | `multifilesrc gazebo.avi loop=true` | Development and simulation without physical hardware | [09-file-pipeline.md](09-file-pipeline.md) |
| 10 | **RealSense / Camera Pipeline** | `v4l2src /dev/video0` | Intel RealSense or UVC camera physically attached to companion computer | [06-realsense.md](06-realsense.md) |
| 11 | **RTSP Source Pipeline** | `rtspsrc rtsp://...` | External IP camera or SDK Gazebo simulation camera streams | [10-rtsp-pipeline.md](10-rtsp-pipeline.md) |

---

## Quick Lookup

| I want to… | Skill # | Prompt file |
|-----------|---------|------------|
| Start pipelines automatically when UAV arms | 1 | [01-run-pipeline.md](01-run-pipeline.md) |
| Manually start a CPU/GPU/NPU pipeline | 1 | [01-run-pipeline.md](01-run-pipeline.md) |
| Measure FPS and find max concurrent streams | 2 | [02-benchmarking.md](02-benchmarking.md) |
| Fix pipelines not starting on ARM | 3 | [03-troubleshooting.md](03-troubleshooting.md) |
| Fix GPU/NPU pipeline errors | 3 | [03-troubleshooting.md](03-troubleshooting.md) |
| Add battery voltage to the video overlay | 4 | [04-telemetry-fields.md](04-telemetry-fields.md) |
| Remove GPS coordinates from the overlay | 4 | [04-telemetry-fields.md](04-telemetry-fields.md) |
| See all MAVLink messages my flight controller sends | 5 | [05-mavlink-listener.md](05-mavlink-listener.md) |
| Use a RealSense camera as video input | 6/10 | [06-realsense.md](06-realsense.md) |
| Build a new pymavlink-based stack | 7 | [07-create-pymavlink-app.md](07-create-pymavlink-app.md) |
| Build a new MAVSDK-based stack | 8 | [08-create-mavsdk-app.md](08-create-mavsdk-app.md) |
| Use a looped video file as source | 9 | [09-file-pipeline.md](09-file-pipeline.md) |
| Use an IP camera or external RTSP stream | 11 | [10-rtsp-pipeline.md](10-rtsp-pipeline.md) |
