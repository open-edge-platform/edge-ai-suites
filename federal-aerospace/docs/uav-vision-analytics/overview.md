<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# UAV Vision Analytics — Overview

This application demonstrates AI-based object detection integrated with drone flight controller telemetry on a companion compute platform. Telemetry data (GPS, altitude, speed, heading) is correlated with AI inference results and rendered as an on-screen overlay in near real-time, producing a watermarked RTSP video stream consumable by ground control software such as QGroundControl (QGC).

---

## Deployment Modes

The application supports two deployment modes that differ in how telemetry is sourced.

### Mode 1 — Standalone / pymavlink (`docker-compose-pymavlink.yml`)

A self-contained stack. PX4 SITL, MAVLink router, MQTT broker, and Metrics Manager are all started together. Telemetry flows from PX4 SITL through `mavlink-router` to the DL Streamer container, where `pymavlink` reads it directly over UDP.

```mermaid
flowchart LR
    subgraph Stack["docker-compose-pymavlink.yml"]
        direction TB
        PX4["PX4 SITL\npx4io/px4-sitl"]
        ROUTER["mavlink-router\n(:14550 server\n→ :14541 broadcast)"]
        BROKER["Eclipse Mosquitto\nMQTT :1883"]
        DLSPS["DL Streamer\nPipeline Server\n(REST :8081 · RTSP :8555)"]
        MM["Metrics Manager\n(REST :9090)"]

        PX4 -->|"MAVLink"| ROUTER
        ROUTER -->|"UDP :14541"| DLSPS
        DLSPS -.->|"inference metrics"| BROKER
    end

    VIDEO["Video Source\n(Camera / file)"] -->|"video"| DLSPS
    DLSPS -->|"RTSP :8555"| CLIENT["QGC / ffplay"]
```

**Telemetry flow:**

```mermaid
sequenceDiagram
    participant PX4 as PX4 SITL
    participant RTR as mavlink-router
    participant OVL as gvapython (MavlinkReceiver)
    participant Frame as Video Frame

    PX4->>RTR: MAVLink stream (UDP :14550)
    RTR->>OVL: broadcast UDP :14541
    Note over OVL: background thread parses<br/>GLOBAL_POSITION_INT, VFR_HUD,<br/>GPS_RAW_INT into latest_data
    Frame->>OVL: process_frame() per frame
    OVL->>Frame: ROI labels (ALT · SPD · HDG · LAT · LON · SATS)
```

**Services:**

| Service | Image | Ports | Role |
|---|---|---|---|
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server` + pymavlink | `8081`, `8555` | AI inference, RTSP output |
| `broker` | `eclipse-mosquitto:2.0.22` | `1883` | MQTT broker |
| `px4` | `px4io/px4-sitl` | — | Flight controller simulator |
| `mavlink-router` | custom build | — | MAVLink UDP routing (:14550 → :14541) |
| `metrics-manager` | `intel/metrics-manager` | — | CPU/GPU/NPU/power metrics |

---

### Mode 1b — Standalone / pymavlink + WebRTC (`docker-compose-pymavlink-mediamtx.yml`)

Extends Mode 1 with a **WebRTC streaming path** alongside RTSP. MediaMTX acts as the WebRTC signaling server and coturn provides a TURN relay for NAT traversal. Clients can view the annotated video in a browser without a dedicated RTSP player.

```mermaid
flowchart LR
    subgraph Stack["docker-compose-pymavlink-mediamtx.yml"]
        direction TB
        PX4["PX4 SITL\npx4io/px4-sitl"]
        ROUTER["mavlink-router\n(:14550 server\n→ :14541 broadcast)"]
        BROKER["Eclipse Mosquitto\nMQTT :1883"]
        DLSPS["DL Streamer\nPipeline Server\n(REST :8081 · RTSP :8555 · WebRTC)"]
        MTX["MediaMTX\nWebRTC signaling :8889"]
        COTURN["coturn\nTURN/STUN :3478/udp"]
        MM["Metrics Manager\n(REST :9090)"]

        PX4 -->|"MAVLink"| ROUTER
        ROUTER -->|"UDP :14541"| DLSPS
        DLSPS -->|"WebRTC signaling"| MTX
        MTX -->|"ICE/TURN"| COTURN
        DLSPS -.->|"inference metrics"| BROKER
    end

    VIDEO["Video Source\n(Camera / file)"] -->|"video"| DLSPS
    DLSPS -->|"RTSP :8555"| CLIENT_RTSP["QGC / ffplay"]
    MTX -->|"WebRTC via :8889"| CLIENT_WEB["Browser"]
