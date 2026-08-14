<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# UAV Vision Analytics Application

AI-powered drone object detection with live telemetry overlay, built on Intel DL Streamer Pipeline Server.

This application processes video from a drone-mounted camera (or simulated video file), runs YOLOv8n-VisDrone inference to detect objects in ten classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) directly on the video stream. The annotated output is served as RTSP on port `8555`, consumable by any RTSP-capable client.

---

## Quick Start

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
cp .env.example .env
# Set HOST_IP to the host machine's IP address
nano .env
```

### 2. Prepare the model

Download and export the YOLOv8n-VisDrone model to OpenVINO FP16 IR:

```bash
make model
```

> See [export_model.md](export_model.md) for full manual instructions and troubleshooting.

### 3a. Standalone mode (pymavlink)

```bash
make pymav-up
```

### 3b. MAVSDK mode (depends on uav-mission-compute-sdk)

Start the SDK project first, then start this application:

```bash
# In uav-mission-compute-sdk directory — starts PX4, MQTT, RTSP server
make up-sim-camera

# In this directory
make mavsdk-up
```

### 4. Start inference pipelines

Three options are available depending on your use case:

#### Option A — Managed RTSP output (recommended)

Runs `pipeline_manager.py` inside the DLSPS container. It monitors the drone's ARMED/DISARMED state and automatically starts and stops inference pipelines. Annotated frames are served as RTSP on port `8555`.

```bash
make start-rtsp
```

**RTSP output streams** (same paths for both pymavlink and MAVSDK modes):
```
rtsp://<HOST_IP>:8555/nadir      (nadir camera, CPU)
rtsp://<HOST_IP>:8555/forward    (forward camera, GPU)
rtsp://<HOST_IP>:8555/rear       (rear camera, NPU)
```

**MAVSDK mode** — full terminal output when the drone arms:
```
Vehicle Status: ARMED -> starting pipelines
[rtsp-check] Probing rtsp://host.docker.internal:8554/uav-1/nadir (attempt 1/3)...
[rtsp-check] rtsp://host.docker.internal:8554/uav-1/nadir is available.
[pipeline] Start 'nadir_camera_rtsp_cpu' status: 200

[rtsp-check] Probing rtsp://host.docker.internal:8554/uav-1/forward (attempt 1/3)...
[rtsp-check] rtsp://host.docker.internal:8554/uav-1/forward is available.
[pipeline] Start 'forward_camera_rtsp_gpu' status: 200

[rtsp-check] Probing rtsp://host.docker.internal:8554/uav-1/rear (attempt 1/3)...
[rtsp-check] rtsp://host.docker.internal:8554/uav-1/rear is available.
[pipeline] Start 'rear_camera_rtsp_npu' status: 200

RTSP streams available at:
  CPU: rtsp://localhost:8555/nadir
  GPU: rtsp://localhost:8555/forward
  NPU: rtsp://localhost:8555/rear
```

> `uav-1` is the default value of the `UAV_ID` environment variable in `.env`. The SDK's
> MediaMTX RTSP server publishes streams under `rtsp://…:8554/{UAV_ID}/{camera}`.
> Change `UAV_ID` in `.env` if your SDK project uses a different vehicle identifier.

#### Option B — Managed UDP output

Same pipeline manager as Option A, but routes annotated frames to UDP sink instead of RTSP. Useful for low-latency local consumption or integration with custom GStreamer receivers.

```bash
make start-udpsink
```

| Pipeline | Device | UDP Port |
|---|---|---|
| CPU | CPU | `5600` |
| GPU | GPU | `5601` |
| NPU | NPU | `5602` |

Receive a stream with GStreamer:
```bash
gst-launch-1.0 udpsrc port=5600 \
  caps="application/x-rtp,media=video,encoding-name=H264" \
  ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink
```

#### Option C — Manual REST API

Start a single pipeline directly without the pipeline manager. Useful for testing individual pipelines or custom configurations.

```bash
# Start CPU pipeline (pymavlink mode)
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
        "path": "uav-cpu"
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
```

For GPU or NPU, change the pipeline name and `device` value:

```bash
# GPU
curl -s -X POST http://localhost:8081/pipelines/user_defined_pipelines/uav_object_detection_gpu \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"detection-properties": {"model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml", "device": "GPU"}}, "destination": {"frame": {"type": "rtsp", "path": "uav-gpu"}}}'

# NPU
curl -s -X POST http://localhost:8081/pipelines/user_defined_pipelines/uav_object_detection_npu \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"detection-properties": {"model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml", "device": "NPU"}}, "destination": {"frame": {"type": "rtsp", "path": "drone-npu"}}}'
```

Stop a pipeline:
```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```

### 5. View the output stream

```bash
# View annotated RTSP output (install ffmpeg first if not present)
ffplay rtsp://<HOST_IP>:8555/nadir      # nadir camera (CPU)
ffplay rtsp://<HOST_IP>:8555/forward    # forward camera (GPU)
ffplay rtsp://<HOST_IP>:8555/rear       # rear camera (NPU)
```

Or open the URL in QGroundControl: **Application Settings → Video**.

