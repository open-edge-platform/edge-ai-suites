<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Intel DL Streamer Pipelines Guide

## Overview

Intel DL Streamer is a GStreamer-based framework for building video analytics pipelines with AI inference on Intel CPU, GPU, and NPU using OpenVINO.

A pipeline is a chain of GStreamer elements:

```text
input source ! decode ! inference ! post-processing ! output sink
```

## Prerequisites

- Edge Node Infrastructure software image deployed
- Docker Engine 25+ with CDI enabled (see [Container Device Interface Guide](configure-cdi.md))
- Intel GPU and/or NPU hardware present
- Network connectivity for pulling images and sample videos

---

## Setup

### Pull the DL Streamer Image

```bash
docker pull intel/dlstreamer:latest
```

Verify it works:

```bash
docker run --rm --device intel.com/gpu=card0 intel/dlstreamer:latest gst-inspect-1.0 gvadetect
```

### Download Models

DL Streamer inference elements need OpenVINO IR models. Download them using the bundled script:

```bash
mkdir -p models

docker run --rm \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  intel/dlstreamer:latest \
  bash -c "/opt/intel/dlstreamer/samples/download_public_models.sh yolox_s"
```

Add `coco128` to also quantize to INT8:

```bash
docker run --rm \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  intel/dlstreamer:latest \
  bash -c "/opt/intel/dlstreamer/samples/download_public_models.sh yolox_s coco128"
```

Available models include: `yolox-tiny`, `yolox_s`, `yolov7`, `yolov8s`, `yolov9c`, `yolov10s`, `yolo11s`, `yolo11s-seg`, `yolo11s-pose`, and others. Pass `all` for everything.

Models are saved to `models/public/<model_name>/<precision>/` (containing `.xml` and `.bin` files).

---

## Running Pipelines

Each example below is a complete, copy-paste-ready command.

> **Proxy note:** If behind a corporate proxy, add `-e http_proxy=$http_proxy -e https_proxy=$https_proxy -e no_proxy=$no_proxy` to each `docker run` command. This is needed both for model downloads and for `urisourcebin` to fetch remote videos.

### Object Detection — GPU

```bash
docker run --rm \
  --device intel.com/gpu=card0 \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  intel/dlstreamer:latest \
  bash -c "\
    gst-launch-1.0 \
      urisourcebin buffer-size=4096 uri=https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4 \
      ! decodebin3 \
      ! gvadetect model=\$MODELS_PATH/public/yolox_s/FP16/yolox_s.xml model-proc=/opt/intel/dlstreamer/samples/model_proc/public/yolo-x.json device=GPU pre-process-backend=va-surface-sharing \
      ! queue \
      ! gvafpscounter \
      ! fakesink async=false"
```

### Object Detection — CPU

```bash
docker run --rm \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  intel/dlstreamer:latest \
  bash -c "\
    gst-launch-1.0 \
      urisourcebin buffer-size=4096 uri=https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4 \
      ! decodebin3 \
      ! gvadetect model=\$MODELS_PATH/public/yolox_s/FP16/yolox_s.xml model-proc=/opt/intel/dlstreamer/samples/model_proc/public/yolo-x.json device=CPU pre-process-backend=opencv \
      ! queue \
      ! gvafpscounter \
      ! fakesink async=false"
```

### Object Detection — NPU

```bash
docker run --rm \
  --device intel.com/gpu=card0 \
  --device intel.com/npu=npu0 \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  intel/dlstreamer:latest \
  bash -c "\
    gst-launch-1.0 \
      urisourcebin buffer-size=4096 uri=https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4 \
      ! decodebin3 \
      ! gvadetect model=\$MODELS_PATH/public/yolox_s/FP16/yolox_s.xml model-proc=/opt/intel/dlstreamer/samples/model_proc/public/yolo-x.json device=NPU pre-process-backend=va \
      ! queue \
      ! gvafpscounter \
      ! fakesink async=false"
```

### Save Results to JSON

```bash
docker run --rm \
  --device intel.com/gpu=card0 \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  -v /tmp/results:/results \
  intel/dlstreamer:latest \
  bash -c "\
    gst-launch-1.0 \
      urisourcebin buffer-size=4096 uri=https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4 \
      ! decodebin3 \
      ! gvadetect model=\$MODELS_PATH/public/yolox_s/FP16/yolox_s.xml model-proc=/opt/intel/dlstreamer/samples/model_proc/public/yolo-x.json device=GPU pre-process-backend=va-surface-sharing \
      ! queue \
      ! gvametaconvert add-tensor-data=true \
      ! gvametapublish file-format=json-lines file-path=/results/output.json \
      ! fakesink async=false"
```

Results are saved to `/tmp/results/output.json` on the host.

### Use a Local Video File

To use a local video instead of a remote URL, two things change from the examples above:

1. Add a volume mount for your video directory: `-v /path/to/videos:/videos`
2. Use `filesrc location=/videos/my-video.mp4` as the source element instead of `urisourcebin ... uri=<URL>`

