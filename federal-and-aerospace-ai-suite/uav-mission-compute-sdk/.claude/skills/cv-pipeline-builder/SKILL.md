---
name: cv-pipeline-builder
description: Build or modify DL Streamer / OpenVINO computer-vision pipelines that consume the UAV's RTSP camera streams and publish results to MQTT. Use when asked to detect, track, classify, or count objects in a camera feed, to swap the inference model, to change inference rate or confidence threshold, or when detections are empty, mislabelled, or not reaching MQTT.
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# CV Pipeline Builder

The reference implementation is `sample-apps/helpers/vision-processor/detector_multicam_rtsp.py`.
Read it before writing a new processor — most requests are better served by configuring or
extending it than by starting fresh.

## Read this first

**Detections are not read from GVA metadata.** `_detect_boxes_from_watermark()`
(`detector_multicam_rtsp.py:248`) recovers bounding boxes by HSV colour-thresholding the blue
rectangles that `gvawatermark` painted onto the frame, then filtering by area, aspect ratio,
and edge margin. Consequences:

- `label` is hard-coded `"vehicle"` and `confidence` is hard-coded `0.8` for every detection.
- Swapping in a multi-class model yields boxes that are all still labelled `"vehicle"` with a
  fabricated confidence. The model's real class output is discarded.
- Objects smaller than 500 px² or within 5 % of the frame edge are dropped, and boxes with
  aspect ratio outside `0.3–3.5` are discarded regardless of what the model said.

If the task needs real labels, real confidences, tracking IDs, or multi-class output, **stop
colour-thresholding and read GVA metadata off the buffer instead** — see
`references/detection-contract.md`. Do not layer more heuristics onto the watermark parser.

## Pipeline shape

Built at `detector_multicam_rtsp.py:100`:

```
rtspsrc location=<rtsp> latency=100 protocols=tcp
  ! rtph264depay ! h264parse ! avdec_h264
  ! videoconvert ! videoscale ! video/x-raw,width=416,height=416
  ! gvadetect model=$MODEL_XML model-proc=$MODEL_PROC device=$DEVICE
              batch-size=1 inference-interval=N threshold=$CONF_THRESH
  ! queue ! gvawatermark ! videoconvert ! video/x-raw,format=BGR
  ! appsink name=sink emit-signals=true max-buffers=2 drop=true
```

`inference-interval` is `max(1, round(STREAM_FPS / INFERENCE_FPS))`
(`detector_multicam_rtsp.py:55`) — inference runs on every Nth frame while the stream decodes
at full rate. Raising `INFERENCE_FPS` raises GPU load roughly linearly.

**The 416×416 scale is hardcoded**, not an env var: `self.model_size = 416` at
`detector_multicam_rtsp.py:79` and `:308` (two classes, both need changing). Swapping to a
model with a different input resolution requires editing both — otherwise frames are scaled
to the wrong size and accuracy silently degrades rather than erroring.

## Configuration

All via env vars in `sample-apps/docker-compose.yml`; defaults from
`detector_multicam_rtsp.py:39-54`.

| Var | Default | Notes |
|---|---|---|
| `MODEL_XML` | `yolo-v2-tiny-vehicle-detection-0001` FP16 | OpenVINO IR `.xml` path |
| `MODEL_PROC` | matching `.json` in DL Streamer `model_proc/` | Must pair with the model |
| `INFERENCE_DEVICE` | `GPU` | `GPU`, `CPU`, `NPU`, `AUTO` |
| `CONF_THRESH` | `0.6` | Passed to `gvadetect threshold=` |
| `CAMERA_IDS` | `nadir,forward,rear` | One pipeline per ID |
| `USE_RTSP` | `false` | **`false` selects the legacy MQTT frame path**, not RTSP |
| `RTSP_HOST` / `RTSP_PORT` | `mediamtx` / `8554` | Container-internal hostname |
| `RTSP_LATENCY` | `100` | ms jitter buffer |
| `STREAM_FPS` / `INFERENCE_FPS` | `30` / `10` | Ratio sets `inference-interval` |

Note `MQTT_BROKER_PORT` defaults to `1883` (container-internal). The broker is published on
host port **1884** — use 1884 only from the host, 1883 from inside the compose network.

## Sources and sinks

Input streams (MediaMTX, `rtsp://mediamtx:8554/...` in-container, `localhost:8554` from host):

| Path | Mode |
|---|---|
| `uav-1/nadir` | sim, USB |
| `uav-1/forward`, `uav-1/rear` | sim only |
| `uav-1/ir`, `uav-1/depth` | RealSense only |

Outputs per camera:

- `uav/{uav_id}/camera/{cam}/detections` — detection JSON (schema in `references/detection-contract.md`)
- `uav/{uav_id}/camera/{cam}/processed` — annotated frame, JPEG quality 80

No annotated stream is pushed back to MediaMTX — annotated frames go to MQTT only.

## Pipeline lifecycle

Pipelines are **armed-state driven**. On disarm the pipeline is torn down (an RTSP source
would stall against a dead stream); on re-arm it is rebuilt fresh. This is intentional —
do not add retry loops or restart the container to "fix" a stopped pipeline when the UAV is
simply disarmed. Arm the UAV and the stream returns on its own.

## Verifying a change

```bash
# MediaMTX sees the source paths
docker exec vision-processor-multicam curl -sf http://mediamtx:9997/v3/paths/list

# Detections actually flowing
mosquitto_sub -h localhost -p 1884 -t "uav/uav-1/camera/+/detections" -v

# Inference landed on the iGPU, not a silent CPU fallback
docker logs vision-processor-multicam 2>&1 | grep -i "device\|GPU\|fallback"
```

The UAV must be **armed** for any of these to produce output.