The annotated stream includes bounding boxes for detected objects (person, car, bus, truck, van, bicycle, tricycle, awning-tricycle, motor, others) and a live telemetry overlay (GPS, altitude, speed, heading).

---

## Pipelines

### pymavlink mode (`config-pymavlink.json`)

| Pipeline | Device | Source | Output |
|---|---|---|---|
| `uav_object_detection_cpu` | CPU | Looped video file (`gazebo.avi`) | RTSP `:8555` |
| `uav_object_detection_gpu` | GPU | Looped video file (`gazebo.avi`) | RTSP `:8555` |
| `uav_object_detection_npu` | NPU | Looped video file (`gazebo.avi`) | RTSP `:8555` |
| `uav_realsense_cpu` | CPU | Intel RealSense camera (v4l2src) | RTSP `:8555` |
| `uav_realsense_gpu` | GPU | Intel RealSense camera (v4l2src) | RTSP `:8555` |
| `uav_realsense_npu` | NPU | Intel RealSense camera (v4l2src) | RTSP `:8555` |
| `nadir_camera_rtsp_cpu` | CPU | `rtsp://…:8554/{UAV_ID}/nadir` | `rtsp://<HOST_IP>:8555/nadir` |
| `forward_camera_rtsp_gpu` | GPU | `rtsp://…:8554/{UAV_ID}/forward` | `rtsp://<HOST_IP>:8555/forward` |
| `rear_camera_rtsp_npu` | NPU | `rtsp://…:8554/{UAV_ID}/rear` | `rtsp://<HOST_IP>:8555/rear` |
| `uav_udpsink_cpu` | CPU | Looped video file (`gazebo.avi`) | UDP `:5600` |
| `uav_udpsink_gpu` | GPU | Looped video file (`gazebo.avi`) | UDP `:5601` |
| `uav_udpsink_npu` | NPU | Looped video file (`gazebo.avi`) | UDP `:5602` |

### MAVSDK mode (`config-mavsdk.json`)

| Pipeline | Device | Source (inside Docker) | Output RTSP (host) |
|---|---|---|---|
| `nadir_camera_rtsp_cpu` | CPU | `rtsp://host.docker.internal:8554/uav-1/nadir` | `rtsp://<HOST_IP>:8555/nadir` |
| `forward_camera_rtsp_gpu` | GPU | `rtsp://host.docker.internal:8554/uav-1/forward` | `rtsp://<HOST_IP>:8555/forward` |
| `rear_camera_rtsp_npu` | NPU | `rtsp://host.docker.internal:8554/uav-1/rear` | `rtsp://<HOST_IP>:8555/rear` |

> `uav-1` in the source URL is the value of the `UAV_ID` environment variable (default: `uav-1`).
> Set a different value in `.env` if your SDK project uses a different vehicle ID.

All pipelines are `auto_start: false` — started explicitly via the pipeline managers (`make start-rtsp` / `make start-udpsink`) or the REST API directly.

REST endpoint: `POST http://localhost:8081/pipelines/user_defined_pipelines/{name}`

---

## Telemetry Overlay Fields

Each output frame carries these overlaid fields in the upper-left corner:

| Field | Source MAVLink message | Description |
|---|---|---|
| `Protocol` | — | `pymavlink` or `MQTT` |
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
| `1883` | TCP | Mosquitto MQTT broker | pymavlink modes |
| `14541` | UDP | MAVLink broadcast (mavlink-router) | pymavlink modes |
| `9090` | HTTP | metrics-manager (HW metrics) | pymavlink modes |
| `5600` | UDP | CPU pipeline UDP sink output | pymavlink (`make start-udpsink`) |
| `5601` | UDP | GPU pipeline UDP sink output | pymavlink (`make start-udpsink`) |
| `5602` | UDP | NPU pipeline UDP sink output | pymavlink (`make start-udpsink`) |
| `8554` | RTSP | SDK camera source streams | MAVSDK mode |
| `8889` | HTTP/WebRTC | MediaMTX WebRTC signaling | MAVSDK only |
| `3478` | UDP | coturn TURN/STUN relay | MAVSDK only |

---

## Documentation

| Document | Description |
|---|---|
| [overview.md](overview.md) | Architecture overview and component block diagrams |
| [user-guide.md](user-guide.md) | Full deployment, configuration, architecture, and design guide |
| [export_model.md](export_model.md) | Model download and OpenVINO export instructions |
| [mavsdk-guide.md](mavsdk-guide.md) | End-to-end MAVSDK mode walkthrough |
| [realsense-guide.md](realsense-guide.md) | Intel RealSense camera setup and pipelines |
| [benchmark.md](benchmark.md) | Performance benchmarking guide (`calc_stream_density.sh`) |
| [makefile.md](makefile.md) | Makefile target reference |
| [troubleshooting.md](troubleshooting.md) | Known issues and resolutions |

---

## Notices and Disclaimers

**Notice for GStreamer:**
GStreamer is an open source framework licensed under LGPL. See https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html. You are solely responsible for determining if your use of GStreamer requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of GStreamer.

**Notice for FFmpeg:**
FFmpeg is an open source project licensed under LGPL and GPL. See https://www.ffmpeg.org/legal.html. You are solely responsible for determining if your use of FFmpeg requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of FFmpeg.
