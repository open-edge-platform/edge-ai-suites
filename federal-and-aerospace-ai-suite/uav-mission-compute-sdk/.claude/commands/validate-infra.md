<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Validate Infrastructure Stack

Validate the UAV infrastructure (PX4 + Gazebo stack) is healthy and streaming.

## Camera Profile Awareness
- Sim profile: `camera-bridge` should run, `usb-camera-bridge` should not.
- USB profile: `usb-camera-bridge` should run, `camera-bridge` should not.
- In both profiles, PX4 + companion-bridge + mediamtx + mosquitto must be up.

## Context
- Compose file: `docker-compose.yml` at repo root
- Core services: mosquitto, mediamtx, px4, companion-bridge, one camera bridge
- AI helpers (vision-processor): `sample-apps/docker-compose.yml`
- MQTT broker exposed on host port 1884 (telemetry + detections only)
- MediaMTX RTSP server on host port 8554 (camera streams)
- Companion REST API at px4-gazebo:8080 (sim) / px4-sitl:8080 (usb) on container network; host: localhost:8080
- PX4 MAVLink on host UDP ports 14540/14580

## Validation Steps

### 1. Check all containers are running and healthy
```bash
docker compose ps
```
Expected: Services "Up", px4 shows "(healthy)", and only one camera bridge active.

### 1b. Confirm active camera bridge
```bash
docker compose ps --services --filter status=running | grep -E 'camera-bridge|usb-camera-bridge'
```
Expected: exactly one result.

### 2. Check MQTT broker is accepting connections
```bash
docker exec mqtt-broker mosquitto_sub -t '$SYS/broker/clients/connected' -C 1 -W 5
```
Expected: Number >= 2 (bridge, companion)

### 3. Verify PX4 SITL is running
```bash
docker exec px4-gazebo pgrep -x px4   # sim-camera mode
docker exec px4-sitl pgrep -x px4     # usb-camera mode
```
Expected: PID returned (not empty)

### 4. Check companion bridge connected to PX4
```bash
docker logs companion-bridge --tail 5
```
Expected: "Connected to PX4" and "Telemetry → MQTT publishing started"

### 5. Verify MediaMTX RTSP server is healthy
```bash
docker exec vision-processor-multicam curl -sf http://mediamtx:9997/v3/config/global/get | python3 -c "import sys,json; print('API OK:', json.load(sys.stdin).get('api'))"
docker exec vision-processor-multicam curl -sf http://mediamtx:9997/v3/paths/list | python3 -c "import sys,json; [print(i['name']) for i in json.load(sys.stdin)['items']]"
```
Expected: Shows "API OK: True" and lists uav-1 camera paths

### 6. Verify RTSP camera streams are available
Arm first (required for stream publication):
```bash
curl -X POST http://localhost:8080/action/arm
sleep 2
```

```bash
ffprobe -v quiet -print_format json -show_streams rtsp://localhost:8554/uav-1/nadir 2>&1 | grep -q '"codec_name":"h264"' && echo "Nadir stream OK" || echo "Nadir stream missing"

# Sim profile only
ffprobe -v quiet -print_format json -show_streams rtsp://localhost:8554/uav-1/forward 2>&1 | grep -q '"codec_name":"h264"' && echo "Forward stream OK" || echo "Forward stream missing"
ffprobe -v quiet -print_format json -show_streams rtsp://localhost:8554/uav-1/rear 2>&1 | grep -q '"codec_name":"h264"' && echo "Rear stream OK" || echo "Rear stream missing"
```
Expected: `nadir` always present when armed; `forward/rear` present only in sim profile.

### 7. Verify telemetry is flowing
```bash
docker exec mqtt-broker mosquitto_sub -t "uav/uav-1/telemetry/position" -C 1 -W 5
```
Expected: JSON with lat_deg, lng_deg, relative_altitude_m

### 8. Test companion bridge REST API
```bash
docker exec px4-gazebo curl -sf http://127.0.0.1:8080/health   # sim-camera mode
docker exec px4-sitl curl -sf http://127.0.0.1:8080/health     # usb-camera mode
```
Expected: `{"armed": false, "connected": true, "mode": "...", "status": "ok"}`

## Common Fixes

| Symptom | Fix |
|---------|-----|
| px4 unhealthy | `docker compose restart px4` (sim) or `docker compose restart px4-sih` (usb), then recheck `docker compose ps` |
| mediamtx unhealthy | `docker compose restart mediamtx` |
| companion-bridge "Connection refused" or "heartbeats timed out" | `docker compose restart companion-bridge` |
| camera-bridge no RTSP streams | Check logs: `docker logs camera-bridge` (sim profile - look for "RTSP pipeline started") |
| usb-camera-bridge no RTSP streams | Check logs: `docker logs usb-camera-bridge` and verify `USB_VIDEO_DEVICE` |
| camera-bridge GStreamer errors | Verify MediaMTX is healthy, check RTSP_HOST/RTSP_PORT env vars |
| vision-processor no detections | Check RTSP consumption: `docker logs vision-processor-multicam` (look for "RTSP DL Streamer pipeline started") |
| vision-processor "Could not connect to RTSP" | Verify MediaMTX has streams: `docker exec vision-processor-multicam curl -sf http://mediamtx:9997/v3/paths/list` |
| All services stale after PX4 restart | Restart in order: `px4`/`px4-sih` → `mediamtx` → `camera-bridge`/`usb-camera-bridge` |
| Want to revert to MQTT mode | Set `USE_RTSP=false` in docker-compose.yml, restart camera-bridge |

## Restart Order (full stack)
```bash
make down
make up-sim-camera
```
