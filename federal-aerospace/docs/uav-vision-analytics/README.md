<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# UAV Vision Analytics Application

AI-powered drone object detection with live telemetry overlay, built on Intel DL Streamer Pipeline Server.

This application processes video from a drone-mounted camera (or simulated RTSP feed), runs YOLOv8n-VisDrone inference to detect objects in ten classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) directly on the video stream. The annotated output is served as RTSP on port `8555`, consumable by QGroundControl (QGC) or any RTSP-capable client.

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
make model
```

See [export_model.md](export_model.md) for manual step-by-step instructions.

### 3a. Standalone mode (pymavlink)

```bash
make pymav-up
```

### 3b. MAVSDK mode (depends on uav-mission-compute-sdk)

Start the SDK project first, then start this application:

```bash
# In uav-mission-compute-sdk directory
make up

# In this directory
make mavsdk-up
```

### 4. Start an inference pipeline

Use the REST API to start the desired pipeline (CPU / GPU / NPU). The response body is the
integer `instance_id` — save it to stop the pipeline later:

```bash
# CPU pipeline — pymavlink mode
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/drone_object_detection_cpu \
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
            "path": "drone-cpu"
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

To stop the pipeline:

```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```

The annotated RTSP stream is then available at:
- `rtsp://<host-ip>:8555/drone-cpu`

---


## Pipelines

### pymavlink mode (`config-pymavlink.json`)

| Pipeline | Device | Source |
|---|---|---|
| `drone_object_detection_cpu` | CPU | Looped video file |
| `drone_object_detection_gpu` | GPU | Looped video file |
| `drone_object_detection_npu` | NPU | Looped video file |
| `drone_realsense_cpu` | CPU | RealSense camera |
| `drone_realsense_gpu` | GPU | RealSense camera |
| `drone_realsense_npu` | NPU | RealSense camera |
| `drone_udpsink_cpu` | CPU | Looped video → UDP sink |
| `drone_udpsink_gpu` | GPU | Looped video → UDP sink |
| `drone_udpsink_npu` | NPU | Looped video → UDP sink |

### MAVSDK mode (`config-mavsdk.json`)

| Pipeline | Device | Source RTSP |
|---|---|---|
| `nadir_camera_rtsp_cpu` | CPU | `rtsp://…:8554/uav-1/nadir` |
| `forward_camera_rtsp_gpu` | GPU | `rtsp://…:8554/uav-1/forward` |
| `rear_camera_rtsp_npu` | NPU | `rtsp://…:8554/uav-1/rear` |

All pipelines are `auto_start: false` — started explicitly via the REST API or pipeline managers.

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

## Documentation

| Document | Description |
|---|---|
| [overview.md](overview.md) | Architecture overview and component block diagrams |
| [user-guide.md](user-guide.md) | Full deployment, configuration, architecture, and design guide |
| [export_model.md](export_model.md) | Model download and OpenVINO export instructions |
| [mavsdk-guide.md](mavsdk-guide.md) | End-to-end MAVSDK mode walkthrough |
| [realsense-guide.md](realsense-guide.md) | Intel RealSense camera setup and pipelines |
| [benchmark.md](benchmark.md) | Performance benchmarking guide |
| [makefile.md](makefile.md) | Makefile target reference |
| [troubleshooting.md](troubleshooting.md) | Known issues and resolutions |

---

## Notices and Disclaimers

**Notice for GStreamer:**
GStreamer is an open source framework licensed under LGPL. See https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html. You are solely responsible for determining if your use of GStreamer requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of GStreamer.

**Notice for FFmpeg:**
FFmpeg is an open source project licensed under LGPL and GPL. See https://www.ffmpeg.org/legal.html. You are solely responsible for determining if your use of FFmpeg requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of FFmpeg.
