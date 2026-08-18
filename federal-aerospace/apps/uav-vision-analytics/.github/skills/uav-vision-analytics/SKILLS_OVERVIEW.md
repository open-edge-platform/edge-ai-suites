<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UAV Vision Analytics — Skills Overview

This document describes the capabilities of the `uav-vision-analytics` skill set.
Skills are organized into two categories: **Operational** (working with an
existing deployed stack) and **Application** (creating a new stack from scratch).

---

## Operational Skills

These skills assist with day-to-day operation, monitoring, tuning, and
maintenance of a running UAV vision analytics stack.

### Run Pipeline

Start, stop, and monitor DL Streamer inference pipelines using the REST API
or the automated pipeline manager.

- **Automated (recommended):** Run `make start-rtsp`
  inside the container. The pipeline manager monitors the UAV armed/disarmed
  state and starts/stops pipelines automatically.
- **Manual REST API:** POST to start a named pipeline; capture the returned
  `instance_id`; DELETE to stop.
- **Verify:** `curl http://localhost:8081/pipelines/{instance_id}/status`
- **Watch output:** `ffplay rtsp://localhost:8555/<stream-path>`

See [`references/PIPELINE.md`](references/PIPELINE.md) for payload formats,
REST paths, and common pipeline variants.

---

### Benchmarking

Measure inference throughput (FPS) and system resource utilisation across
CPU, GPU, and NPU device targets.

- **FPS counter:** `gvafpscounter` is included in GPU/NPU pipeline strings
  and prints live FPS to container stdout:
  ```bash
  docker logs -f dlstreamer-pipeline-server | grep fps
  ```
- **Stream density:** `benchmark/calc_stream_density.sh` measures how many
  concurrent pipeline instances the host can sustain before FPS drops below
  target.
- **System metrics:** The `metrics-manager` container (pymavlink mode) collects
  CPU, GPU, NPU, and power utilization continuously and exposes them via its API.
- **Reference baselines:** See [`../../docs/uav-vision-analytics/benchmark.md`](../../docs/uav-vision-analytics/benchmark.md)
  for recorded FPS baselines per device.

---

### Troubleshooting

Diagnose and resolve common deployment issues.

- **Container logs:**
  ```bash
  docker logs dlstreamer-pipeline-server
  docker logs px4
  docker logs mavlink-router
  ```
- **REST API unreachable:** Verify port 8081 is not already bound;
  confirm the container is `running` with `docker ps`.
- **No RTSP stream:** Confirm a pipeline is in `RUNNING` state via
  `GET /pipelines/{id}/status`; check the `frame.path` in the POST payload.
- **Pipelines not starting on ARM:** Confirm the pipeline manager is running
  (`make start-rtsp`); check MAVLink heartbeat is received in container logs.
- **GPU/NPU pipeline fails:** Verify `group_add` GIDs match host
  (`stat -c %g /dev/dri/render*`); ensure `ZE_ENABLE_ALT_DRIVERS` is set for NPU.
- **Model not found:** Run `make model` to download and export the OpenVINO IR.

Full troubleshooting guide: [`../../docs/uav-vision-analytics/troubleshooting.md`](../../docs/uav-vision-analytics/troubleshooting.md)

---

### Add / Remove Telemetry Fields

Customise which MAVLink fields appear in the on-screen overlay by editing the
`gvapython` telemetry overlay script.

**Current overlay fields** (from `GLOBAL_POSITION_INT`, `VFR_HUD`, `GPS_RAW_INT`):

| Label | MAVLink field | Message |
|-------|--------------|---------|
| `ALT` | `relative_alt / 1000.0` | `GLOBAL_POSITION_INT` |
| `SPD` | `groundspeed` | `VFR_HUD` |
| `HDG` | `hdg / 100.0` | `GLOBAL_POSITION_INT` |
| `LAT` | `lat / 1e7` | `GPS_RAW_INT` |
| `LON` | `lon / 1e7` | `GPS_RAW_INT` |
| `SATS` | `satellites_visible` | `GPS_RAW_INT` |

**To add a new field:**

1. Identify the MAVLink message type and field (use the listener tool below).
2. In `gvapython/telemetry-overlay-pymavlink.py`, add a new `elif` branch in
   `MavlinkReceiver.run()` to parse the field into `latest_data`.
