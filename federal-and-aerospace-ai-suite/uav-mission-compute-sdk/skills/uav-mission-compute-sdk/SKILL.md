---
name: uav-mission-compute-sdk
description: >
  Operate and troubleshoot the UAV Mission Compute SDK for PX4 telemetry, camera streaming, missions, computer vision, and edge AI demonstrations. USE FOR: SDK setup, infrastructure validation, camera profile switching (sim/USB/RealSense), mission execution, telemetry benchmarking, Ethernet remote PX4 deployment. DO NOT USE FOR: General PX4 flight control beyond MQTT/REST, custom hardware integration details, or production flight planning.
license: Apache-2.0
compatibility: Requires Docker Engine 24+, Docker Compose v2, Python 3.10+, Ubuntu 24.04, Intel GPU recommended
metadata:
  author: Intel Open Edge Platform Team
  tags: uav, px4, mavlink, mqtt, docker
---

# UAV Mission Compute SDK Skill

Operate the UAV Mission Compute SDK for PX4 SITL, camera streaming (sim/USB/RealSense), telemetry, and edge AI demonstrations.

## When to Use This Skill

**Use for**: SDK initialization, infrastructure validation, camera switching, telemetry benchmarking, remote PX4 deployment, AI analytics integration, troubleshooting.

**Do not use for**: General PX4 control beyond REST/MQTT, production flight planning, custom hardware integration.

## Quick Start

```bash
make init                # Initialize .env, detect GPU/RealSense
make up-sim-camera      # Start Gazebo with 3 cameras
/validate-infra         # Confirm all services healthy
curl -X POST http://localhost:8080/action/arm  # Arm UAV
```

## Workflows

### Initialize SDK
```bash
make init  # Creates .env, auto-detects GPU and RealSense devices
```

### Switch Camera Profiles
```bash
/switch-camera-mode sim|usb|realsense  # Atomic teardown + startup
```

**Before USB/RealSense**: Use `v4l2-ctl --list-devices` (USB) or `make init` after plugging in RealSense.

### Validate Infrastructure
```bash
/validate-infra  # Checks PX4, MQTT, bridges, REST, RTSP, telemetry
```

### Capture Frames
```bash
curl -X POST http://localhost:8080/action/arm  # Required: RTSP only when armed
ffmpeg -i rtsp://localhost:8554/uav-1/nadir -frames:v 1 /tmp/frame.jpg -y
```

### Run Benchmarks
```bash
make deps                                    # One-time setup
make bench                                   # Passive telemetry (30s)
make bench-client-sweep                      # Fan-out scaling (1, 5, 10, 25 clients)
make bench-bridge-sweep                      # Stress test (20, 50, 100, 150 Hz)
make bench-all ARGS="--html-report"         # All modes + HTML
```

### Deploy Remote PX4
```bash
export FC_IP=192.168.1.100
make up-ethernet FC_IP=$FC_IP
```

### Recover from PX4 Restart
```bash
docker compose restart px4 mediamtx companion-bridge
/validate-infra
```

### Safe Cleanup
```bash
/cleanup-stack              # Safe: stops apps, runs make clean
make clean-all              # Destructive: removes volumes + images
```

## Key Ports

| Service | Port | Purpose |
|---------|------|---------|
| REST API | :8080 | Arm, takeoff, land |
| MQTT | :1884 | Telemetry + detections |
| RTSP (raw) | :8554 | Camera streams |
| Grafana | :3000 | Dashboards (admin/uav-sdk) |
| InfluxDB | :8086 | Time-series DB |

## Common Fixes

| Issue | Fix |
|-------|-----|
| PX4 unhealthy | `docker compose restart px4` |
| No RTSP streams | Arm first: `curl -X POST http://localhost:8080/action/arm` |
| USB camera not found | Run `v4l2-ctl --list-devices`, verify `/dev/videoX` |
| RealSense not detected | Run `make init` after plugging in camera |
| Stale containers | `docker compose restart px4 mediamtx companion-bridge` |

## References

- [CLAUDE.md](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/CLAUDE.md) — MQTT topics, RTSP paths, ports, gotchas
- [docs/user-guide/](https://github.com/open-edge-platform/edge-ai-suites/tree/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide) — Detailed procedures
- [docs/user-guide/benchmarking.md](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/benchmarking.md) — Benchmark methodology
- [docs/user-guide/ethernet-px4.md](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/ethernet-px4.md) — Remote PX4 setup
- [docs/user-guide/ports.md](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/ports.md) — All ports and endpoints
