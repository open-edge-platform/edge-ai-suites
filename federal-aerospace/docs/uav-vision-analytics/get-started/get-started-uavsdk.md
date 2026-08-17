<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->


# Get Started (UAV Mission Compute SDK Mode)

This guide provides a step-by-step walkthrough for testing the UAV Vision Analytics application in UAV Mission Compute SDK mode and running the demo with a simulated UAV camera feed/RealSense cameras.

## How It Works

A minimal single-container stack. Telemetry is received via MQTT from the `uav-mission-compute-sdk` project, which must be started first. The DLSPS container reads armed/disarmed state from `uav/{id}/telemetry/status` and subscribes to three RTSP camera streams (nadir, forward, rear).

![uav vision analytics sdk](../_assets/FedAero-uav-vision-uavsdk.drawio.svg)


**Telemetry / pipeline lifecycle flow:**

```mermaid
sequenceDiagram
    participant SDK as uav-mission-compute-sdk
    participant OVL as gvapython (MavlinkReceiver)
    participant Frame as Video Frame

    SDK->>OVL: broadcast MQTT Telemetry :1883
    Note over OVL: background thread parses<br/>GLOBAL_POSITION_INT, VFR_HUD,<br/>GPS_RAW_INT into latest_data
    Frame->>OVL: process_frame() per frame
    OVL->>Frame: ROI labels (ALT · SPD · HDG · LAT · LON · SATS)
```

**Services:**

| Service | Image | Ports | Role |
|---|---|---|---|
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server` | `8081`, `8555` | AI inference, RTSP output |

---

## Steps to Test the Application

### Prerequisites

- Docker and Docker Compose v2
- Intel platform with at least 16 GB RAM (Panther Lake recommended)
- Network access to pull Docker images (configure proxy if behind a corporate firewall)
- The following system packages:

```bash
sudo apt install -y python3.12-venv ffmpeg
```

> `python3.12-venv` is required by `make model` to create a Python virtual environment.
> `ffmpeg` provides `ffplay` for viewing the RTSP output stream and `ffmpeg` for recording.

### 1. Configure environment

```bash
make init
```

`make init` creates `.env` from the template and **auto-detects your Intel GPU** device paths (`GPU_DEVICE`, `GPU_RENDER_DEVICE`). It skips silently if `.env` already exists.

Then set your host IP address in `.env`:

```bash
nano .env   # set HOST_IP=<your-machine-IP>
```

### 2. Prepare the model

Download and export the YOLOv8n-VisDrone model to OpenVINO FP16 IR:

```bash
make model
```

> See the [AI Model guide](../how-to-guides/model.md) for model details.

### 3. Start the UAV Mission Compute SDK (depends on uav-mission-compute-sdk)

Follow the setup instructions in the [README](../../../uav-mission-compute-sdk/README.md) before proceeding.

```bash
cd edge-ai-suites/federal-aerospace/uav-mission-compute-sdk
# In uav-mission-compute-sdk directory — starts PX4, MQTT, RTSP server
make up-sim-camera
```

### 4. Start the UAV Mission Compute SDK (depends on uav-mission-compute-sdk)

Start the SDK project first, then start this application:

```bash
cd edge-ai-suites/federal-aerospace/apps/uav-vision-analytics
make uavsdk-up
```

### 5. Run a simple mission

> **Note:** Video streams are not available until the UAV is armed and actively on a mission.

The following sequence arms the UAV, commands a takeoff to 10 m, holds for 120 seconds, then lands:

```bash
curl -X POST http://localhost:8080/action/arm
curl -sf -X POST http://localhost:8080/action/takeoff \
  -H "Content-Type: application/json" \
  -d '{"altitude": 10}'
sleep 120
curl -X POST http://localhost:8080/action/land
```

### 6. Start inference pipelines

Three options are available depending on your use case:

#### Option A — Managed RTSP output (recommended)

Runs `pipeline_manager.py` inside the DLSPS container. It monitors the drone's ARMED/DISARMED state and automatically starts and stops inference pipelines. Annotated frames are served as RTSP on port `8555`.

```bash
make start-rtsp
```

**uav-mission-compute-sdk mode** — output streams (available after drone arms):
```
rtsp://<HOST_IP>:8555/nadir      (nadir camera, CPU)
rtsp://<HOST_IP>:8555/forward    (forward camera, GPU)
rtsp://<HOST_IP>:8555/rear       (rear camera, NPU)
```

#### Option B — Manual REST API

> **Note:** RTSP streams are not available until the UAV is armed. Run a simple mission first (see [Step 5: Run a simple mission](#5-run-a-simple-mission)).

Start a single camera pipeline directly. The UAVSDK mode loads `config-uavsdk.json` which defines the three camera-source pipelines (`nadir_camera_rtsp_cpu`, `forward_camera_rtsp_gpu`, `rear_camera_rtsp_npu`).

Once the source is confirmed live, start the pipeline:

```bash
# Start CPU pipeline (uav-mission-compute-sdk mode)
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/nadir_camera_rtsp_cpu \
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
        "path": "nadir"
      }
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "CPU"
      }
    }
  }' | tr -d '"')
