# Overview

`WinVisionAI` is a Python application for running multiple AI inference pipelines
concurrently on Intel hardware (CPU / GPU / NPU). Built on GStreamer and Intel®
DL Streamer, it handles the end-to-end pipeline — from camera or video input,
through OpenVINO-accelerated detection and classification, to live RTSP / WebRTC
streaming and structured metadata output.

Configuration is YAML-driven: define your models, input sources, and outputs, then
run. Advanced users can supply raw GStreamer pipeline strings directly for full
control.

> **Platform:** Windows only.

## Description

### Architecture

It consists of the following components:

- App (`app.py`) — config loader, service bootstrap, pipeline builder
- PipelineManager — runs N GStreamer pipelines on a shared GLib main loop
- DL Streamer — `gvadetect` / `gvaclassify` / `gvametapublish` on OpenVINO
- MediaService — auto-downloads and starts the embedded MediaMTX server
- MediaMTX server — re-streams encoded video over RTSP and WebRTC / WHIP
- MQTT broker — receives inference metadata via `gvametapublish method=mqtt`
- JSON file output — `gvametapublish method=file` writes metadata to disk
- Metrics — log / Prometheus exporter for FPS, latency, and pipeline state

<div style="text-align: center;">
    <img src=docs/winvisionai-architecture.drawio.svg width=800>
</div>