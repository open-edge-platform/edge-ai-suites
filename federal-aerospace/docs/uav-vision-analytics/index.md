# UAV Vision Analytics Application

AI-powered UAV object detection with live telemetry overlay, built on Intel DL Streamer Pipeline Server.

This application processes video from a UAV-mounted camera (or simulated video file), runs YOLOv8n-VisDrone inference to detect objects across ten object classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) directly on the video stream. The annotated output is served as an RTSP stream, consumable by any capable client such as QGroundControl (QGC) or VLC or ffplay.

# Overview

UAV Vision Analytics integrates AI-based object detection with UAV flight controller telemetry on a companion compute platform. Inference results and telemetry are correlated in near real-time and rendered as an on-screen overlay, producing an annotated RTSP stream. The application supports two deployment modes depending on whether an external SDK is available.

![UAV Vision Analytics Application Architecture](./_assets/uav-vision-analytics-architecture.svg)

| Component                                          | Role                                                                                                    |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| RTSP / Video File / Live Camera Streams            | Input video source — UAV camera feed, a recorded video file, or a simulated RTSP stream                 |
| MAVLink UAV Telemetry                              | Telemetry input — GPS, altitude, speed, and heading received from the flight controller over UDP         |
| DL Streamer Pipeline Server (CPU / GPU / NPU)      | Core inference engine — runs YOLOv8n-VisDrone object detection and renders the telemetry overlay on each frame |
| RTSP Stream with Detection & Telemetry Overlay | Annotated output stream — processed video with bounding boxes and telemetry overlay, served over RTSP |


## Deployment Modes

The application supports two deployment modes.

### 1. Standalone Mode (pymavlink)

Self-contained mode using PX4 SITL simulation and pymavlink for MAVLink communication. No external dependencies required.

[Get Started — Standalone Mode](./get-started/get-started-standalone.md)

### 2. UAV Mission Compute SDK Mode

Integration mode that connects to a running instance of the UAV Mission Compute SDK, enabling full mission control and multi-camera pipeline management.

[Get Started — UAV Mission Compute SDK Mode](./get-started/get-started-uavsdk.md)

# Documentation

- [Get Started — Standalone Mode](./get-started/get-started-standalone.md)
- [Get Started — UAV Mission Compute SDK Mode](./get-started/get-started-uavsdk.md)
- [Release Notes](./release-notes.md)

# How-to Guides

- [AI Model](./how-to-guides/model.md) — YOLOv8n-VisDrone model details, `make model` usage
- [Benchmark](./how-to-guides/benchmark.md) — Measure stream density and hardware utilization using `calc_stream_density.sh`
- [Makefile Reference](./how-to-guides/makefile.md) — Shorthand targets for model setup, stack management, and pipeline control
- [Intel RealSense](./how-to-guides/realsense-guide.md) — Connect and stream from an Intel RealSense depth camera as the video source
- [QGroundControl](./how-to-guides/qgroundcontrol.md) — Configure QGroundControl to receive the UAV Vision Analytics video stream
- [Troubleshooting](./how-to-guides/troubleshooting.md) — Common issues and fixes for deployment, inference, and streaming problems

# AI Agent Skills

This application supports AI agent skills for GitHub Copilot and compatible coding agents. Skills cover operational tasks (running pipelines, benchmarking, troubleshooting) and application creation (scaffolding new pymavlink or UAVSDK stacks).

# Intended and Responsible Use

## Intended Use

This project is intended to demonstrate the capabilities of Intel Edge AI for UAV object detection and live telemetry overlay. It is provided for reference and demonstration purposes only, and is not intended to be deployed as-is or for alternate use cases or applications.

## Responsible Use

Intel is committed to respecting human rights and avoiding complicity in human rights abuses. See [Intel's Global Human Rights Principles](https://www.intel.com/content/www/us/en/policy/policy-human-rights.html). Intel's products and software are intended only to be used in applications that do not cause or contribute to a violation of an internationally recognized human right.

If you or anyone on your team becomes aware of instances of potentially inappropriate use, regardless of severity, notify [responsible-ai@intel.com](mailto:responsible-ai@intel.com) or use the [Ethics Reporting Portal](https://www.intel.com/content/www/us/en/corporate-responsibility/ethics-and-compliance.html) immediately.