echo "Instance ID: $INSTANCE_ID"

# Verify it reached RUNNING state (not ERROR)
curl -s http://localhost:8081/pipelines/${INSTANCE_ID}/status | python3 -m json.tool
```

If `state` is `ERROR`, check the container logs:
```bash
docker logs dlstreamer-pipeline-server 2>&1 | tail -20
```

Stop a pipeline:
```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```

### 6. View the output stream

#### View with ffplay

```bash
# View annotated RTSP output (install ffmpeg first if not present)
ffplay rtsp://<HOST_IP>:8555/nadir               # uav-mission-compute-sdk mode, nadir camera
```

#### Capture all the video streams
Record all three streams to disk with `ffmpeg`:

```bash
ffmpeg \
  -rtsp_transport tcp -i rtsp://localhost:8555/nadir \
  -rtsp_transport tcp -i rtsp://localhost:8555/forward \
  -rtsp_transport tcp -i rtsp://localhost:8555/rear \
  -map 0:v -c:v copy nadir.mkv \
  -map 1:v -c:v copy forward.mkv \
  -map 2:v -c:v copy rear.mkv
```

The annotated stream includes bounding boxes for detected objects (person, car, bus, truck, van, bicycle, tricycle, awning-tricycle, motor, others) and a live telemetry overlay (GPS, altitude, speed, heading).

---

## Pipelines

### UAV Mission Compute SDK Mode (`config-uavsdk.json`)

| Pipeline | Device | Source (inside Docker) | Output RTSP (host) |
|---|---|---|---|
| `nadir_camera_rtsp_cpu` | CPU | `rtsp://host.docker.internal:8554/uav-1/nadir` | `rtsp://<HOST_IP>:8555/nadir` |
| `forward_camera_rtsp_gpu` | GPU | `rtsp://host.docker.internal:8554/uav-1/forward` | `rtsp://<HOST_IP>:8555/forward` |
| `rear_camera_rtsp_npu` | NPU | `rtsp://host.docker.internal:8554/uav-1/rear` | `rtsp://<HOST_IP>:8555/rear` |

> `uav-1` in the source URL is the value of the `UAV_ID` environment variable (default: `uav-1`).
> Set a different value in `.env` if your SDK project uses a different vehicle ID.
> Also update the RTSP input URLs in `config-uavsdk.json` if you change the UAV ID.

All pipelines are `auto_start: false` — started explicitly via the pipeline managers (`make start-rtsp`) or the REST API directly.

REST endpoint: `POST http://localhost:8081/pipelines/user_defined_pipelines/{name}`

---

## Telemetry Overlay Fields

Each output frame carries these overlaid fields in the upper-left corner:

| Field | Source MAVLink message | Description |
|---|---|---|
| `Name` | — | Name passed as argument to the gvapython |
| `Frame` | — | Running frame counter |
| `ALT` | `GLOBAL_POSITION_INT.relative_alt` | Relative altitude (m) |
| `SPD` | `VFR_HUD.groundspeed` | Ground speed (m/s) |
| `HDG` | `GLOBAL_POSITION_INT.hdg` | Heading (degrees) |
| `LAT` | `GPS_RAW_INT.lat` | Latitude |
| `LON` | `GPS_RAW_INT.lon` | Longitude |
| `SATS` | `GPS_RAW_INT.satellites_visible` | GPS satellites visible |

---

## Port Reference

| Port | Protocol | Service | Mode |
|---|---|---|---|
| `8081` | HTTP | DL Streamer REST API | All modes |
| `8555` | RTSP | Annotated video output | All modes |

---

## Documentation

| Document | Description |
|---|---|
| [index.md](../index.md) | Application overview and component block diagrams |
| [realsense-guide.md](../how-to-guides/realsense-guide.md) | Intel RealSense camera setup and pipelines |
| [benchmark.md](../how-to-guides/benchmark.md) | Performance benchmarking guide (`calc_stream_density.sh`) |
| [makefile.md](../how-to-guides/makefile.md) | Makefile target reference |
| [troubleshooting.md](../how-to-guides/troubleshooting.md) | Known issues and resolutions |

