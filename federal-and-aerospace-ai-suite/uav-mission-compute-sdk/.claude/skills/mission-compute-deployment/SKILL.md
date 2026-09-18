---
name: mission-compute-deployment
description: Deploy, manage, and validate the UAV SDK infrastructure stack — start/stop services with camera mode selection, validate health, collect diagnostics. Use when asked to "start the stack", "deploy the SDK", "switch camera modes", "bring down the stack", "check infrastructure health", or when infrastructure is not responding.
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Stack Deployment

Deploy and manage the complete UAV SDK infrastructure: PX4 SITL + Gazebo (or USB camera / RealSense), bridges,
MQTT broker, RTSP server, and optional observability (metrics, Grafana).

## Camera Profiles

The SDK supports three camera modes via `.env` file configuration:

| Mode | Make Target | Cameras | Use Case |
|---|---|---|---|
| **sim** (default) | `make up-sim-camera` | 3 virtual (nadir, forward, rear) | Development, testing, CI/CD |
| **usb** | `make up-usb-camera` | 1 real USB V4L2 webcam | Testing with real hardware (single camera) |
| **realsense** | `make up-realsense-camera` | Intel D400 (IR + depth) | Testing with Intel RealSense depth camera |

Each mode rewrites the `.env` file and composes the appropriate `docker-compose.yml` override. All modes
expose RTSP streams on `localhost:8554`, MQTT on `localhost:1884`, and the companion-bridge REST API on
`localhost:8080`.

## Startup Options

### Core infrastructure only (minimal footprint)
```bash
make up-sim-camera    # 3 virtual cameras (3 containers: px4-sim, bridges, mqtt/rtsp/rest)
make up-usb-camera    # 1 USB camera
make up-realsense-camera  # RealSense D400
```

Add `-lean` to omit the observability stack (metrics-manager, InfluxDB, Grafana):
```bash
make up-sim-camera-lean
```

### Add the app layer (vision processing + dashboard)
```bash
make apps             # Starts vision-processor (YOLOv2 vehicle detection) + edge-ai-showcase dashboard (port 5002)
```

Run `make apps` **after** the core stack is up. The vision-processor consumes RTSP camera streams and
publishes detections (JSON) + annotated frames to MQTT.

### Check infrastructure health
```bash
curl -s localhost:8080/health          # Companion-bridge REST health (connected/armed/mode)
mosquitto_sub -h localhost -p 1884 -t "uav/uav-1/telemetry/#" -v  # Live telemetry
docker exec vision-processor-multicam curl -sf http://mediamtx:9997/v3/paths/list  # RTSP streams
```

## Teardown

```bash
make down             # Stop core infra (px4-sim, bridges, mqtt, rtsp, metrics)
make apps-down        # Stop app layer (vision-processor, edge-ai-showcase)
```

## Compose files & environment

- **`docker-compose.yml`** — core stack (always run). Camera mode via `.env`.
- **`docker-compose.ethernet.yml`** — optional override for remote flight controller (set `FC_IP=x.x.x.x`).
- **`sample-apps/docker-compose.yml`** — app layer (vision-processor + dashboard). Uses `uav-mission-compute-sdk_default` network to reach core infra containers.

The `.env` file controls which camera bridge runs and how mediamtx routes RTSP streams. **Do not edit `.env`
manually** — use the `make up-*` targets, which rewrite `.env` and validate the configuration.

## Validation checklist

After `make up-*`, confirm:

1. **REST API responsive**: `curl -s localhost:8080/health` returns `{status: "ok", connected: true, ...}`
2. **MQTT broker running**: `mosquitto_sub -h localhost -p 1884 -t '$SYS/#' -W 1` (returns broker stats)
3. **RTSP streams live**: Try `ffplay rtsp://localhost:8554/uav-1/nadir` (requires ffmpeg/ffplay installed)
4. **Docker network**: All containers on `uav-mission-compute-sdk_default` bridge

Run `make validate-infra` for an automated check.

## Common pitfalls

1. **Stack won't start after camera-mode switch**: The `.env` file may be out of sync. Run the target
   again: `make up-sim-camera` rewrites `.env` and validates before bringing up containers.
2. **RTSP streams not showing in apps**: Confirm PX4 is armed with `curl localhost:8080/health`.
   Camera bridges only publish while armed; disarm pauses streams and tears down pipelines.
3. **Bridges not connecting to PX4**: After a PX4 restart, the MAVSDK connection may stale. Restart
   bridges manually: `docker restart companion-bridge camera-bridge`.
4. **Port conflicts**: Default ports are 8080 (REST), 8554 (RTSP), 1884 (MQTT). If in use on your system,
   edit `docker-compose.yml` port bindings and update `.env` accordingly.

## Observability stack

By default (without `-lean`), the core stack includes:

- **InfluxDB** — time-series telemetry store (no port exposed, internal only)
- **metrics-manager** — scrapes container stats (CPU, memory, GPU/NPU) every 10 s
- **Grafana** — dashboard (port `3000`, admin user: `admin`, password: `admin`)

Grafana is optional for development. Use `-lean` targets to reduce resource footprint during testing.

## References

- **MQTT topics**: See CLAUDE.md, MQTT Topics section
- **REST API contract**: See mission-authoring skill, REST contract section
- **Makefile targets**: Defined in repo root `Makefile`
- **Docker network**: All containers share `uav-mission-compute-sdk_default` bridge created by root compose
