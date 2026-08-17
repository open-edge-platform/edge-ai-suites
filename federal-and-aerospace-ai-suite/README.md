# Federal and Aerospace AI Suite

AI-enabled applications and supporting components for aerospace and defense edge deployments.

## Applications

### Handheld Multi-Modal

The Handheld Multi-Modal application is a full-stack AI inference and observability platform for handheld scenarios. The application combines LLM inference capability served through the OpenVINO Model Server platform, speech-to-text transcription through the Whisper service, a chat UI through the Open WebUI software, and metrics information through the Grafana dashboard; and runs with the [Visual Pipeline and Platform Evaluation Tool](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/tools/visual-pipeline-and-platform-evaluation-tool) for pipeline visualization.

See [`apps/handheld-multi-modal/`](apps/handheld-multi-modal/README.md).

### Deterministic Threat Detection (Preview)

[Deterministic Threat Detection](apps/deterministic-threat-detection) : A sample application that showcases Time-Sensitive Networking (TSN) to enable deterministic, low-latency transmission of AI-processed video and sensor data alongside best-effort traffic on a shared network. This application is currently in preview. [User Docs](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-aerospace/docs/deterministic-threat-detection/user-guide/index.md)


### UAV Vision Analytics

[UAV Vision Analytics](apps/uav-vision-analytics) : An AI-powered UAV object detection application with live telemetry overlay, built on Intel DL Streamer Pipeline Server. It processes video from a UAV-mounted camera (or simulated video file), runs YOLOv8n-VisDrone inference across ten object classes, and overlays correlated MAVLink telemetry (GPS, altitude, speed, heading) on the output RTSP stream. Supports standalone (pymavlink + PX4 SITL) and UAV Mission Compute SDK deployment modes.

See [`docs/uav-vision-analytics/`](docs/uav-vision-analytics/index.md).


## Components

| Directory                               | Description                                |
|-----------------------------------------|--------------------------------------------|
| `apps/handheld-multi-modal/`            | Handheld multi-modal application           |
| `apps/deterministic-threat-detection/`  | Deterministic threat detection application (Preview) |
| `apps/uav-vision-analytics/`            | UAV vision analytics application           |
| `docs/`                                 | Documentation                              |
