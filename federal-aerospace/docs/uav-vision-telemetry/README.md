<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Drone Vision Telemetry

AI-powered drone object detection with live telemetry overlay, built on Intel DL Streamer Pipeline Server.

This application processes video from a drone-mounted camera (or simulated RTSP feed), runs YOLOv8n-VisDrone inference to detect objects in eight classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) directly on the video stream. The annotated output is served as RTSP and WebRTC, making it consumable by QGroundControl (QGC) or any RTSP-capable client.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Intel platform with at least 16 GB RAM (Panther Lake recommended)
- Network access to pull Docker images
- YOLOv8n-VisDrone model exported to OpenVINO FP16 (see [export_model.md](export_model.md))

### 1. Configure environment

```bash
cp .env.example .env
# Set HOST_IP to the host machine's IP address
nano .env
```

### 2. Prepare the model

Download and export the YOLOv8n-VisDrone model to `resources/models/yolov8n-visdrone/best_openvino_model/`:

```bash
# Full instructions in export_model.md
cd resources
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
hf download mshamrai/yolov8n-visdrone best.pt --local-dir ./yolov8n-visdrone
yolo export model=./models/yolov8n-visdrone/best.pt format=openvino dynamic=True imgsz=640 quantize=16
```

### 3a. Standalone mode (pymavlink)


```bash
docker compose -f docker-compose-pymavlink.yml up -d
```

### 3b. MAVSDK mode (depends on fedaero-drone-sdk-poc)

Start the SDK project first, then start this application:

```bash
# In fedaero-drone-sdk-poc directory
make up

# In this directory
docker compose -f docker-compose-mavsdk.yml up -d
```

### 4. Start an inference pipeline

Use the REST API to start the desired pipeline (CPU / GPU / NPU):

```bash
# CPU pipeline — pymavlink mode
curl -X POST http://localhost:8081/pipelines/drone_object_detection_cpu \
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
            "path": "drone-mavlink-cpu"
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
            "device": "CPU"
        }
    }
}'
```

The annotated RTSP stream is then available at:
- `rtsp://<host-ip>:8555/drone-detect-cpu`

---


## Pipelines

Three pipelines are registered, all running YOLOv8n-VisDrone at 640×640 FP16:

| Pipeline | Inference device | REST path |
|---|---|---|
| `drone_object_detection_cpu` | CPU | `/pipelines/drone_object_detection_cpu` |
| `drone_object_detection_gpu` | GPU | `/pipelines/drone_object_detection_gpu` |
| `drone_object_detection_npu` | NPU | `/pipelines/drone_object_detection_npu` |

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

## Documentation

| Document | Description |
|---|---|
| [overview.md](overview.md) | Architecture overview and component block diagrams |
| [user-guide.md](user-guide.md) | Full deployment, configuration, architecture, and design guide |
| [export_model.md](export_model.md) | Model download and OpenVINO export instructions |

---

## Notices and Disclaimers

**Notice for GStreamer:**
GStreamer is an open source framework licensed under LGPL. See https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html. You are solely responsible for determining if your use of GStreamer requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of GStreamer.

**Notice for FFmpeg:**
FFmpeg is an open source project licensed under LGPL and GPL. See https://www.ffmpeg.org/legal.html. You are solely responsible for determining if your use of FFmpeg requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of FFmpeg.
