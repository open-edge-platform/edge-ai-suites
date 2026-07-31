<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Start UAV Stack

Start the full UAV infrastructure and sample applications.

## Start Order (dependencies matter)

### Step 1: Start core infrastructure
```bash
make up
```
This starts: mosquitto → mediamtx → px4 → companion-bridge + camera-bridge + observability

### Step 2: Wait for PX4 to become healthy (~60-90 seconds)
```bash
docker compose ps px4
```
Wait until status shows "(healthy)". The bridges depend on this.

### Step 3: Verify bridges connected
```bash
docker logs companion-bridge --tail 3
docker logs camera-bridge --tail 3
```
Look for "Connected to PX4" and "First frame published"

### Step 4: Start AI helpers + sample apps
```bash
make apps
```
This starts: vision-processor (AI helper) + edge-ai-showcase (demo dashboard).

## Access Points
- **Edge AI Showcase**: http://localhost:5002
- MQTT broker: localhost:1884
- Companion REST API: localhost:8080

## Stop Everything
```bash
make apps-down
make down
```

## Key Environment Variables (.env + docker-compose.yml)
| Variable | Default | Description |
|----------|---------|-------------|
| PX4_START_SCRIPT | start_px4_multicam.sh | PX4 startup script |
| CAMERA_IDS | nadir,forward,rear | Cameras to stream |
| GZ_WORLD | baylands_multicam | Gazebo world name |
| UAV_ID | uav-1 | UAV identifier used in all MQTT topics |
| INFERENCE_DEVICE | GPU | OpenVINO device (GPU/CPU/NPU) |
| CONF_THRESH | 0.4 | Detection confidence threshold |

## After PX4 Restart
Bridges lose connection when PX4 restarts. Fix:
```bash
docker compose restart companion-bridge camera-bridge
```
Wait 5 seconds, then verify with `/validate-infra`.