3. Add a corresponding label line in `DrawDynamicText.process_frame()`.
4. Restart the DLSPS container: `make pymav-down && make pymav-up`.

**To remove a field:** Delete the corresponding `lines.append(...)` entry in
`process_frame()`.

See [`references/TELEMETRY.md`](references/TELEMETRY.md) for the full overlay
source and message reference.

---

### MAVLink Message Listener

When adding new telemetry fields, it is useful to first discover which MAVLink
messages your flight controller actually emits and what fields they carry.

The helper script `scripts/mavlink_listener.py` connects to the MAVLink UDP
stream and prints every received message type with its fields and values.

**Usage:**
```bash
# Run on host (requires pymavlink installed: pip install pymavlink)
python3 scripts/mavlink_listener.py

# Run inside the container
docker exec -it dlstreamer-pipeline-server \
  python3 /home/pipeline-server/scripts/mavlink_listener.py

# Filter to a specific message type
python3 scripts/mavlink_listener.py --filter GLOBAL_POSITION_INT

# Log to file
python3 scripts/mavlink_listener.py --output mavlink_log.txt
```

**Source:** `scripts/mavlink_listener.py`

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Listen to all incoming MAVLink messages and print their type,
fields, and values. Useful for discovering available telemetry
data before adding new overlay fields.

Usage:
  python3 mavlink_listener.py [--port PORT] [--filter MSG_TYPE] [--output FILE]
