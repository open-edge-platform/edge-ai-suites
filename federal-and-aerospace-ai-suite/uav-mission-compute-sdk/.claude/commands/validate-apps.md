<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Validate Sample Applications

Validate that the sample applications are running and connected to the UAV infrastructure.

## Prerequisites
- Infrastructure stack must be healthy first (run `/validate-infra` if unsure)
- The apps connect to the infra stack via the shared `uav-mission-compute-sdk_default` Docker network

## Applications

### edge-ai-showcase (port 5002) — PRIMARY DEMO
- Location: `sample-apps/edge-ai-showcase/`
- Container: `edge-ai-showcase`
- Subscribes to: camera detection feeds configured by `VISION_CAMERA_IDS` + telemetry
- Intel Edge AI Stack demo with multi-camera analytics

## Validation Steps

### 1. Check app containers are running
```bash
docker ps --filter name=edge-ai-showcase --filter name=vision-processor --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 2. Verify edge-ai-showcase health endpoint
```bash
curl -s http://localhost:5002/health
```
Expected: `{"cameras_active": [...], "mqtt_connected": true, "status": "healthy"}`

### 2b. Verify active camera set matches mode
```bash
docker logs vision-processor-multicam 2>&1 | grep "Cameras:" | tail -1
```
Expected:
- Sim mode: `Cameras: ['nadir', 'forward', 'rear']`
- USB mode: `Cameras: ['nadir']`

### 3. Verify showcase is receiving frames (count should increase)
```bash
curl -s http://localhost:5002/api/stats | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['frame_counts'])"
sleep 3
curl -s http://localhost:5002/api/stats | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['frame_counts'])"
```
Expected: Second counts > first counts

### 4. Verify showcase can reach companion bridge (UAV commands work)
```bash
docker exec edge-ai-showcase python3 -c "
import urllib.request, json
resp = urllib.request.urlopen('http://px4-gazebo:8080/health', timeout=5)  # px4-sitl:8080 in usb-camera mode
print(json.loads(resp.read()))
"
```
Expected: `{'armed': False, 'connected': True, 'mode': '...', 'status': 'ok'}`

### 5. Test mission capability
```bash
curl -s http://localhost:5002/api/mission/status
```
Expected: `{"progress": 0, "running": false, "step": "Idle"}`

## Starting the Apps

```bash
# From repo root:
make apps
```

## Common Fixes

| Symptom | Fix |
|---------|-----|
| No camera feeds | Check vision-processor: `docker logs vision-processor-multicam --tail 20` |
| "Connection refused" on mission | Companion bridge needs restart: `docker compose restart companion-bridge` |
| "Failed to resolve 'px4-gazebo'" | Wrong hostname. Use `px4-gazebo` (sim) or `px4-sitl` (usb) — set via `COMPANION_BRIDGE_URL` in `.env` |
| App can't connect to MQTT | Check it's on `uav-mission-compute-sdk_default` network |
| Processed feed not showing | Check `vision-processor-multicam` is running |
| Only one camera visible in sim mode | Set `.env` `VISION_CAMERA_IDS=nadir,forward,rear`, then restart apps |
| Forward/rear errors in USB mode | Set `.env` `VISION_CAMERA_IDS=nadir`, then restart apps |
| RTSP 404 from app | Arm UAV: `curl -X POST http://localhost:8080/action/arm` |

## Rebuild After Code Changes
```bash
docker compose -f sample-apps/docker-compose.yml up -d --build edge-ai-showcase
```
