<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# RTSP Source Pipeline

## Start pipeline consuming an external RTSP camera

```
I have an external IP camera streaming at rtsp://192.168.1.50:554/stream1.
Start a DL Streamer pipeline on the running dlstreamer-pipeline-server that
reads from this RTSP source, runs YOLOv8n-VisDrone detection on CPU,
overlays telemetry, and outputs the annotated stream as RTSP at
rtsp://localhost:8555/uav-external-cam.
Model: /home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml.
Show the curl POST payload with rtspsrc source configuration.
```

## Generate RTSP source pipeline definitions in config.json

```
Generate pipeline definitions for the DL Streamer Pipeline Server that
consume RTSP streams from rtsp://host.docker.internal:8554/uav-1/nadir,
/forward, and /rear. Pipeline names: nadir_camera_rtsp_cpu,
forward_camera_rtsp_gpu, rear_camera_rtsp_npu.
Use rtspsrc location=<url> latency=100 ! rtph264depay ! h264parse ! decodebin3
as the source. Include gvapython telemetry overlay for each. Devices:
nadir=CPU, forward=GPU, rear=NPU.
```

## Switch from file source to RTSP source

```
I currently have file-based pipelines (uav_object_detection_cpu/gpu/npu)
running on the dlstreamer-pipeline-server. I want to add RTSP source pipelines
alongside them that consume rtsp://192.168.1.100:8554/nadir.
Add new pipeline definitions to configs/config-pymavlink.json named
uav_rtsp_cpu, uav_rtsp_gpu using rtspsrc. Show how to restart DLSPS
to pick up the new config (force-recreate, not restart).
```
