<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Run Pipeline

## Automated (pipeline manager)

```
I have the UAV vision analytics pymavlink stack running (make pymav-up).
Start the pipeline manager inside the container so that pipelines automatically
start when the UAV arms and stop when it disarms. Use RTSP sink output.
```

## Manual — start a single CPU pipeline

```
Manually start the uav_object_detection_cpu pipeline on the running
dlstreamer-pipeline-server container. The RTSP output path should be "uav-cpu".
Use the model at /home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml.
Show me the curl command, capture the instance_id from the response,
check its status, and provide the command to stop it.
```

## Manual — start GPU and NPU pipelines

```
Start both uav_object_detection_gpu and uav_object_detection_npu pipelines
on the running dlstreamer-pipeline-server at http://localhost:8081.
RTSP paths: "uav-gpu" and "uav-npu" respectively.
Capture instance IDs and show how to stop both.
```

## Check pipeline status

```
Show me how to list all registered pipelines, check the status of a running
pipeline instance, and list all currently running instances on the
dlstreamer-pipeline-server REST API at http://localhost:8081.
```
