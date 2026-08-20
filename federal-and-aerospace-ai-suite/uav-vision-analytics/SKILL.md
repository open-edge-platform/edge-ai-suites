---
name: uav-vision-analytics
description: >-
  Build an end-to-end UAV object detection and telemetry overlay application
  on Intel hardware using DL Streamer Pipeline Server with MAVLink telemetry.
  USE FOR: creating UAV/drone vision analytics stacks that detect objects from
  aerial video (file, RealSense camera, or RTSP feed), overlay live MAVLink
  telemetry (GPS, altitude, speed, heading) on the annotated RTSP stream, and
  support autonomous pipeline start/stop triggered by the drone armed/disarmed
  state. Supports two deployment modes: pymavlink (self-contained with PX4 SITL)
  and UAVSDK (integrates with uav-mission-compute-sdk). DO NOT USE FOR:
  ground-based camera analytics without MAVLink telemetry, cloud-only
  deployments, or model training.
license: Apache-2.0
compatibility: >-
  Requires Docker + Docker Compose v2, Intel CPU (optionally GPU/NPU with
  video/render groups). For pymavlink mode: PX4 SITL runs in simulation.
  For UAVSDK mode: uav-mission-compute-sdk must be running first.
  Ports 8081 (REST), 8555 (RTSP), 1883 (MQTT), 14541/udp (MAVLink) must be
  free. Tested with intel/dlstreamer-pipeline-server:2026.1.0 image.
---

<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# UAV Vision Analytics Skill

Build an end-to-end aerial object detection and telemetry overlay application
using Intel DL Streamer Pipeline Server. The stack detects objects in video
from a UAV camera using YOLOv8n-VisDrone (or a custom OpenVINO model),
overlays live MAVLink flight telemetry (altitude, speed, heading, GPS) onto the
annotated RTSP stream, and automatically starts/stops inference pipelines in
sync with the UAV armed/disarmed state.

## Architecture Overview

```
Video Source (file/RealSense/RTSP)
    │
    ▼
DL Streamer Pipeline Server
  ├── gvadetect (OpenVINO YOLOv8n-VisDrone, CPU/GPU/NPU)
  ├── gvapython (telemetry overlay — altitude, speed, heading, GPS)
  ├── gvametaconvert → gvametapublish → MQTT
  └── appsink → RTSP :8555
         │
         ▼
    QGC / ffplay / browser

MAVLink/MQTT → Pipeline Manager → start/stop pipelines on ARMED/DISARMED
```

## Deployment Modes

| Mode | Compose file | Telemetry source | When to use |
|------|-------------|-----------------|-------------|
| **pymavlink** | `docker-compose-pymavlink.yml` | MAVLink UDP :14541 via mavlink-router from PX4 SITL | Self-contained simulation |
| **uavsdk** | `docker-compose-uavsdk.yml` | MQTT `uav/{id}/telemetry/status` from SDK | Integration with uav-mission-compute-sdk |

## How to Use This Skill

1. Read this file end-to-end.
2. Ask the questions in ONE batched message (defaults shown in brackets); accept
   `go` / `defaults` / empty to proceed.
3. Validate parameters before generating files.
4. Load reference files on demand — **do not load all up front**.
5. Generate the application files and verify against the completion criteria.

## Reference Files (load on demand)

| File | Load when authoring |
|------|-------------------|
| [`references/PIPELINE.md`](references/PIPELINE.md) | DL Streamer config.json, pipeline variants, REST launcher, payload format |
| [`references/TELEMETRY.md`](references/TELEMETRY.md) | MAVLink/UAVSDK telemetry overlay (gvapython), pipeline manager scripts |
| [`references/DEPLOY.md`](references/DEPLOY.md) | Docker Compose services, env vars, Makefile targets, volumes, device access |
| [`references/MODEL.md`](references/MODEL.md) | YOLOv8n-VisDrone download + OpenVINO export, custom model substitution |
| [`references/TESTS.md`](references/TESTS.md) | pytest structure, REST API tests, RTSP stream validation, MQTT checks |

## Parameters (from invoking prompt)

| Param | Purpose |
|-------|---------|
| `{{DEPLOYMENT_MODE}}` | `pymavlink` \| `uavsdk` |
| `{{VIDEO_SOURCE}}` | `file` (gazebo.avi loop) \| `realsense` (v4l2src) \| `rtsp` (rtspsrc) \| `gazebo-rtsp` (RTSP from SDK sim) |
| `{{DEVICE}}` | `CPU` \| `GPU` \| `NPU` \| `all` (generates CPU+GPU+NPU variants) |
| `{{MODEL}}` | `yolov8n-visdrone` (default) \| path to custom OpenVINO IR `.xml` |
| `{{PIPELINE_PREFIX}}` | prefix for pipeline names, e.g. `uav_object_detection` |
| `{{RTSP_PATHS}}` | RTSP stream path(s) published by DLSPS, e.g. `uav-cpu`, `uav-gpu` |
| `{{UAV_ID}}` | UAV identifier for UAVSDK MQTT topic, e.g. `uav-1` |
| `{{STACK_DIR}}` | output directory for the new application stack |
| `{{OVERLAY_NAME}}` | label shown in the telemetry overlay, e.g. `MyUAV-CPU` |

## Questions (single batched prompt)

