# UAV Vision Analytics Application

AI-powered UAV object detection with live telemetry overlay, built on Intel DL Streamer Pipeline Server.

This application processes video from a UAV-mounted camera (or simulated video file), runs YOLOv8n-VisDrone inference to detect objects in ten classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) directly on the video stream. The annotated output is served as RTSP on port `8555`, consumable by any RTSP-capable client.

# Overview

This application demonstrates AI-based object detection integrated with UAV flight controller telemetry on a companion compute platform. Telemetry data (GPS, altitude, speed, heading) is correlated with AI inference results and rendered as an on-screen overlay in near real-time, producing a watermarked RTSP video stream consumable by ground control software such as QGroundControl (QGC).

## Standalone Mode (pymavlink)

[Get Started — Standalone Mode](./get-started/get-started-standalone.md)

## UAV Mission Compute SDK Mode (uav-mission-compute-sdk)

[Get Started — UAV Mission Compute SDK Mode](./get-started/get-started-sdk.md)

# Documentation

- [Get Started — Standalone Mode](./get-started/get-started-standalone.md)
- [Get Started — UAV Mission Compute SDK Mode](./get-started/get-started-sdk.md)
- [Release Notes](./release-notes.md)

# How-to Guides

- [Benchmark](./how-to-guides/benchmark.md)
- [Export YOLOv8n-VisDrone to OpenVINO](./how-to-guides/export_model.md)
- [Makefile Reference](./how-to-guides/makefile.md)
- [UAV Mission Compute SDK flow](./how-to-guides/sdk-guide.md)
- [Intel RealSense](./how-to-guides/realsense-guide.md)
- [Troubleshooting](./how-to-guides/troubleshooting.md)