```

**WebRTC path:** DLSPS publishes the annotated video to MediaMTX over the WebRTC signaling endpoint (`http://mediamtx-server:8889`). Browsers connect to MediaMTX at `:8889`; coturn handles ICE relay for clients behind NAT using credentials set via `MTX_WEBRTCICESERVERS2_0_USERNAME` / `MTX_WEBRTCICESERVERS2_0_PASSWORD`.

**Services:**

| Service | Image | Ports | Role |
|---|---|---|---|
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server` + pymavlink | `8081`, `8555` | AI inference, RTSP + WebRTC output |
| `broker` | `eclipse-mosquitto:2.0.22` | `1883` | MQTT broker |
| `px4` | `px4io/px4-sitl` | — | Flight controller simulator |
| `mavlink-router` | custom build | — | MAVLink UDP routing (:14550 → :14541) |
| `mediamtx` | `bluenviron/mediamtx:1.11.3` | `8889` | WebRTC signaling server |
| `coturn` | `coturn/coturn:4.12.0` | `3478/udp` | TURN/STUN relay for WebRTC NAT traversal |
| `metrics-manager` | `intel/metrics-manager` | — | CPU/GPU/NPU/power metrics |

---

### Mode 2 — MAVSDK / external SDK (`docker-compose-mavsdk.yml`)

A minimal single-container stack. Telemetry is received via MQTT from the `uav-mission-compute-sdk` project, which must be started first. The DLSPS container reads armed/disarmed state from `uav/{id}/telemetry/status` and subscribes to three RTSP camera streams (nadir, forward, rear).

```mermaid
flowchart LR
    subgraph SDK["uav-mission-compute-sdk (started separately)"]
        direction TB
        PX4E["PX4 + Gazebo"]
        BRIDGE["companion-bridge\nMAVLink → MQTT"]
        BROKER_E["MQTT Broker :1884"]
        MEDIAMTX["MediaMTX\nRTSP :8554"]

        PX4E -->|"MAVLink"| BRIDGE
        BRIDGE -->|"uav/uav-1/telemetry/status\nuav/uav-1/camera/*/detections"| BROKER_E
        PX4E -->|"camera frames"| MEDIAMTX
    end

    subgraph Stack["docker-compose-mavsdk.yml"]
        DLSPS2["DL Streamer\nPipeline Server\n(REST :8081 · RTSP :8555)"]
    end

    BROKER_E -->|"MQTT armed state"| DLSPS2
    MEDIAMTX -->|"RTSP nadir/forward/rear"| DLSPS2
    DLSPS2 -->|"RTSP :8555"| CLIENT2["QGC / ffplay"]
```

**Telemetry / pipeline lifecycle flow:**

```mermaid
sequenceDiagram
    participant SDK as uav-mission-compute-sdk
    participant BROKER as MQTT Broker (:1884)
    participant PM as mavsdk_pipeline_manager
    participant DLSPS as DL Streamer REST API

    SDK->>BROKER: uav/uav-1/telemetry/status {armed: true}
    BROKER->>PM: on_message callback
    PM->>PM: wait_for_rtsp_stream() probe nadir/forward/rear
    PM->>DLSPS: POST /pipelines/user_defined_pipelines/nadir_camera_rtsp_cpu
    PM->>DLSPS: POST /pipelines/user_defined_pipelines/forward_camera_rtsp_gpu
    PM->>DLSPS: POST /pipelines/user_defined_pipelines/rear_camera_rtsp_npu
    Note over DLSPS: Inference running,<br/>annotated RTSP at :8555
    SDK->>BROKER: uav/uav-1/telemetry/status {armed: false}
    BROKER->>PM: on_message callback
    PM->>DLSPS: DELETE /pipelines/{instance_id} × 3
