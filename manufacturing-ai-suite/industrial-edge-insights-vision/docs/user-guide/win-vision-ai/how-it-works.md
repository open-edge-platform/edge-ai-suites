# How It Works

This document provides an overview of the architecture and components of Win Vision AI.

## Architecture

![Win Vision AI Architecture](./_assets/winvisionai-arch-full.drawio.svg)

### Inputs

- **Video file** — local video file playback
- **RTSP camera** — network camera stream
- **GenICam camera** — industrial camera via GenICam SDK

### Application

- **Config Loader** — loads and validates YAML configuration; defines models and pipelines
- **Pipeline Manager** — manages N parallel GStreamer pipelines with FPS and latency probes
- **Media Manager** — manages the embedded MediaMTX server for RTSP and WebRTC output
- **Metrics Collector** — exports pipeline metrics to log or Prometheus

### Inference

- **Intel DL Streamer** — runs object detection and classification inference using OpenVINO™
  on:
  - CPU: runs inference using the OpenVINO™ runtime on system memory
  - GPU: runs inference using the D3D11 OpenVINO™ plugin with D3D11 shared memory
  - NPU: runs inference using the OpenVINO™ runtime on the neural engine

### Outputs

- **MediaMTX** — re-streams encoded video over RTSP (port 8554) and WebRTC (port 8889)
- **MQTT broker** — receives structured inference metadata over TCP (port 1883)
- **JSON file** — writes inference metadata to a file using the DL Streamer `gvametapublish`
  element (for information on the element, see [DL Streamer Documentation](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/elements/gvametapublish.html))

### Viewers

- **Browser / VLC** — consume the live stream over WebRTC or RTSP
- **MQTT subscriber** — consumes inference metadata published to the MQTT broker

## Supporting Resources

- [DL Streamer Documentation](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/index.html)
  - [DL Streamer Supported Models](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/supported_models.html)
  - [DL Streamer Model Conversion Scripts README](https://github.com/open-edge-platform/dlstreamer/blob/main/scripts/download_models/README.md)