```bash
docker run --rm \
  --device intel.com/gpu=card0 \
  -v $(pwd)/models:/models \
  -e MODELS_PATH=/models \
  -v /path/to/videos:/videos \
  intel/dlstreamer:latest \
  bash -c "\
    gst-launch-1.0 \
      filesrc location=/videos/my-video.mp4 \
      ! decodebin3 \
      ! gvadetect model=\$MODELS_PATH/public/yolox_s/FP16/yolox_s.xml model-proc=/opt/intel/dlstreamer/samples/model_proc/public/yolo-x.json device=GPU pre-process-backend=va-surface-sharing \
      ! queue \
      ! gvafpscounter \
      ! fakesink async=false"
```

---

## Key Elements Reference

| Element | Purpose | Devices |
|---------|---------|---------|
| `gvadetect` | Object detection (YOLO, SSD, etc.) | CPU, GPU, NPU |
| `gvaclassify` | Classification, segmentation, pose | CPU, GPU, NPU |
| `gvainference` | Raw model inference | CPU, GPU, NPU |
| `gvagenai` | GenAI/VLM inference (image → text) | CPU, GPU |
| `gvatrack` | Object tracking across frames | CPU |
| `gvawatermark` | Draw inference results on frames | — |
| `gvafpscounter` | Measure pipeline FPS | — |
| `gvametaconvert` | Convert metadata to JSON | — |
| `gvametapublish` | Publish to file, MQTT, or Kafka | — |

## Pipeline Building Blocks

### Sources

| Use case | Element |
|----------|---------|
| Remote video | `urisourcebin buffer-size=4096 uri=<URL>` |
| Local file | `filesrc location=<path>` |
| USB camera | `v4l2src device=/dev/video0` |
| RTSP stream | `rtspsrc location=rtsp://<host>:<port>/<path>` |

### Device + Pre-process Combinations

| Device | `pre-process-backend` | Notes |
|--------|----------------------|-------|
| `CPU` | `opencv` | No GPU needed |
| `GPU` | `va-surface-sharing` | Zero-copy decode → inference |
| `NPU` | `va` | VA-API pre-processing |

### Output Sinks

| Output | Elements |
|--------|----------|
| FPS only | `gvafpscounter ! fakesink async=false` |
| JSON file | `gvametaconvert ! gvametapublish file-format=json-lines file-path=out.json ! fakesink async=false` |
| Display | `vapostproc ! gvawatermark ! videoconvert ! autovideosink sync=false` |
| MP4 file | `vapostproc ! gvawatermark ! vah264enc ! h264parse ! mp4mux ! filesink location=out.mp4` |

---

## Running in Kubernetes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: dlstreamer-gpu
spec:
  restartPolicy: Never
  containers:
    - name: dlstreamer
      image: intel/dlstreamer:latest
      command:
        - bash
        - -c
        - |
          gst-launch-1.0 \
            urisourcebin buffer-size=4096 uri=https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4 \
            ! decodebin3 \
            ! gvadetect model=$MODELS_PATH/public/yolox_s/FP16/yolox_s.xml model-proc=/opt/intel/dlstreamer/samples/model_proc/public/yolo-x.json device=GPU pre-process-backend=va-surface-sharing \
            ! queue \
            ! gvafpscounter \
            ! fakesink async=false
      env:
        - name: MODELS_PATH
          value: /models
      resources:
        limits:
          gpu.intel.com/xe: "1"
      volumeMounts:
        - name: models
          mountPath: /models
  volumes:
    - name: models
      hostPath:
        path: /path/to/dlstreamer/models
```

```bash
kubectl apply -f dlstreamer-gpu.yaml
kubectl wait pod/dlstreamer-gpu --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s
kubectl logs dlstreamer-gpu
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No such element 'gvadetect'" | Run `gst-inspect-1.0 gvadetect` inside the container to verify plugins are loaded |
| GPU not available in container | Check CDI: `ls /etc/cdi/intel.com-gpu.yaml` |
| "Could not initialize element" | Model file missing — re-run download script |
| Low FPS on GPU | Set `pre-process-backend=va-surface-sharing` for zero-copy |

---

## Advanced: AI-Assisted Pipeline Generation

For complex pipelines, you can use the **DL Streamer Coding Agent** — a Claude Code skill that generates complete, working DL Streamer applications from plain-English descriptions. Instead of manually wiring GStreamer elements, describe what you want and the agent builds, validates, and runs the app for you.

See the [DL Streamer Coding Agent Guide](./use-dlstreamer-coding-agent.md) for usage details, example prompts, and supported use cases.

---

## References

- [DL Streamer Repository](https://github.com/open-edge-platform/dlstreamer)
- [DL Streamer Docker Hub](https://hub.docker.com/r/intel/dlstreamer)
- [DL Streamer Elements Reference](https://github.com/open-edge-platform/dlstreamer/blob/main/docs/user-guide/elements/elements.md)
- [DL Streamer Samples](https://github.com/open-edge-platform/dlstreamer/tree/main/samples)
- [Container Device Interface Guide](./configure-cdi.md) — CDI setup for GPU/NPU access

<!--hide_directive
:::{toctree}
:hidden:

DL Streamer Coding Agent Guide <use-dlstreamer-coding-agent.md>
:::
hide_directive-->
