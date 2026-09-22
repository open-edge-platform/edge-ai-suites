<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# AI Helpers

These services process data from the core infra stack and feed results back via MQTT.

## vision-processor/

Real-time object detection on 3 camera feeds using DL Streamer + OpenVINO.

- **Model**: YOLOv2-tiny-vehicle (Intel GPU optimized)
- **Input**: RTSP camera streams from MediaMTX (nadir, forward, rear)
- **Output**: MQTT detection JSON + RTSP annotated streams (with bounding boxes)
- **Config**: `INFERENCE_DEVICE=GPU`, `CONF_THRESH=0.4`, `INFERENCE_FPS=10`
