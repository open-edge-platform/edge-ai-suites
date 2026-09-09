# Release Notes: UAV Blueprint

## Version 2026.2.0

**Release Date**: September 9, 2026

**New**:

- **Initial SDK release** for local, single-user UAV edge AI development and evaluation.
- **UAV Vision Analytics application** is now available as a standalone application and integrates with MAVLink telemetry provided by the UAV Mission Compute SDK.
- **Use Case Implementation**: Includes the necessary code to test both the standalone application and the UAV Mission Compute SDK use case.
- **Two camera input modes**: simulated 3-camera Gazebo profile and real V4L2 USB profile with Docker Compose profile-based mutual exclusion.
- **RTSP-first video pipeline** via MediaMTX with H.264 streams for raw and processed feeds.
- **Companion telemetry and control bridge** exposing MAVLink-to-MQTT telemetry plus REST command APIs.
- **Intel GPU AI inference pipeline** using OpenVINO + DL Streamer (YOLOv2-tiny), with detections published to MQTT topics.
- **Observability stack included by default** (InfluxDB + Grafana + telemetry extractors), with lean startup targets available for reduced memory usage.
- **Remote PX4 over Ethernet evaluation workflow** is available for testing companion compute with a separate flight-controller host.
- **Benchmarking workflows** for passive telemetry, bridge stress sweep, and client scaling sweep, including optional HTML reports.
- **Documentation**: Comprehensive documentation on how to set up, configure, and run tests for the use case.

**Known issues and limitations**:

- The SDK is intended for development and evaluation, not production deployment.
- In Ethernet mode, MAVLink UDP and MQTT are not authenticated/encrypted by default; additional transport and broker security is required outside trusted networks.
- Camera streams are available only while the UAV is armed; clients may see RTSP 404 when disarmed.
- Simulated and USB camera bridges cannot run simultaneously.
- First-run image builds can take approximately 10-15 minutes.

## [Edge-Node Infrastructure software](https://github.com/open-edge-platform/edge-node-infrastructure-blueprint/releases)
