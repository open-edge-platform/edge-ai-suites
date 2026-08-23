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
| 1935 | MediaMTX RTMP | RTMP ingest (internal: vision-processor pushes annotated streams) |
| 5002 | edge-ai-showcase | Primary demo dashboard |
| 14540/udp | MAVLink | PX4 inbound |
| 14580/udp | MAVLink | PX4 outbound |

## Internal Only (not host-published)

| Port | Service | Description |
|------|---------|-------------|
| 9997 | MediaMTX API | Stream management API (container-internal only) |
| 9998 | MediaMTX Metrics | Prometheus-compatible — container-internal only |

## Observability (always on)

> **Note** — Grafana is intended **only for simulation visualization when the drone is grounded**.

| Port | Service | Description |
|------|---------|-------------|
| 8086 | InfluxDB | Time-series DB — org: uav-sdk, bucket: telemetry |
| 3000 | Grafana | Dashboards — admin / uav-sdk |
| 9090 | metrics-manager | REST API + SSE stream — container-internal only; use `docker exec metrics-manager curl -sf http://localhost:9090/health` |
| 9273 | metrics-manager | Prometheus exposition (Telegraf) — container-internal only |

