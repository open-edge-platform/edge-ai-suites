<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Drone Vision Telemetry — Overview

This application demonstrates AI-based object detection integrated with drone flight controller telemetry on a companion compute platform. Telemetry data (GPS, altitude, speed, heading) is correlated with AI inference results and rendered as an on-screen overlay in near real-time, producing a watermarked RTSP/WebRTC video stream consumable by ground control software such as QGroundControl (QGC).

---

## Deployment Modes

The application supports two deployment modes that differ in how telemetry is sourced and which supporting services are included.

### Mode 1 — Standalone with pymavlink (`docker-compose-pymavlink.yml`)

A fully self-contained stack. All services—including the PX4 SITL simulator, MQTT broker, and media relay—are started together. The `gvapython` telemetry overlay subscribes directly to the PX4 SITL via MAVLink UDP on port `14550`.

```mermaid
flowchart LR
    subgraph Standalone["docker-compose-pymavlink.yml"]
        direction TB

        PX4["PX4 SITL\n(px4io/px4-sitl)"]
        BROKER["MQTT Broker\n(Eclipse Mosquitto :1883)"]
        DLSPS["DL Streamer\nPipeline Server\n(:8080 REST, :8554 RTSP)"]
        MTX["MediaMTX\n(:8889 WebRTC)"]
        TURN["coturn\n(:3478 TURN)"]
        MM["Metrics Manager"]

        PX4 -->|"MAVLink UDP :14550"| DLSPS
        DLSPS -->|"appsink frames"| MTX
        MTX -->|"ICE relay"| TURN
        DLSPS -.->|"telemetry metrics"| BROKER
        MM -.->|"system metrics"| BROKER
    end

    VIDEO["Video Source\n(RTSP / Camera)"] -->|"RTSP"| DLSPS
    CLIENT["QGC / Browser"] -->|"RTSP :8554"| DLSPS
    CLIENT -->|"WebRTC :8889"| MTX
```

**Telemetry flow (pymavlink):**

```mermaid
sequenceDiagram
    participant PX4 as PX4 SITL
    participant OVL as gvapython overlay
    participant Frame as Video Frame

    PX4->>OVL: MAVLink GLOBAL_POSITION_INT (UDP :14550)
    PX4->>OVL: MAVLink VFR_HUD
    PX4->>OVL: MAVLink GPS_RAW_INT
    Note over OVL: MavlinkReceiver thread<br/>updates latest_data dict
    Frame->>OVL: process_frame() called per frame
    OVL->>Frame: adds ROI labels (ALT, SPD, HDG, LAT, LON, SATS)
```

---

### Mode 2 — MAVSDK / External Stack (`docker-compose-mavsdk.yml`)

A minimal stack that integrates with the `fedaero-drone-sdk-poc` project, which must be running first. Telemetry is received via MQTT topics published by the companion bridge in the SDK project. This mode maps DL Streamer to different host ports (`8081`, `8555`) to avoid conflicts.

```mermaid
flowchart LR
    subgraph External["fedaero-drone-sdk-poc (running separately)"]
        direction TB
        PX4_EXT["PX4 + Gazebo\nSITL Simulation"]
        BRIDGE["companion-bridge\n(MAVLink → MQTT)"]
        BROKER_EXT["MQTT Broker\n(:1884)"]

        PX4_EXT -->|"MAVLink"| BRIDGE
        BRIDGE -->|"mavlink/GLOBAL_POSITION_INT\nmavlink/VFR_HUD\nmavlink/GPS_RAW_INT"| BROKER_EXT
    end

    subgraph MAVSDK["docker-compose-mavsdk.yml"]
        direction TB
        DLSPS2["DL Streamer\nPipeline Server\n(:8081 REST, :8555 RTSP)"]
        TURN2["coturn\n(:3478 TURN)"]
        DLSPS2 -.-> TURN2
    end

    BROKER_EXT -->|"MQTT telemetry"| DLSPS2
    VIDEO2["Video Source\n(RTSP from SDK)"] -->|"RTSP"| DLSPS2
    CLIENT2["QGC / Browser"] -->|"RTSP :8555"| DLSPS2
```

**Telemetry flow (MAVSDK / MQTT):**

```mermaid
sequenceDiagram
    participant BRIDGE as companion-bridge
    participant BROKER as MQTT Broker
    participant OVL as gvapython overlay (MqttReceiver)
    participant Frame as Video Frame

    BRIDGE->>BROKER: publish mavlink/GLOBAL_POSITION_INT
    BRIDGE->>BROKER: publish mavlink/VFR_HUD
    BRIDGE->>BROKER: publish mavlink/GPS_RAW_INT
    BROKER->>OVL: on_message callback
    Note over OVL: updates latest_data dict<br/>thread-safe via lock
    Frame->>OVL: process_frame() called per frame
    OVL->>Frame: adds ROI labels (ALT, SPD, HDG, LAT, LON, SATS)
```

---

## AI Model

| Property | Value |
|---|---|
| Model | YOLOv8n-VisDrone |
| Source | [mshamrai/yolov8n-visdrone](https://huggingface.co/mshamrai/yolov8n-visdrone) |
| Precision | FP16 (OpenVINO IR) |
| Input resolution | 640 × 640 |
| Detection classes | pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor |
| Framework | Ultralytics YOLOv8 / OpenVINO |

See [export_model.md](export_model.md) for instructions on downloading and converting the model.

---

## Related Documentation

| Document | Description |
|---|---|
| [README.md](README.md) | Quick-start guide |
| [user-guide.md](user-guide.md) | Deployment, configuration, architecture, and design |
| [export_model.md](export_model.md) | Downloading and exporting the YOLOv8n-VisDrone model |
