<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Ports

## Internal Only by Default

| Port | Service | Description | Authenticated | Encrypted |
|------|---------|-------------|:---:|:---:|
| 1884 | MQTT broker | Telemetry + detections (container port 1883) | No | No |
| 8080 | REST API | UAV commands (arm, takeoff, land, goto) | No | No |
| 8554 | MediaMTX RTSP | Raw + annotated camera streams (rtsp://localhost:8554/uav-1/{camera}[/processed]) | No | No |
| 8888 | MediaMTX HLS | Optional web viewing | No | No |
| 8889 | MediaMTX WebRTC | Optional web viewing | No | No |
| 1935 | MediaMTX RTMP | RTMP ingest (internal: vision-processor pushes annotated streams) | No | No |
| 5002 | edge-ai-showcase | Primary demo dashboard | No | No |
| 14540/udp | MAVLink | PX4 inbound | No | No |
| 14580/udp | MAVLink | PX4 outbound | No | No |

## Docker-Network Only

| Port | Service | Description | Authenticated | Encrypted |
|------|---------|-------------|:---:|:---:|
| 9997 | MediaMTX API | Stream management API (container-internal only) | No | No |
| 9998 | MediaMTX Metrics | Prometheus-compatible — container-internal only | No | No |

## Observability (always on)

> **Note** — Grafana is intended **only for simulation visualization when the drone is grounded**.

| Port | Service | Description | Authenticated | Encrypted |
|------|---------|-------------|:---:|:---:|
| 8086 | InfluxDB | Time-series DB — org: uav-sdk, bucket: telemetry | Yes (API token) | No |
| 3000 | Grafana | Dashboards — admin / uav-sdk | Yes (login) | No |
| 9090 | metrics-manager | REST API + SSE stream — container-internal only; use `docker exec metrics-manager curl -sf http://localhost:9090/health` | No | No |
| 9273 | metrics-manager | Prometheus exposition (Telegraf) — container-internal only | No | No |

