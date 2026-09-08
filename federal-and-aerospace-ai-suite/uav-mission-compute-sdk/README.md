<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Edge AI UAV (Uncrewed Aerial Vehicle) Platform

> This SDK is intended as a development kit and reference solution for evaluating Intel Edge AI capabilities on UAV platforms.
>
> This deployment is for a single-user system. It is designed for local and single-user development.

Multi-camera UAV simulation with Intel Edge AI — PX4 + Gazebo + OpenVINO vision processing.

---

## Where to Start

| I want to… | Go here |
|---|---|
| Run the demo end-to-end | [Quick Start](#quick-start) below |
| Understand the full architecture | [docs/user-guide/how-it-works.md](docs/user-guide/how-it-works.md) |
| Configure cameras, switch USB/sim | [docs/user-guide/camera-modes.md](docs/user-guide/camera-modes.md) |
| See all ports and services | [docs/user-guide/ports.md](docs/user-guide/ports.md) |
| Connect a real PX4 over Ethernet | [docs/user-guide/ethernet-px4.md](docs/user-guide/ethernet-px4.md) |
| Review security config/recommendations | [docs/security-considerations.md](docs/security-considerations.md) |
| Troubleshoot a broken stack | [docs/user-guide/get-started.md](docs/user-guide/get-started.md) |

---

## Getting the Code

This SDK lives inside the [edge-ai-suites](https://github.com/open-edge-platform/edge-ai-suites) monorepo. To
check out only this directory instead of the entire repo, use a sparse
checkout:

```bash
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set federal-and-aerospace-ai-suite/uav-mission-compute-sdk
cd federal-and-aerospace-ai-suite/uav-mission-compute-sdk
```

---

## Prerequisites

- **OS**: Ubuntu 24.04
- **Docker Engine** 24+ and Docker Compose v2 (`docker compose version`)
- **Intel GPU** for vision inference
- **RAM**: 16 GB minimum (sim mode); 8 GB sufficient for USB camera mode
- **Disk**: ~15 GB for Docker images

```bash
# Verify Intel GPU render nodes are present
ls /dev/dri/renderD*
```

---

## Quick Start

```bash
# 1. Create/populate .env and detect GPU devices
make init
```

```bash
# 2. Start core infra (PX4 + Gazebo + camera bridges + MQTT + RTSP + observability)
make up-sim-camera
```

See [docs/user-guide/get-started.md](docs/user-guide/get-started.md) for full setup, troubleshooting, and ports.

---

## What It Does

A PX4 UAV simulation with 3 cameras (nadir, forward, rear) streams live H264 video via RTSP through OpenVINO vehicle detection on Intel GPU. The dashboard shows real-time detections, bounding boxes, and flight telemetry.

```mermaid
flowchart LR
    SIM[PX4 + Gazebo<br/>3 Cameras 416x416]
    BRIDGE[Bridges<br/>MAVLink + RTSP H264]
    RTSP[MediaMTX<br/>RTSP :8554]
    MQTT[MQTT Broker<br/>:1884]
    AI[Intel Edge AI<br/>YOLOv2 GPU]
    APPS[Applications<br/>Dashboards]
    
    SIM -->|MAVLink| BRIDGE
    SIM -->|gz frames| BRIDGE
    BRIDGE -->|telemetry| MQTT
    BRIDGE -->|"H264<br/>streams"| RTSP
    RTSP -->|RTSP| AI
    AI -->|detections| MQTT
    MQTT --> APPS
    RTSP -.->|"optional<br/>viewing"| APPS
    
    style SIM fill:#e1f5ff,stroke:#0277bd,stroke-width:2px
    style BRIDGE fill:#f1f8e9,stroke:#558b2f,stroke-width:2px
    style RTSP fill:#ffe0b2,stroke:#e65100,stroke-width:3px
    style MQTT fill:#fff4e1,stroke:#f57c00,stroke-width:2px
    style AI fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style APPS fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
```

---

## Camera Modes

| Mode | Command | PX4 | Cameras |
|---|---|---|---|
| Simulated (default) | `make up-sim-camera` | Gazebo SITL | 3 virtual cameras (nadir, forward, rear) |
| Real USB camera | `make up-usb-camera` | SIH (no Gazebo) | 1 USB/V4L2 device |

---

## Key Makefile Targets

```bash
make init                  # Create .env, detect GPU
make up-sim-camera         # Start sim stack (includes Grafana/InfluxDB)
make up-sim-camera-lean    # Start sim stack without observability (~300 MB RAM saved)
make up-usb-camera         # Start USB camera stack
make up-usb-camera-lean    # Start USB camera stack without observability
make down                  # Stop all containers (core infra + apps)
make logs                  # Tail core infra logs
```

---

## Structure

```
Makefile                     Shortcuts for common dev workflows
infra/                       Infrastructure definitions
  px4-sim/                   PX4 SITL + Gazebo image; also used for remote FC deploy
  bridges/companion/         MAVLink ↔ MQTT bridge (companion_bridge.py — REST API)
  bridges/camera/            Gazebo cameras → RTSP (ffmpeg H264)
  bridges/usb-camera/        USB/V4L2 device → RTSP
  mediamtx/                  RTSP server config
  mosquitto/                 MQTT broker config
  grafana/                   Dashboards provisioning (Flight Telemetry, Platform Health)
  metrics-manager/           Host GPU/CPU/power metrics → InfluxDB
sample-apps/
  helpers/vision-processor/  YOLOv2-tiny on Intel GPU; outputs detections to MQTT + RTSP
  edge-ai-showcase/          Flask dashboard (detections, telemetry, arm/fly/land)
  mission-simulation/        Scripted waypoint missions via REST API
mcp-server/                  MCP server — AI agent control of the UAV stack
docs/                        Architecture, ports, camera modes, Ethernet guide
docker-compose.yml           Core simulation stack
docker-compose.ethernet.yml  Override for remote PX4 FC over Ethernet
```

---

## Key Ports

| Service | URL | Purpose |
|---|---|---|
| REST API | http://localhost:8080 | UAV commands (arm, takeoff, land, goto) |
| RTSP Streams | rtsp://localhost:8554/uav-1/{cam} | Raw + annotated video |
| MQTT broker | localhost:1884 | Telemetry + detection events |
| Grafana | http://localhost:3000 | Flight telemetry + platform health dashboards |
| InfluxDB | http://localhost:8086 | Time-series data UI |

## Disabling Observability (Save ~300 MB RAM)

Grafana, InfluxDB, topic-extractor, and metrics-manager are grouped under the
`observability` profile. They are **on by default** but can be omitted for
tighter memory budgets.

```bash
# Start without observability stack (~300 MB RAM saved)
make up-sim-camera-lean    # sim cameras, no Grafana/InfluxDB
make up-usb-camera-lean    # USB camera, no Grafana/InfluxDB

# Standard start includes observability (default)
make up-sim-camera         # includes Grafana + InfluxDB
```

Or stop observability on an already-running stack:
```bash
docker compose stop grafana influxdb topic-extractor metrics-manager
```

**View live camera**: `ffplay rtsp://localhost:8554/uav-1/nadir` (needs a local display). Headless alternative: `ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/uav-1/nadir -t 10 -c:v copy nadir.mkv`

## Notices and Disclaimers

**Notice for FFmpeg:**

FFmpeg is an open source project licensed under LGPL and GPL. See https://www.ffmpeg.org/legal.html. You are solely responsible for determining if your use of FFmpeg requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of FFmpeg.

**Notice for GStreamer:**

GStreamer is an open source framework licensed under LGPL. See https://gstreamer.freedesktop.org/documentation/frequently-asked-questions/licensing.html. You are solely responsible for determining if your use of GStreamer requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of GStreamer.

Intel is committed to respecting human rights and avoiding complicity in human rights abuses. See Intel's [Global Human Rights Principles](https://www.intel.com/content/www/us/en/policy/policy-human-rights.html). Intel's products and software are intended only to be used in applications that do not cause or contribute to a violation of an internationally recognized human right.
