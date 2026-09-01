<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Start UAV Stack

Start the full UAV infrastructure stack.

## Modes
- `sim` (default): Gazebo 3-camera bridge (`make up-sim-camera`)
- `usb`: USB camera bridge (`make up-usb-camera`)

When using `usb` mode, the `.env` is updated automatically by `make up-usb-camera`.
When using `sim` mode, the `.env` is updated automatically by `make up-sim-camera`.

## Start Order (dependencies matter)

### Step 1: Start core infrastructure
```bash
# Sim mode
make up-sim-camera

# USB mode
make up-usb-camera

# Lean variants — omit Grafana/InfluxDB/metrics-manager (~300 MB RAM saved)
make up-sim-camera-lean
make up-usb-camera-lean
```
This starts: mosquitto -> mediamtx -> px4 -> companion-bridge + one camera bridge + observability (lean skips observability)

### Step 2: Verify bridges connected
```bash
docker logs companion-bridge --tail 3

# Sim mode
docker logs camera-bridge --tail 3

# USB mode
docker logs usb-camera-bridge --tail 3
```
Look for "Connected to PX4" and camera frame push logs.

## Access Points
- MQTT broker: localhost:1884
- Companion REST API: localhost:8080
- RTSP raw stream: rtsp://localhost:8554/uav-1/nadir

## Stop Everything
```bash
make down
```

## Key Environment Variables (.env + docker-compose.yml)
| Variable | Default | Description |
|----------|---------|-------------|
| PX4_START_SCRIPT | start_px4_multicam.sh | PX4 startup script |
| CAMERA_IDS | nadir,forward,rear | Cameras to stream |
| GZ_WORLD | baylands_multicam | Gazebo world name |
| UAV_ID | uav-1 | UAV identifier used in all MQTT topics |
| USB_VIDEO_DEVICE | /dev/video32 | Host camera device for usb mode |
| USB_CAMERA_ID | nadir | RTSP camera path published by usb bridge |
| VISION_CAMERA_IDS | nadir,forward,rear | Camera list consumed by vision processor |
| INFERENCE_DEVICE | GPU | OpenVINO device (GPU/CPU/NPU) |
| CONF_THRESH | 0.4 | Detection confidence threshold |

## After PX4 Restart
Bridges lose connection when PX4 restarts. Fix:
```bash
# Sim mode
docker compose restart companion-bridge camera-bridge

# USB mode
docker compose restart companion-bridge usb-camera-bridge
```
Wait 5 seconds, then verify with `/validate-infra`.

## RTSP 404 Note
RTSP paths exist only while UAV is armed. If stream returns 404:
```bash
curl -X POST http://localhost:8080/action/arm
```
