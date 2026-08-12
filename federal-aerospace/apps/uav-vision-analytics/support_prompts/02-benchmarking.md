<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Benchmarking

## FPS from container logs

```
The dlstreamer-pipeline-server container is running with the
uav_object_detection_gpu pipeline active. Show me how to watch
live FPS output from the gvafpscounter element in the container logs,
and explain what the output means.
```

## Stream density test

```
I want to find the maximum number of concurrent uav_object_detection_cpu
pipeline instances that can run on my host before FPS drops below 15.
Use the benchmark/calc_stream_density.sh script or guide me through
using the REST API to start multiple instances and monitor their status.
Host is at http://localhost:8081.
```

## Compare CPU vs GPU vs NPU performance

```
I want to benchmark YOLOv8n-VisDrone inference on CPU, GPU, and NPU using
the UAV vision analytics stack. Start one pipeline per device
(uav_object_detection_cpu, uav_object_detection_gpu, uav_object_detection_npu),
collect FPS from container logs for 30 seconds each, and produce a
comparison table.
```

## System resource utilisation

```
The metrics-manager container is running alongside the pymavlink stack.
Show me how to query CPU, GPU, NPU, and power utilisation metrics from it
while the uav_object_detection_gpu pipeline is running.
```
