<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Intel RealSense — UAV Vision Analytics

## Prerequisites

See [System Requirements](../get-started/system-requirements.md) for the full list of software and hardware prerequisites.

---

## Testing the camera streams

List connected USB devices and enumerate available video devices:

```bash
lsusb
v4l2-ctl --list-devices
```

### View the RGB video stream

```bash
# ffplay is part of the ffmpeg package
ffplay -f v4l2 -input_format yuyv422 -video_size 1280x720 /dev/video4
```

> **Note:** The device file may vary depending on your system. Use `v4l2-ctl --list-devices` to find the correct device file.

### View the depth stream

```bash
ffplay -f v4l2 -input_format Z16 -video_size 848x480 /dev/video0
```

> **Note:** The device file may vary depending on your system. Use `v4l2-ctl --list-devices` to find the correct device file.
> The `Z16` format is a 16-bit depth value per pixel. `ffplay` will render it as a greyscale image.

---

## DLStreamer pipelines

Three inference pipelines are available. Only one can be active at a time because they each access the video device directly:

| Pipeline | Inference device | `device` value |
|---|---|---|
| `uav_realsense_cpu` | CPU | `CPU` |
| `uav_realsense_gpu` | GPU | `GPU` |
| `uav_realsense_npu` | NPU | `NPU` |

### Starting a pipeline

> **Note:** Currently the realsense pipelines are only available in standalone mode (pymavlink). The UAV Mission Compute SDK mode does not support the RealSense camera. Adding support should be straightforward by copying the existing pipelines from `config-pymavlink.json` into `config-uavsdk.json`.

> **Note:** The device file `/dev/video4` may vary depending on your system. Use `v4l2-ctl --list-devices` to find the correct device file and update `config-pymavlink.json` accordingly for the above pipelines before proceeding with the following steps.

Use the Pipeline Server REST API to start a pipeline. The POST response body is the UUID of the running instance — save it to stop the pipeline later.

Replace `<pipeline-name>` with one of the pipeline names from the table above, `<rtsp-stream-name>` with the desired RTSP path (e.g. `realsense`), and `device` with the matching value.

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/<pipeline-name> \
  -H 'Content-Type: application/json' \
  -d '{
    "destination": {
      "metadata": {
        "type": "file",
        "path": "/tmp/results.jsonl",
        "format": "json-lines"
      },
      "frame": {
        "type": "rtsp",
        "path": "<rtsp-stream-name>"
      }
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "<CPU|GPU|NPU>"
      }
    }
  }' | tr -d '"')
echo "Instance ID: $INSTANCE_ID"
```

**Example** — start the CPU pipeline and publish the stream at `rtsp://localhost:8555/realsense`:

```bash
INSTANCE_ID=$(curl -s -X POST \
  http://localhost:8081/pipelines/user_defined_pipelines/uav_realsense_cpu \
  -H 'Content-Type: application/json' \
  -d '{
    "destination": {
      "metadata": {
        "type": "file",
        "path": "/tmp/results.jsonl",
        "format": "json-lines"
      },
      "frame": {
        "type": "rtsp",
        "path": "realsense"
      }
    },
    "parameters": {
      "detection-properties": {
        "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
        "device": "CPU"
      }
    }
  }' | tr -d '"')
echo "Instance ID: $INSTANCE_ID"
```

View the annotated stream:

```bash
ffplay rtsp://localhost:8555/realsense
```

To stop the pipeline:

```bash
curl -X DELETE http://localhost:8081/pipelines/${INSTANCE_ID}
```
