<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Makefile Reference

The `Makefile` at the root of `apps/uav-vision-analytics/` provides shorthand targets for the most common development and deployment tasks.

Run `make help` (or just `make`) to list all targets with descriptions.

---

## Quick Reference

| Target | Description |
|---|---|
| `make model` | Download YOLOv8n-VisDrone checkpoint and export to OpenVINO FP16 |
| `make pymav-up` | Start the standalone pymavlink stack |
| `make pymav-down` | Stop and remove the pymavlink stack (includes volumes) |
| `make mavsdk-up` | Start the MAVSDK stack |
| `make mavsdk-down` | Stop and remove the MAVSDK stack (includes volumes) |
| `make start-rtsp` | Start inference pipelines with RTSP output |
| `make start-udpsink` | Start inference pipelines with UDP sink output |
| `make build` | Alias for `pymav-up` |

---

## Target Details

### `make model`

Creates a Python virtual environment under `resources/venv/`, installs dependencies from `resources/requirements.txt`, downloads the `best.pt` checkpoint from HuggingFace, and exports it to OpenVINO FP16 IR format.

```
resources/
├── requirements.txt
├── venv/                          ← created by this target
└── models/
    └── yolov8n-visdrone/
        ├── best.pt                ← downloaded checkpoint
        └── best_openvino_model/   ← exported IR (best.xml + best.bin)
```

> **Note:** `ultralytics` is pinned to `8.4.67`. Do not upgrade without re-verifying GPU/NPU compatibility of the exported IR — newer versions use a CumSum-based detection head that fails to compile on GPU and NPU OpenVINO plugins.

---

### `make pymav-up` / `make pymav-down`

Manages the **standalone pymavlink stack** (`docker-compose-pymavlink.yml`), which includes:

- `dlstreamer-pipeline-server` — AI inference, REST API (:8081), RTSP output (:8555)
- `broker` — Eclipse Mosquitto MQTT broker (:1883)
- `px4` — PX4 SITL flight controller simulator
- `mavlink-router` — MAVLink routing sidecar (receives on :14550, broadcasts to :14541)
- `metrics-manager` — system metrics dashboard

`down` passes `-v` to also remove named volumes (pipeline cache).

---

### `make mavsdk-up` / `make mavsdk-down`

Manages the **MAVSDK stack** (`docker-compose-mavsdk.yml`), which requires the `edge-ai-suites/federal-aerospace/uav-mission-compute-sdk` project to already be running.

Start order:

```bash
# 1. Start the SDK project (provides PX4, MQTT telemetry)
cd edge-ai-suites/federal-aerospace/uav-mission-compute-sdk && make up-sim-camera

# 2. Start this application
make mavsdk-up
```

`down` passes `-v` to also remove named volumes.

---

### `make start-rtsp`

Executes `mavlink_pipeline_manager.py` inside the running `dlstreamer-pipeline-server` container. This script monitors MAVLink ARMED/DISARMED state and automatically starts/stops inference pipelines with **RTSP frame output**.

Requires the DLSPS container to already be running (`make pymav-up` or `make mavsdk-up` first).

---

### `make start-udpsink`

Same as `start-rtsp` but uses `mavlink_pipeline_manager_udpsink.py`, which routes annotated frames to a **UDP sink** instead of RTSP. Useful for low-latency local consumption or integration with custom receivers.

---

### `make build`

Convenience alias for `make pymav-up`. Starts the default standalone stack.

---

## Common Workflows

### First-time setup

```bash
cp .env.example .env    # set HOST_IP
make model              # download + export model
make pymav-up           # start the stack
make start-rtsp         # start pipelines
```

### Stop everything and clean up

```bash
make pymav-down
```

### Switch to MAVSDK mode

```bash
make pymav-down                       # stop standalone stack if running
cd edge-ai-suites/federal-aerospace/uav-mission-compute-sdk && make up-sim-camera   # start SDK project
cd .. && make mavsdk-up               # start MAVSDK stack
make start-rtsp
```
