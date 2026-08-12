<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# File-based Pipeline

## Use looped gazebo.avi as video source

```
I want to run the UAV vision analytics stack using a looped video file
(resources/videos/gazebo.avi) as the video source — no physical camera needed.
The pymavlink stack is already deployed. Start the uav_object_detection_cpu
pipeline with the file source via the REST API at http://localhost:8081.
RTSP output path: "uav-file-cpu". Show the curl command and how to view
the output stream.
```

## Generate file-based pipelines in config.json

```
Generate a config.json for the DL Streamer Pipeline Server with three
file-based pipeline variants (CPU, GPU, NPU) using
multifilesrc location=.../resources/videos/gazebo.avi loop=true as source.
Pipeline names: uav_object_detection_cpu, uav_object_detection_gpu,
uav_object_detection_npu. Include gvapython telemetry overlay with arg
"SimFlight" for all variants. Model path:
/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml
```

## Change the source video file

```
I want to replace gazebo.avi with a different video file (mission_flight.avi)
in the UAV vision analytics pipeline configs. Update all multifilesrc location
paths in configs/config-pymavlink.json to point to
/home/pipeline-server/resources/videos/mission_flight.avi.
Also update any documentation or Makefile references to the filename.
```
