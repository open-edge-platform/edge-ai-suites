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
- Subscribes to: All 3 camera detection feeds (`nadir`, `forward`, `rear`) + telemetry
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
resp = urllib.request.urlopen('http://px4-gazebo:8080/health', timeout=5)
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
| "Failed to resolve 'px4-gazebo'" | Wrong hostname in env. Must be `px4-gazebo` |
| App can't connect to MQTT | Check it's on `uav-mission-compute-sdk_default` network |
| Processed feed not showing | Check `vision-processor-multicam` is running |

## Rebuild After Code Changes
```bash
docker compose -f sample-apps/docker-compose.yml up -d --build edge-ai-showcase
```
