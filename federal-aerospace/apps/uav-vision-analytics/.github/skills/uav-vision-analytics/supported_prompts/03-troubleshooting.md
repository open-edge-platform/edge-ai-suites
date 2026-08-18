<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Troubleshooting

## Pipelines not starting on ARM

```
The UAV vision analytics pymavlink stack is running but pipelines are not
starting when I arm the UAV in QGroundControl. The pipeline manager is running
inside the container. Help me diagnose: check the container logs for MAVLink
heartbeat receipt, verify the mavlink-router is routing from :14550 to :14541,
and confirm the REST API at http://localhost:8081 is reachable.
```

## No RTSP stream visible in ffplay

```
I started the uav_object_detection_cpu pipeline via the REST API and got
an instance_id back, but ffplay shows a blank screen on
rtsp://localhost:8555/uav-cpu. Help me diagnose: check pipeline state,
verify RTSP_PORT is set correctly, and confirm the frame destination
path matches what I used in the POST payload.
```

## GPU pipeline fails to start

```
The uav_object_detection_gpu pipeline returns an error when started.
The container has /dev/dri mounted. Help me diagnose: check the group_add
GIDs in the compose file against the host render group
(stat -c %g /dev/dri/render*), verify the DLSPS container can access
the GPU, and check container logs for gvadetect device errors.
```

## NPU pipeline fails to start

```
The uav_object_detection_npu pipeline fails with a device error.
Help me verify: ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so is set in
the container environment, /dev/accel is accessible, the group_add
list includes the accel GID, and the model is valid OpenVINO IR FP16.
```

## Model file not found

```
The dlstreamer-pipeline-server container starts but all pipelines fail
with a model not found error. Help me: verify the model file exists at
resources/models/yolov8n-visdrone/best_openvino_model/best.xml on the
host, confirm the resources volume is correctly mounted inside the container,
and run make model if the export is missing.
```

## REST API unreachable

```
curl http://localhost:8081/pipelines returns connection refused.
The docker ps output shows the dlstreamer-pipeline-server container is running.
Help me diagnose the port binding, check REST_SERVER_PORT environment variable,
and verify no other process is using port 8081.
```