```

**Services:**

| Service | Image | Ports | Role |
|---|---|---|---|
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server` | `8081`, `8555` | AI inference, RTSP output |

---

## GStreamer Pipeline

All pipelines follow the same element chain (device and source vary per pipeline):

```mermaid
flowchart LR
    SRC["rtspsrc / multifilesrc"]
    DEC["h264parse\ndecodebin3"]
    CONV["videoconvert\nNV12 416×416"]
    DET["gvadetect\nOpenVINO device=CPU|GPU|NPU\nmodel-instance-id per device"]
    OVL["gvapython\nDrawDynamicText\ntelemetry overlay"]
    META["gvametaconvert\ngvametapublish → MQTT"]
    SINK["appsink → RTSP :8555"]

    SRC --> DEC --> CONV --> DET --> OVL --> META --> SINK
```

### pymavlink pipelines (`config-pymavlink.json`)

| Pipeline | Device | Source |
|---|---|---|
| `drone_object_detection_cpu` | CPU | `multifilesrc` (loop file) |
| `drone_object_detection_gpu` | GPU | `multifilesrc` (loop file) |
| `drone_object_detection_npu` | NPU | `multifilesrc` (loop file) |
| `drone_realsense_cpu` | CPU | RealSense (`v4l2src`) |
| `drone_realsense_gpu` | GPU | RealSense (`v4l2src`) |
| `drone_realsense_npu` | NPU | RealSense (`v4l2src`) |
| `drone_udpsink_cpu` | CPU | `multifilesrc` → UDP sink |
| `drone_udpsink_gpu` | GPU | `multifilesrc` → UDP sink |
| `drone_udpsink_npu` | NPU | `multifilesrc` → UDP sink |

### MAVSDK pipelines (`config-mavsdk.json`)

| Pipeline | Device | Source RTSP |
|---|---|---|
| `nadir_camera_rtsp_cpu` | CPU | `rtsp://host.docker.internal:8554/uav-1/nadir` |
| `forward_camera_rtsp_gpu` | GPU | `rtsp://host.docker.internal:8554/uav-1/forward` |
| `rear_camera_rtsp_npu` | NPU | `rtsp://host.docker.internal:8554/uav-1/rear` |

---

## AI Model

| Property | Value |
|---|---|
| Model | YOLOv8n-VisDrone |
| Source | [mshamrai/yolov8n-visdrone](https://huggingface.co/mshamrai/yolov8n-visdrone) |
| Precision | FP16 (OpenVINO IR) |
| Input resolution | 640 × 640 |
| Detection classes | pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor |
| Ultralytics version | 8.4.67 (pinned — see `resources/requirements.txt`) |

See [export_model.md](export_model.md) for download and export instructions.

---

## Port Reference

| Port | Protocol | Service | Mode |
|---|---|---|---|
| `8081` | HTTP | DL Streamer REST API | All modes |
| `8555` | RTSP | Annotated video output | All modes |
| `1883` | TCP | Mosquitto MQTT broker | pymavlink modes only |
| `14541` | UDP | MAVLink broadcast (mavlink-router) | pymavlink modes only |
| `8889` | HTTP/WebRTC | MediaMTX WebRTC signaling | Mode 1b only |
| `3478` | UDP | coturn TURN/STUN relay | Mode 1b only |

---

## Related Documentation

| Document | Description |
|---|---|
| [README.md](README.md) | Quick-start guide |
| [user-guide.md](user-guide.md) | Deployment, configuration, architecture, and design |
| [export_model.md](export_model.md) | Downloading and exporting the YOLOv8n-VisDrone model |
| [mavsdk-guide.md](mavsdk-guide.md) | End-to-end MAVSDK mode walkthrough |
| [realsense-guide.md](realsense-guide.md) | Intel RealSense camera setup and pipelines |
| [benchmark.md](benchmark.md) | Performance benchmarking guide |
| [makefile.md](makefile.md) | Makefile target reference |
| [troubleshooting.md](troubleshooting.md) | Known issues and resolutions |
