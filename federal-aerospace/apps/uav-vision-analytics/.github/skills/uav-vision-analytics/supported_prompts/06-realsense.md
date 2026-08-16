<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# RealSense Camera Pipelines

## Start a RealSense CPU pipeline

```
I have the UAV vision analytics pymavlink stack running and an Intel RealSense
camera connected at /dev/video0. Start the uav_realsense_cpu pipeline using
the REST API at http://localhost:8081. RTSP output path: "uav-realsense".
Model: /home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml.
Capture the instance_id and show how to view the stream with ffplay.
```

## Start a RealSense GPU pipeline

```
Start the uav_realsense_gpu pipeline on the running dlstreamer-pipeline-server
at http://localhost:8081. RTSP output path: "uav-realsense-gpu".
Device: GPU. Show the curl command with instance_id capture.
```

## Verify RealSense device is accessible in the container

```
I have an Intel RealSense camera connected to the host. Verify that
/dev/video0 is accessible inside the dlstreamer-pipeline-server container,
check that the device is mounted correctly in the compose file, and confirm
the video group GID in group_add matches the host.
```

## Switch from looped file to RealSense mid-session

```
The uav_object_detection_cpu pipeline is running with a looped gazebo.avi file.
I now want to switch to a live Intel RealSense camera feed instead.
Stop the current pipeline, then start uav_realsense_cpu with RTSP output
path "uav-realsense". Show all curl commands with instance_id handling.
```
