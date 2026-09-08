<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# UAV Vision Analytics Application

The UAV Vision Analytics application is an AI-powered UAV object detection application with live telemetry overlay, optimized for Intel® edge hardware. It processes video from a UAV-mounted camera (or a simulated video file), runs YOLO11s inference across 80 object classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) on the output RTSP stream. The stream is consumable by any capable client, such as QGroundControl (QGC), VLC, and ffplay.

The application is built on Intel DL Streamer Pipeline Server and supports two deployment modes: a self-contained **Standalone (pymavlink)** mode using Gazebo/PX4 Software-in-the-Loop (SITL) simulation, and a **UAV Mission Compute SDK** mode that integrates with a running instance of the UAV Mission Compute SDK for full mission control and multi-camera pipeline management. Both modes are deployed on top of the Edge Node Infrastructure software - an edge computing platform, which enables hardware acceleration capabilities. See [Infrastructure Setup](docs/user-guide/infrastructure-setup.md) for build and provisioning steps.

## Project Structure

```text
docker-compose-pymavlink.yml  Standalone mode: PX4 SITL, mavlink-router, broker, DLSPS, metrics-manager.
docker-compose-uavsdk.yml     UAV Mission Compute SDK mode: DLSPS only (connects to an external SDK stack).
.env.example                  Template for .env — GPU/NPU/camera device paths and image tags.
Makefile                      Operational targets (init, model, pymav-*, uavsdk-*, start-rtsp).
configs/                      Mosquitto and mavlink-router configuration, DLSPS pipeline configs.
gvapython/                    Telemetry overlay Python scripts (pymavlink and UAVSDK variants).
scripts/                      Pipeline manager and MAVLink listener scripts.
resources/                    Python requirements for `make model`, sample input video, and the exported YOLO11s model (after running `make model`).
benchmark/                    Stream density benchmarking tooling (`calc_stream_density.sh`).
```

## Stack

### Standalone Mode (pymavlink)

| Service | Image | Role |
|---------|-------|------|
| `broker` | `eclipse-mosquitto:2.0.22` | MQTT broker for telemetry and pipeline events |
| `px4` | `px4io/px4-sitl:latest` | PX4 SITL flight controller simulation |
| `mavlink-router` | Built from `uav-mission-compute-sdk/infra/px4-sim/mavlink-router` | Routes MAVLink telemetry between PX4 and the pipeline server |
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc3` (+ `pymavlink`) | Core inference engine — YOLO11s detection and telemetry overlay |
| `metrics-manager` | `intel/metrics-manager:2026.2.0-rc3` | Host platform (CPU/GPU) metrics, exposed on port 9090 |

All services share the `app_network` Docker network and are defined in [`docker-compose-pymavlink.yml`](docker-compose-pymavlink.yml).

### UAV Mission Compute SDK Mode

| Service | Image | Role |
|---------|-------|------|
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24-rc3` | Core inference engine — YOLO11s detection and telemetry overlay; connects to an externally running UAV Mission Compute SDK stack |

Defined in [`docker-compose-uavsdk.yml`](docker-compose-uavsdk.yml). Requires the
`edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk` stack to be running first.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker Engine release 24 or later | [Install guide](https://docs.docker.com/engine/install/) |
| Docker Compose v2 | Included with Docker Desktop; on Linux OS, install the `docker-compose-plugin` package. Use `docker compose` (space), not `docker-compose` (hyphen). |
| Intel® GPU with OpenVINO support | Required for `GPU_DEVICE` / `GPU_RENDER_DEVICE` in `.env`. |
| Python 3 with `venv` | Required by `make model` to create a Python virtual environment for exporting YOLO11s. |
| Intel® NPU (optional) | For NPU-accelerated pipelines; falls back to `/dev/null` (disabled) if not detected. |
| USB or RealSense camera (optional) | For live-camera pipelines; auto-detected by `make init`. |

Run `make init` after cloning to create `.env` from `.env.example` and auto-detect GPU, NPU, and camera device paths.

## Quick Start

### Step 1: Download the model

```bash
cd uav-vision-analytics
make model
```

This creates a Python virtual environment, downloads YOLO11s, and exports it to OpenVINO FP16 format under `resources/models/yolo11s/`.

### Step 2: Start a deployment mode

**Standalone Mode (pymavlink)** — self-contained, no external dependencies:

```bash
make pymav-up
```

**UAV Mission Compute SDK Mode** — requires the UAV Mission Compute SDK stack running first:

```bash
make uavsdk-up
```

### Step 3: Start RTSP pipelines

```bash
make start-rtsp DEVICE=gpu   # or cpu | npu | all
```

## Endpoints

| Service | URL / Path | Notes |
|---------|-----------|-------|
| DL Streamer Pipeline Server REST API | `http://localhost:8081` | Pipeline control and status |
| RTSP annotated stream | `rtsp://localhost:8555` | Detection + telemetry overlay output |
| Metrics manager (Standalone mode only) | `http://localhost:9090` | Host platform (CPU/GPU) metrics |

## Make Targets

```text
make init          Create .env from template and auto-detect GPU/NPU/camera device paths
make model         Download YOLO11s and export to OpenVINO FP16
make pymav-up       Start standalone pymavlink stack (PX4 SITL + broker + DLSPS + metrics-manager)
make pymav-down     Stop and remove pymavlink stack (includes volumes)
make uavsdk-up      Start UAV Mission Compute SDK stack (requires uav-mission-compute-sdk running first)
make uavsdk-down    Stop and remove UAV Mission Compute SDK stack (includes volumes)
make start-rtsp     Start RTSP pipelines. DEVICE=cpu|gpu|npu|all (default: gpu)
make build          Alias: start the default pymavlink stack
```

## Related Documentation

- [User Guide](docs/user-guide/index.md) — Full deployment, configuration, and how-to guides.
- [Infrastructure Setup](docs/user-guide/infrastructure-setup.md) — Build the OS image, flash it to a bootable USB, and validate the provisioned platform.
- [Benchmarks](docs/user-guide/benchmark.md) — Measure stream density and hardware utilization.
- [Agent SKILLs](docs/user-guide/agents.md) — AI agent skills for platform automation and DL Streamer pipeline generation.
