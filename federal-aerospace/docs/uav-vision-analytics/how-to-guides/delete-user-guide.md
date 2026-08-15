<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# User Guide — UAV Vision Analytics Application

This guide covers deployment, configuration, architecture, and design of the UAV Vision Analytics Application.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Design](#design)
3. [Prerequisites](#prerequisites)
4. [Deployment — Standalone (pymavlink)](#deployment--standalone-pymavlink)
5. [Deployment — uav-mission-compute-sdk mode](#deployment--uav-mission-compute-sdk-mode)
6. [Pipeline Configuration](#pipeline-configuration)
7. [Environment Variables Reference](#environment-variables-reference)
8. [REST API Reference](#rest-api-reference)
9. [Verifying the Output Stream](#verifying-the-output-stream)
10. [Stopping the Application](#stopping-the-application)
11. [Troubleshooting](#troubleshooting)

---

## Design

### Telemetry integration

The application supports two telemetry strategies, selected by the compose file used:

**pymavlink (standalone)**
- `mavlink-router` runs as a sidecar, receiving MAVLink from PX4 on UDP `:14550` and broadcasting it to `:14541`.
- A background `MavlinkReceiver` thread inside the DL Streamer container connects to `udpin:0.0.0.0:14541` and reads `GLOBAL_POSITION_INT`, `VFR_HUD`, and `GPS_RAW_INT` messages.
- Thread-safe access via a `threading.Lock` protecting the shared `latest_data` dict.

**uav-mission-compute-sdk / MQTT**
- `sdk_pipeline_manager.py` subscribes to `uav/{id}/telemetry/status` on the SDK project's MQTT broker (`:1884`).
- On ARMED: probes each RTSP source with `ffprobe`, then POSTs the three camera pipelines to the REST API.
- On DISARMED: DELETEs all running pipeline instances.
- The DL Streamer `gvapython` overlay (`telemetry-overlay-sdk.py`) also reads telemetry via MQTT.

### Overlay rendering

`gvapython` invokes `DrawDynamicText.process_frame()` on each decoded frame. The method reads the latest telemetry snapshot and calls `frame.add_region()` for each text line, positioning them as 1×1 pixel ROIs in the upper-left corner. The DL Streamer `gvawatermark` element renders these as visible text on the encoded RTSP stream.

### Hardware inference

| Device | `gvadetect` flag | Notes |
|---|---|---|
| CPU | `device=CPU` | Works on any x86 host |
| Intel GPU | `device=GPU` | Requires i915 / render group access (`/dev/dri/renderD128`) |
| Intel NPU | `device=NPU` | Requires `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so` and `/dev/accel/accel0` |

### RTSP output

Both compose files expose RTSP on port `8555`. The DL Streamer built-in RTSP server encodes frames from `appsink` to H264 using `vah264lpenc` (VA-API hardware encoder).

---

## Prerequisites

### System requirements

- **Host OS:** Ubuntu 22.04 or 24.04 (Blueprint OS validated)
- **Hardware:** Intel Panther Lake platform recommended; minimum 16 GB RAM
- **Software:** Docker Engine, Docker Compose v2

### Required packages

Install the following on the host before running any `make` target:

```bash
sudo apt update
sudo apt install -y \
  python3.12-venv \    # needed by make model (virtual environment)
  ffmpeg               # needed to view RTSP streams (ffplay) and record video
```

> **Why `python3.12-venv`?** The `make model` target creates a Python virtual environment via `python3 -m venv`. On Ubuntu 22/24 the venv support is a separate package not installed by default. Without it you will see:
> ```
> The virtual environment was not created successfully because ensurepip is not available.
> make: *** [Makefile:28: model] Error 1
> ```

> **Why `ffmpeg`?** The `ffplay` command (part of `ffmpeg`) is used to view the annotated RTSP output stream. Without it you will see:
> ```
> ffplay rtsp://... Command 'ffplay' not found
> ```

### Model

YOLOv8n-VisDrone exported to OpenVINO FP16 (see [export_model.md](export_model.md)). Run `make model` after installing `python3.12-venv`.

### GPU/NPU access (optional)

Device group IDs (`44`, `109`, `110`, `990`–`996`) must exist on the host for GPU and NPU pipelines.

---

## Deployment — Standalone (pymavlink)

### Step 1: Install prerequisites

```bash
sudo apt install -y python3.12-venv ffmpeg
```

### Step 2: Clone and configure

```bash
git clone <repo-url>
cd apps/uav-vision-analytics
make init
```

`make init` creates `.env` from the template and auto-detects Intel GPU paths. Then set your host IP:

```bash
nano .env   # set HOST_IP=<your-machine-IP>
```

### Step 3: Prepare the model

```bash
make model
```

This creates a virtualenv, installs dependencies, downloads the checkpoint from Hugging Face, and exports to OpenVINO FP16. See [export_model.md](export_model.md) for manual steps or if `make model` fails.

### Step 4: Start the stack

```bash
make pymav-up
```

Check that all containers are running:

```bash
docker compose -f docker-compose-pymavlink.yml ps
```

Expected services: `broker`, `mavlink-router`, `px4`, `dlstreamer-pipeline-server`, `metrics-manager`.

### Step 5: Start pipelines

Use `make start-rtsp` to launch the `mavlink_pipeline_manager.py` inside the container, which monitors the drone's armed state via MAVLink and starts/stops pipelines automatically:

```bash
make start-rtsp
```

Or start a pipeline manually via the REST API:

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/uav_object_detection_cpu \
  -H "Content-Type: application/json" \
  -d '{
    "destination": {
      "metadata": {
        "type": "file",
        "path": "/tmp/results.jsonl",
        "format": "json-lines"
      },
      "frame": {
        "type": "rtsp",
        "path": "uav-mavlink-cpu"
      }
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "CPU"
      }
    }
  }' | tr -d '"')
echo "Started instance: $INSTANCE_ID"
```

The annotated RTSP stream is available at `rtsp://<host-ip>:8555/uav-mavlink-cpu`.

To stop it:

```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```

---

## Deployment — uav-mission-compute-sdk mode

### Step 1: Start uav-mission-compute-sdk

```bash
cd uav-mission-compute-sdk
make up
# Wait ~60-90 s for PX4 SITL to become healthy
docker compose ps px4
```

### Step 2: Configure and start this application

```bash
cd apps/uav-vision-analytics
make init
nano .env   # set HOST_IP=<your-machine-IP> and UAV_ID (default: uav-1)

make sdk-up
```

### Step 3: Start the pipeline manager

```bash
make start-rtsp
```

Pipelines started automatically on ARMED:
- `nadir_camera_rtsp_cpu` — nadir camera, CPU
- `forward_camera_rtsp_gpu` — forward camera, GPU
- `rear_camera_rtsp_npu` — rear camera, NPU

Annotated streams available at `rtsp://<host-ip>:8555/nadir`, `/forward`, `/rear`.

---

## Pipeline Configuration

Pipeline definitions live in `configs/config-pymavlink.json` and `configs/config-sdk.json`. Each entry specifies:

| Field | Description |
|---|---|
| `name` | Pipeline identifier used in REST API paths |
| `source` | Always `"gstreamer"` |
| `queue_maxsize` | Internal frame queue depth (default 50) |
| `pipeline` | Full GStreamer launch string (hardcoded sources) |
| `parameters` | JSON Schema for runtime overrides via REST API |
| `auto_start` | `false` — all pipelines require explicit start |

### Switching inference device

Choose the pipeline name matching the desired device (`cpu` / `gpu` / `npu`). The device is encoded in both the pipeline name and the GStreamer launch string.

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `HOST_IP` | *(required)* | Host machine IP address (used for RTSP stream address) |
| `DLSTREAMER_PIPELINE_SERVER_IMAGE` | `intel/dlstreamer-pipeline-server:2026.2.0-...` | Docker image for DL Streamer |
| `UAV_ID` | `uav-1` | UAV identifier for MQTT topic subscription (uav-mission-compute-sdk mode) |
| `http_proxy` / `https_proxy` / `no_proxy` | *(optional)* | Proxy settings forwarded into containers |
| `ZE_ENABLE_ALT_DRIVERS` | `libze_intel_npu.so` | Enables Intel NPU plugin in OpenVINO (set inside compose) |

---

## REST API Reference

The DL Streamer Pipeline Server REST API is available at `http://localhost:8081`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/pipelines` | List all registered pipeline definitions |
| `GET` | `/pipelines/status` | Get status of all running pipeline instances |
| `POST` | `/pipelines/user_defined_pipelines/{name}` | Start a pipeline instance; returns UUID |
| `GET` | `/pipelines/{id}/status` | Get FPS, state, elapsed time for a specific instance |
| `DELETE` | `/pipelines/{id}` | Stop and remove a running instance |
| `GET` | `/models` | List loaded models |

**Example — list registered pipelines:**

```bash
curl http://localhost:8081/pipelines
```

**Example — start a pipeline:**

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/uav_object_detection_cpu \
  -H "Content-Type: application/json" \
  -d '{
    "destination": {
      "metadata": {"type": "file", "path": "/tmp/results.jsonl", "format": "json-lines"},
      "frame": {"type": "rtsp", "path": "uav-mavlink-cpu"}
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "CPU"
      }
    }
  }' | tr -d '"')
echo "Instance ID: $INSTANCE_ID"
```

**Example — check pipeline status:**

```bash
curl http://localhost:8081/pipelines/status | python3 -m json.tool
```

**Example — stop a running instance:**

```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```

---

## Verifying the Output Stream

### View with ffplay

```bash
# Install if needed
sudo apt install ffmpeg

# View the stream
ffplay rtsp://<host-ip>:8555/uav-mavlink-cpu
```

### Record a clip

```bash
ffmpeg -rtsp_transport tcp \
  -i "rtsp://<host-ip>:8555/uav-mavlink-cpu" \
  -c copy -t 30 output.mkv
```

---

## Stopping the Application

```bash
# Standalone mode
make pymav-down

# uav-mission-compute-sdk mode
make sdk-down
```

Both targets pass `-v` to also remove named Docker volumes (pipeline cache).

---

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for a complete list of known issues and resolutions, including:

- `make model` fails with `python3-venv` not available
- `make pymav-up` fails with pip network error (proxy issue)
- DL Streamer container keeps restarting
- No telemetry overlay on stream (all zeros)
- Pipelines not starting in uav-mission-compute-sdk mode
- `ffplay: command not found`
- NPU inference fails / GPU pipeline falls back to CPU
- QGroundControl network warnings
- PX4 SITL image issues
- UDP sink pipeline not working
- Benchmark: `jq`/`gawk` not found
