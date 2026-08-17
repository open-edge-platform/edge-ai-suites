<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Telemetry Reference — UAV Vision Analytics

## Overview

Telemetry data (GPS position, altitude, ground speed, heading, satellite count)
is overlaid directly on every video frame using a `gvapython` element in the
DL Streamer pipeline. The overlay class runs a background thread that receives
MAVLink messages and stores the latest telemetry values, which are then rendered
as ROI labels onto each frame via `gvawatermark`.

Two overlay implementations exist — one per deployment mode:

| File | Mode | Telemetry source |
|------|------|-----------------|
| `gvapython/telemetry-overlay-pymavlink.py` | pymavlink | MAVLink UDP :14541 (via mavlink-router) |
| `gvapython/telemetry-overlay-uavsdk.py` | UAVSDK | MQTT `uav/{id}/telemetry/status` |

---

## pymavlink Telemetry Overlay

### How it works

`MavlinkReceiver` (a daemon thread) connects to `udp:0.0.0.0:14541` and parses
three MAVLink message types:

| Message | Fields extracted |
|---------|----------------|
| `GLOBAL_POSITION_INT` | `relative_alt` (÷1000 → m), `hdg` (÷100 → °) |
| `VFR_HUD` | `groundspeed` (m/s) |
| `GPS_RAW_INT` | `lat`, `lon` (÷1e7 → °), `alt`, `fix_type`, `satellites_visible` |

`DrawDynamicText.process_frame()` is called per frame by `gvapython`. It reads
the latest values under a threading lock and adds one ROI per text line using
`frame.add_region(x, y, 1, 1, label)`. `gvawatermark` renders these ROIs as
text in the upper-left corner of the frame.

### Overlay fields rendered (per frame)

```
Name  : {{OVERLAY_NAME}}
Frame : {frame_number}
ALT   : {altitude:.1f} m
SPD   : {speed:.1f} m/s
HDG   : {heading:.1f}
LAT   : {latitude:.7f}
LON   : {longitude:.7f}
SATS  : {satellites}
```

### GStreamer pipeline element

```
gvapython module=/home/pipeline-server/gvapython/telemetry-overlay-pymavlink.py
           class=DrawDynamicText
           function=process_frame
           arg=["{{OVERLAY_NAME}}"]
```

The `arg` list is passed to `DrawDynamicText.__init__` as the `name` parameter.

### MAVLink routing (pymavlink mode)

```
PX4 SITL → mavlink-router (server :14550) → broadcast UDP :14541 → pymavlink in DLSPS
```

`mavlink-router/main.conf`:
```ini
[General]
TcpServerPort=5760

[UdpEndpoint px4]
Mode = Server
Address = 0.0.0.0
Port = 14550

[UdpEndpoint gcs]
Mode = Normal
Address = 0.0.0.0
Port = 14541
```

### Volume mount in docker-compose

```yaml
volumes:
  - "./gvapython/telemetry-overlay-pymavlink.py:/home/pipeline-server/gvapython/telemetry-overlay-pymavlink.py"
  - "./scripts/mavlink_pipeline_manager.py:/home/pipeline-server/scripts/pipeline_manager.py"
```

---

## UAVSDK Telemetry Overlay

The UAVSDK overlay reads telemetry from MQTT rather than MAVLink directly.
It subscribes to `uav/{id}/telemetry` topics published by the `uav-mission-compute-sdk`
companion bridge.

### Volume mount in docker-compose

```yaml
volumes:
  - "./gvapython/telemetry-overlay-uavsdk.py:/home/pipeline-server/gvapython/telemetry-overlay-uavsdk.py"
  - "./scripts/uavsdk_pipeline_manager.py:/home/pipeline-server/scripts/pipeline_manager.py"
```

---

## Pipeline Manager Scripts

### mavlink_pipeline_manager.py (pymavlink mode)

Monitors the MAVLink HEARTBEAT `base_mode` flag for `MAV_MODE_FLAG_SAFETY_ARMED`.
Only RTSP sink output is supported (`--sink rtsp`).

**RTSP pipelines defined:**
```python
RTSP_PIPELINES = [
    {"name": "uav_object_detection_cpu", "frame_path": "uav-mavlink-cpu", "device": "CPU"},
    {"name": "uav_object_detection_gpu", "frame_path": "uav-mavlink-gpu", "device": "GPU"},
]
```

**Key constants:**
```python
CONNECTION_STRING   = "udpin:0.0.0.0:14541"
PIPELINE_BASE_URL   = "http://localhost:8081/pipelines/user_defined_pipelines"
PIPELINE_DELETE_URL = "http://localhost:8081/pipelines/{instance_id}"
```

**Invocation inside container:**
```bash
python3 /home/pipeline-server/scripts/pipeline_manager.py --sink rtsp
```

**Makefile target:**
```bash
make start-rtsp      # docker exec -it dlstreamer-pipeline-server bash -c "python3 ..."
```

### uavsdk_pipeline_manager.py (uavsdk mode)

Subscribes to MQTT broker at `host.docker.internal:1883` on topic
`uav/{{UAV_ID}}/telemetry/status`. Parses `armed` boolean from JSON payload.

**On ARMED:** calls `wait_for_rtsp_stream()` with `ffprobe` for each camera RTSP URL
before POSTing pipelines (retries 3× with 2 s delay).

**On DISARMED:** DELETEs all running pipeline instances.

**RTSP source URLs probed:**
```python
RTSP_BASE_URL = f"rtsp://host.docker.internal:8554/uav-1"
PIPELINES = [
    {"name": "nadir_camera_rtsp_cpu",    "rtsp_url": f"{RTSP_BASE_URL}/nadir",   "device": "CPU"},
    {"name": "forward_camera_rtsp_gpu",  "rtsp_url": f"{RTSP_BASE_URL}/forward", "device": "GPU"},
    {"name": "rear_camera_rtsp_npu",     "rtsp_url": f"{RTSP_BASE_URL}/rear",    "device": "NPU"},
]
```

**Only RTSP sink is supported** in UAVSDK mode.

---

## MQTT Topics (pymavlink mode)

DLSPS publishes detection metadata to MQTT when configured with:
```yaml
environment:
  - MQTT_HOST=broker
  - MQTT_PORT=1883
  - APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true
```

Detection topic pattern: `{pipeline_name}` (populated by DLSPS from pipeline name).

---

## Environment Variables for Telemetry

| Variable | Value | Purpose |
|----------|-------|---------|
| `ENABLE_RTSP` | `true` | Enable DLSPS RTSP server |
| `RTSP_PORT` | `8555` | RTSP output port |
| `MQTT_HOST` | `broker` | Mosquitto broker hostname |
| `MQTT_PORT` | `1883` | Mosquitto broker port |
| `ZE_ENABLE_ALT_DRIVERS` | `libze_intel_npu.so` | Required for NPU inference |
