<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UAV Vision Analytics — Skill Prompts

Quick reference for all supported skills. Each link opens the full example prompts for that skill.

> For a detailed description of every skill, see [SKILLS_OVERVIEW.md](SKILLS_OVERVIEW.md).

---

## Prerequisites

To use these skills you need a coding agent that can read skill files and execute terminal commands. Any of the following work:

| Agent | How to get it |
|-------|--------------|
| **GitHub Copilot CLI** | Install the [GitHub CLI](https://cli.github.com/) and run `gh extension install github/gh-copilot` |
| **GitHub Copilot in VS Code** | Install the [GitHub Copilot extension](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot) in VS Code |
| **Any OpenAI-compatible agent** | Any coding agent that supports reading `.md` skill files and running shell commands |

Once your agent is set up, copy a prompt from the table below (or from the linked prompt file) and paste it into the agent's chat interface.

---

## Operational Skills

| # | Skill | Description | Prompts |
|---|-------|-------------|---------|
| 1 | **Run Pipeline** | Start/stop inference pipelines — automated via pipeline manager (armed/disarmed trigger) or manually via REST API. Covers CPU, GPU, and NPU variants. | [01-run-pipeline.md](supported_prompts/01-run-pipeline.md) |
| 2 | **Benchmarking** | Measure inference FPS per device, run stream density tests to find maximum concurrent pipelines, and query system resource utilisation from metrics-manager. | [02-benchmarking.md](supported_prompts/02-benchmarking.md) |
| 3 | **Troubleshooting** | Diagnose pipelines not starting on ARM, missing RTSP streams, GPU/NPU device access failures, model not found errors, and REST API connectivity issues. | [03-troubleshooting.md](supported_prompts/03-troubleshooting.md) |
| 4 | **Add / Remove Telemetry Fields** | Add new MAVLink fields (e.g. battery voltage, roll/pitch) to the on-screen overlay, or remove existing fields (e.g. GPS coordinates for privacy). | [04-telemetry-fields.md](supported_prompts/04-telemetry-fields.md) |
| 5 | **MAVLink Message Discovery** | Run `mavlink_listener.py` to print all MAVLink messages and their fields from the flight controller — use before adding new telemetry overlay fields. | [05-mavlink-listener.md](supported_prompts/05-mavlink-listener.md) |
| 6 | **RealSense Camera** | Start inference on a live Intel RealSense camera feed using the `uav_realsense_{cpu,gpu,npu}` pipelines via the REST API. | [06-realsense.md](supported_prompts/06-realsense.md) |

## Application Skills

| # | Skill | Description | Prompts |
|---|-------|-------------|---------|
| 7 | **Create pymavlink App** | Scaffold a self-contained stack with PX4 SITL, mavlink-router, MQTT broker, and DLSPS. Pipelines auto-start on MAVLink ARMED signal. | [07-create-pymavlink-app.md](supported_prompts/07-create-pymavlink-app.md) |
| 8 | **Create UAVSDK App** | Scaffold a single-container DLSPS stack that integrates with `uav-mission-compute-sdk`. MQTT-triggered with RTSP pre-flight probe. Three-camera (nadir/forward/rear) supported. | [08-create-mavsdk-app.md](supported_prompts/08-create-mavsdk-app.md) |
| 9 | **File-based Pipeline** | Configure a looped video file (`gazebo.avi`) as the pipeline source for simulation and development. | [09-file-pipeline.md](supported_prompts/09-file-pipeline.md) |
| 10 | **RealSense / Camera Pipeline** | Configure a `v4l2src` pipeline for an Intel RealSense or UVC camera attached to the companion computer. | [06-realsense.md](supported_prompts/06-realsense.md) |
| 11 | **RTSP Source Pipeline** | Configure an `rtspsrc` pipeline consuming an external IP camera or SDK Gazebo simulation stream. | [10-rtsp-pipeline.md](supported_prompts/10-rtsp-pipeline.md) |

---

## Quick Lookup

| I want to… | Skill # | Prompt file |
|-----------|---------|------------|
| Start pipelines automatically when UAV arms | 1 | [01-run-pipeline.md](supported_prompts/01-run-pipeline.md#automated-pipeline-manager) |
| Manually start a CPU/GPU/NPU pipeline | 1 | [01-run-pipeline.md](supported_prompts/01-run-pipeline.md#manual--start-a-single-cpu-pipeline) |
| Measure FPS and find max concurrent streams | 2 | [02-benchmarking.md](supported_prompts/02-benchmarking.md#stream-density-test) |
| Fix pipelines not starting on ARM | 3 | [03-troubleshooting.md](supported_prompts/03-troubleshooting.md#pipelines-not-starting-on-arm) |
| Fix GPU/NPU pipeline errors | 3 | [03-troubleshooting.md](supported_prompts/03-troubleshooting.md#gpu-pipeline-fails-to-start) |
| Add battery voltage to the video overlay | 4 | [04-telemetry-fields.md](supported_prompts/04-telemetry-fields.md#add-battery-voltage-to-the-overlay) |
| Remove GPS coordinates from the overlay | 4 | [04-telemetry-fields.md](supported_prompts/04-telemetry-fields.md#remove-gps-coordinates-for-privacy) |
| See all MAVLink messages my flight controller sends | 5 | [05-mavlink-listener.md](supported_prompts/05-mavlink-listener.md#list-all-messages-from-px4-sitl) |
| Use a RealSense camera as video input | 6 | [06-realsense.md](supported_prompts/06-realsense.md#start-a-realsense-cpu-pipeline) |
| Build a new pymavlink-based stack | 7 | [07-create-pymavlink-app.md](supported_prompts/07-create-pymavlink-app.md#self-contained-simulation-stack-all-devices) |
| Build a new UAVSDK-based stack | 8 | [08-create-mavsdk-app.md](supported_prompts/08-create-mavsdk-app.md#three-camera-integration-nadir--forward--rear) |
| Use a looped video file as source | 9 | [09-file-pipeline.md](supported_prompts/09-file-pipeline.md#use-looped-gazeboavi-as-video-source) |
| Configure a RealSense / UVC camera pipeline | 10 | [06-realsense.md](supported_prompts/06-realsense.md#start-a-realsense-gpu-pipeline) |
| Use an IP camera or external RTSP stream | 11 | [10-rtsp-pipeline.md](supported_prompts/10-rtsp-pipeline.md#start-pipeline-consuming-an-external-rtsp-camera) |
