<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# FedAero UAV SDK PoC

PX4 SITL + Gazebo multi-camera UAV simulation with Intel Edge AI vision processing.

## Stack

```text
infra/                     Core simulation + messaging (root compose)
├── px4-sim/               PX4 + Gazebo + 3 cameras (nadir, forward, rear)
├── bridges/               MAVLink ↔ MQTT + Gazebo → RTSP + REST API (port 8080)
├── mediamtx/              RTSP server (port 8554) for camera streams
└── mosquitto/             MQTT broker (host port 1884) for telemetry + detections

sample-apps/               AI helper + demo app (sample-apps/docker-compose.yml)
├── helpers/
│   └── vision-processor/  RTSP → YOLOv2-tiny-vehicle (OpenVINO GPU) → MQTT detections + RTSP annotated
├── edge-ai-showcase/      Primary demo (port 5002)
└── mission-simulation/    Python mission scripts

mcp-server/                MCP server for AI agent integration
├── server.py              Entry point (discovers tools from tool_configs/)
├── providers/             Handler implementations (anomalib, dlstreamer, telemetry)
└── tool_configs/          YAML tool definitions (mavlink, anomalib, dlstreamer, edge_ai_suites)
```

**Compose files**:
- `docker-compose.yml` — core infra (sim + bridges + MQTT + RTSP + observability). Camera mode via `.env`
- `docker-compose.ethernet.yml` — override for remote FC
- `sample-apps/docker-compose.yml` — AI helper (vision-processor) + edge-ai-showcase (decoupled from infra)

**Makefile targets**: `make up` (core infra), `make apps` (helpers + apps), `make down`, `make apps-down`, `make up-ethernet FC_IP=x.x.x.x`

**Camera mode** (`.env`): defaults to multi-cam (3 cameras). Switch to single-cam by toggling vars in `.env`.

**Video Architecture**: Gazebo → camera-bridge → MediaMTX (RTSP raw) → vision-processor → MQTT (detections JSON + annotated JPEG frames)

## RTSP Streams (MediaMTX)
- `rtsp://localhost:8554/uav-1/nadir` — Raw nadir camera (downward)
- `rtsp://localhost:8554/uav-1/forward` — Raw forward camera
- `rtsp://localhost:8554/uav-1/rear` — Raw rear camera

## MQTT Topics
All topics use the pattern `uav/{uav_id}/...` (default `uav_id` = `uav-1`) on broker `localhost:1884`.

**Telemetry** (published by `companion-bridge`):
- `uav/{id}/telemetry/position` — GPS position (lat, lon, altitude)
- `uav/{id}/telemetry/attitude` — Roll, pitch, yaw
- `uav/{id}/telemetry/battery` — Voltage, remaining %
- `uav/{id}/telemetry/velocity` — NED velocity
- `uav/{id}/telemetry/gps` — GPS fix/satellite info
- `uav/{id}/telemetry/status` — Armed state, flight mode, connection
- `uav/{id}/telemetry/#` — Wildcard, all telemetry subtopics

**Camera / Vision**:
- `uav/{id}/camera/{cam}/frame` — Raw camera frame (JPEG bytes, legacy MQTT mode)
- `uav/{id}/camera/{cam}/detections` — JSON detections from vision-processor
- `uav/{id}/camera/{cam}/processed` — Annotated frame with bounding boxes
- `uav/{id}/camera/+/detections` — Wildcard, all cameras' detections
- `uav/{id}/camera/+/frame` — Wildcard, all cameras' raw frames

**Commands & Scenescape**:
- `uav/{id}/command` — Legacy command channel (arm/disarm/etc.)
- `scenescape/data/camera/{ss_camera_id}` — 3D fusion data published by scenescape-adapter

Listen example:
```bash
mosquitto_sub -h localhost -p 1884 -t "uav/uav-1/telemetry/#" -v
```

## Commands
- `/start-stack` — Start UAV + apps
- `/switch-camera-mode` — Switch between `sim` and `usb` camera profiles
- `/validate-infra` — Check PX4, MQTT, cameras
- `/capture-camera` — Grab frames for debug

## Startup Order
1. `make up-sim-camera` — Core infra (PX4 sim → bridges → MQTT/RTSP → observability)
2. `make apps` — AI helper (vision-processor) + edge-ai-showcase dashboard

## Running Missions
```bash
make deps          # one-time, from repo root: creates .venv
cd sample-apps/mission-simulation
MQTT_BROKER_HOST=localhost MQTT_BROKER_PORT=1884 \
REST_API_HOST=localhost REST_API_PORT=8080 \
../../.venv/bin/python mission_1_survey.py
```

## Key Gotchas
1. After PX4 restarts, restart bridges manually
2. Cameras only publish when UAV is armed (RTSP streams pause/resume)
3. PX4 auto-disarms ~20s after landing — don't call `disarm()` manually
4. Apps use `uav-mission-compute-sdk_default` network to reach infra containers
5. RTSP mode: Set `USE_RTSP=false` in docker-compose to revert to MQTT frame-by-frame
6. MediaMTX health: `docker exec vision-processor-multicam curl -sf http://mediamtx:9997/v3/paths/list`
7. Pipeline lifecycle: camera-bridge and vision-processor tear down pipelines on disarm and rebuild on re-arm (no manual restart needed)