"""

import argparse
from pymavlink import mavutil


def listen(port: int, msg_filter: str | None, output_path: str | None) -> None:
    conn_str = f"udpin:0.0.0.0:{port}"
    print(f"Connecting to {conn_str} ...")
    master = mavutil.mavlink_connection(conn_str)
    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Connected — System {master.target_system}, Component {master.target_component}")
    print(f"Listening (filter={msg_filter or 'ALL'}). Press Ctrl+C to stop.\n")

    out = open(output_path, "w") if output_path else None

    try:
        while True:
            msg = master.recv_match(blocking=True)
            if msg is None:
                continue
            msg_type = msg.get_type()
            if msg_filter and msg_type != msg_filter:
                continue
            fields = {k: v for k, v in msg.to_dict().items() if k not in ("mavpackettype",)}
            line = f"[{msg_type}] {fields}"
            print(line)
            if out:
                out.write(line + "\n")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if out:
            out.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="MAVLink message listener")
    parser.add_argument("--port", type=int, default=14541,
                        help="UDP port to listen on (default: 14541)")
    parser.add_argument("--filter", dest="msg_filter", default=None,
                        help="Only print messages of this type (e.g. GLOBAL_POSITION_INT)")
    parser.add_argument("--output", default=None,
                        help="Optional file path to log messages to")
    args = parser.parse_args()
    listen(args.port, args.msg_filter, args.output)


if __name__ == "__main__":
    main()
```

---

### RealSense Skills

Use an Intel RealSense camera as the video source for the inference pipeline.

- **Supported pipeline:** `uav_realsense_{cpu,gpu,npu}` in `configs/config-pymavlink.json`
- **Source element:** `v4l2src device=/dev/video0` (RealSense RGB stream via UVC)
- **Resolution:** 640×480, BGR format, 30 fps
- **Device access:** The host `/dev` tree must be bind-mounted into the container
  (already configured in the compose file)
- **Start:**
  ```bash
  # Start the stack with RealSense device available
  make pymav-up

  # Manually start a RealSense pipeline
  INSTANCE_ID=$(curl -s -X POST \
    http://localhost:8081/pipelines/user_defined_pipelines/uav_realsense_cpu \
    -H "Content-Type: application/json" \
    -d '{
      "destination": {
        "metadata": {"type": "file", "path": "/tmp/results.jsonl", "format": "json-lines"},
        "frame": {"type": "rtsp", "path": "uav-realsense"}
      },
      "parameters": {
        "detection-properties": {
          "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
          "device": "CPU"
        }
      }
    }' | tr -d '"')
  echo "Instance: $INSTANCE_ID"
  ```
- **View:** `ffplay rtsp://localhost:8555/uav-realsense`
- **Full guide:** [`../../docs/uav-vision-analytics/realsense-guide.md`](../../docs/uav-vision-analytics/realsense-guide.md)

---

## Application Skills

These skills guide creation of a complete new UAV vision analytics application
stack from scratch, using the `uav-vision-analytics` skill.

### Create an Application

Invoke the skill by providing a natural-language description of what you need.
The skill asks up to 6 questions, then generates all required files.

#### MAVSDK-based Application

Integrates with the `uav-mission-compute-sdk`. The DL Streamer container
subscribes to an MQTT broker for armed/disarmed state and consumes RTSP camera
streams from the SDK's simulation environment.

- **Compose file:** `docker-compose-uavsdk.yml` (single container)
- **Telemetry source:** MQTT `uav/{id}/telemetry/status`
- **Pipeline manager:** `scripts/uavsdk_pipeline_manager.py`
- **Pre-flight check:** `ffprobe` probes each RTSP source before starting pipelines
- **Cameras:** nadir (CPU), forward (GPU), rear (NPU) — each a separate pipeline
- **Prerequisite:** `uav-mission-compute-sdk` must be running first

See [example prompt](example-prompts/02-mavsdk-three-camera.md).

#### pymavlink-based Application

Self-contained stack. PX4 SITL, mavlink-router, MQTT broker, and Metrics
Manager are all started together. The DLSPS container receives MAVLink
directly over UDP using pymavlink.

- **Compose file:** `docker-compose-pymavlink.yml`
- **Telemetry source:** MAVLink UDP :14541 (routed from PX4 via mavlink-router)
- **Pipeline manager:** `scripts/mavlink_pipeline_manager.py`
- **Supports:** RTSP sink (`--sink rtsp`)

See [example prompt](example-prompts/01-pymavlink-sim-all-devices.md).

---

### Pipeline Choice

The pipeline source is selected at stack creation time and determines the
GStreamer source element used in `config.json`.

#### File-based (looped video)

Uses a pre-recorded video file (`resources/videos/gazebo.avi`) looped
continuously via `multifilesrc`. Ideal for development and simulation without
physical hardware.

```
multifilesrc location=.../gazebo.avi loop=true
! h264parse ! decodebin3
! gvadetect ...
```

Pipelines: `uav_object_detection_{cpu,gpu,npu}`

#### RealSense / Camera

Uses an Intel RealSense D-series camera (or any UVC camera) via `v4l2src`.
Requires the camera to be physically connected and `/dev/video0` to be
accessible in the container.

```
v4l2src device=/dev/video0
! video/x-raw,format=BGR,width=640,height=480,framerate=30/1
! videoconvert
! gvadetect ...
```

Pipelines: `uav_realsense_{cpu,gpu,npu}`

#### RTSP Source

Consumes an external RTSP stream — either from the SDK's simulation environment
(Gazebo cameras via MediaMTX) or a real IP camera.

```
rtspsrc location=rtsp://<host>:<port>/<path> latency=100
! rtph264depay ! h264parse ! decodebin3
! gvadetect ...
```

Pipelines: `nadir_camera_rtsp_cpu`, `forward_camera_rtsp_gpu`, `rear_camera_rtsp_npu`
(MAVSDK mode) or custom names (pymavlink mode with external camera).

---

## Quick Reference

| Goal | How |
|------|-----|
| Create a new pymavlink stack | Load skill, answer questions, choose `pymavlink` |
| Create a new UAVSDK stack | Load skill, answer questions, choose `uavsdk` |
| Start inference (automated) | `make start-rtsp` after `make pymav-up` |
| Start inference (manual) | `curl -X POST http://localhost:8081/pipelines/user_defined_pipelines/{name}` |
| Stop a pipeline instance | `curl -X DELETE http://localhost:8081/pipelines/{instance_id}` |
| Add a telemetry overlay field | Edit `gvapython/telemetry-overlay-pymavlink.py` |
| Discover MAVLink messages | `python3 scripts/mavlink_listener.py` |
| Use RealSense camera | Start `uav_realsense_cpu/gpu/npu` pipeline via REST |
| Run benchmarks | `benchmark/calc_stream_density.sh`, `docker logs` FPS output |
| Troubleshoot | See [`troubleshooting.md`](../../docs/uav-vision-analytics/troubleshooting.md) |