1. Deployment mode [`pymavlink`] (`pymavlink` or `uavsdk`)
2. Video source [`file`] (`file` for gazebo.avi loop, `realsense` for Intel RealSense, `rtsp` for external RTSP, `gazebo-rtsp` for SDK simulation streams)
3. Inference device [`CPU`] (`GPU`, `NPU`, or `all` to generate all three variants)
4. Model [`yolov8n-visdrone`] (or path to a custom OpenVINO IR `.xml` file)
5. Output directory [`./uav-stack`]
6. UAV ID (UAVSDK mode only) [`uav-1`]

## Parameter Validation (enforce BEFORE file generation)

| Param | Rule | Failure |
|-------|------|---------|
| `DEPLOYMENT_MODE` | `pymavlink`\|`uavsdk` | wrong compose file selected |
| `VIDEO_SOURCE` | `file`\|`realsense`\|`rtsp`\|`gazebo-rtsp` | pipeline GStreamer string invalid |
| `DEVICE` | `CPU`\|`GPU`\|`NPU`\|`all` | unknown device in gvadetect |
| `MODEL` | ends in `.xml`, file exists (if custom) | DLSPS fails to load model |
| `UAV_ID` | `^[a-z0-9-]+$`, no spaces | MQTT topic invalid |
| `PIPELINE_PREFIX` | `^[a-z0-9_]+$` | REST path + MQTT topic break |

## Supported Use Cases

| Use case | `DEPLOYMENT_MODE` | `VIDEO_SOURCE` | `DEVICE` |
|----------|------------------|---------------|---------|
| PX4 SITL sim, looped video, CPU inference | `pymavlink` | `file` | `CPU` |
| PX4 SITL sim, looped video, all devices | `pymavlink` | `file` | `all` |
| Intel RealSense camera, GPU | `pymavlink` | `realsense` | `GPU` |
| SDK integration, 3-camera (nadir/forward/rear) | `uavsdk` | `gazebo-rtsp` | `all` |
| Custom model, custom RTSP feed | `pymavlink` | `rtsp` | `CPU` |

## Execution Guardrails

- Before generating files: verify all parameters pass validation.
- Before `make pymav-up` or `make uavsdk-up`: check ports 8081, 8555, 1883 are free.
- For UAVSDK mode: confirm `uav-mission-compute-sdk` stack is running first.
- Never hardcode secrets — use `.env` variables for `HOST_IP`, device GIDs, credentials.
- Use `make model` to download and export the model before starting the stack.
- Always quote shell variables: `"$HOST_IP"`, `"$MODEL_PATH"`.
- For pymavlink mode: the `mavlink-router` build `context` MUST point to
  `./mavlink-router` inside `{{STACK_DIR}}` — copy `Dockerfile` + `main.conf`
  into the stack; never reference a sibling repo (e.g.
  `uav-mission-compute-sdk`) as the build context, or `docker compose up`
  fails with "unable to prepare context: path ... not found" on any machine
  that hasn't checked out that sibling repo.

## Generated File Layout

```
{{STACK_DIR}}/
├── docker-compose-pymavlink.yml     # or docker-compose-uavsdk.yml
├── .env                             # HOST_IP, image tags
├── .env.example                     # template copied by make init
├── Makefile                         # init, model, stack up/down, pipeline start/stop
├── configs/
│   └── config-{{PIPELINE_PREFIX}}.json   # DLSPS pipeline definitions
├── gvapython/
│   └── telemetry-overlay-{{MODE}}.py     # gvapython telemetry overlay
├── scripts/
│   └── pipeline_manager.py               # armed/disarmed pipeline lifecycle
├── mavlink-router/
│   ├── Dockerfile                         # self-contained build (pymavlink only — never reference an external path)
│   └── main.conf                          # mavlink-router config (pymavlink only)
├── resources/
│   ├── models/yolov8n-visdrone/          # exported OpenVINO model
│   └── videos/gazebo.avi                 # sample video (file source)
└── tests/
    ├── conftest.py
    ├── test_stack_up.py
    ├── test_pipeline_start.py
    ├── test_rtsp_stream.py
    └── test_mavlink_trigger.py
```

## Template Variable Substitution

Every `{{VAR}}` in generated code MUST be substituted with its concrete value
before writing the file — literal `{{...}}` left in config.json, docker-compose,
or scripts is a syntax error.

## Completion Criteria (all must pass)

1. `make init` succeeds: `.env` created with auto-detected GPU/NPU device paths.
2. `make model` succeeds: OpenVINO IR model present at
   `resources/models/yolov8n-visdrone/best_openvino_model/best.xml`.
3. `make pymav-up` (or `make uavsdk-up`) → all containers `running`.
4. `curl http://localhost:8081/pipelines` returns the registered pipeline definitions.
5. Pipeline manager starts with `make start-rtsp` and connects to MAVLink/MQTT.
6. On ARMED signal: pipelines start; RTSP streams appear at `:8555`.
7. `ffplay rtsp://localhost:8555/{{RTSP_PATH}}` shows annotated video with telemetry overlay.
8. On DISARMED signal: all pipeline instances are deleted.
9. On UAVSDK mode: pipelines start only after RTSP probe confirms streams are live.
10. `make pymav-down` (or `make uavsdk-down`) cleanly stops all containers.
11. `pytest -q tests/` passes all tests.
