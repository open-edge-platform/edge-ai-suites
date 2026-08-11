<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Ports

## Host-Exposed

| Port | Service | Description |
|------|---------|-------------|
| 1884 | MQTT broker | Telemetry + detections (container port 1883) |
| 8080 | REST API | UAV commands (arm, takeoff, land, goto) |
| 8554 | MediaMTX RTSP | Raw + annotated camera streams (rtsp://localhost:8554/uav-1/{camera}[/processed]) |
| 8888 | MediaMTX HLS | Optional web viewing |
| 8889 | MediaMTX WebRTC | Optional web viewing |
| 9997 | MediaMTX API | Stream management |
| 1935 | MediaMTX RTMP | RTMP ingest (internal: vision-processor pushes annotated streams) |
| 9998 | MediaMTX Metrics | Prometheus-compatible |
| 5002 | edge-ai-showcase | Primary demo dashboard |
| 14540/udp | MAVLink | PX4 inbound |
| 14580/udp | MAVLink | PX4 outbound |

## Observability (always on)

| Port | Service | Description |
|------|---------|-------------|
| 8086 | InfluxDB | Time-series DB — org: uav-sdk, bucket: telemetry |
| 3000 | Grafana | Dashboards — admin / uav-sdk |
| 9090 | metrics-manager | REST API + SSE stream (`/health`, `/api/v1/metrics`, `/metrics/stream`) |
| 9273 | metrics-manager | Prometheus exposition endpoint (Telegraf output — exposed but not scraped by this stack) |

