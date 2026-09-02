
<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Getting Started

## Prerequisites

- Docker Engine 24+ with Docker Compose v2
- Intel GPU (Arc / iGPU) with drivers installed
- 16 GB RAM, 20 GB free disk space

### Install Docker and Docker Compose v2 (Ubuntu or Debian)

If Docker is not installed yet, run:

```bash
sudo apt update
sudo apt install -y docker.io
sudo apt install -y docker-compose-v2
sudo usermod -aG docker "$USER"
newgrp docker
```

### Optional: Configure Docker daemon proxy (corporate networks)

If your environment requires HTTP or HTTPS proxy access for Docker pulls/builds,
configure a systemd drop-in for the Docker service:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d

sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf >/dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080"
Environment="HTTPS_PROXY=http://proxy.example.com:8080"
Environment="NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,192.168.0.0/16,.local,.internal"
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
```

Replace `proxy.example.com:8080` and `NO_PROXY` with values for your environment.

Verify Docker is ready:
```bash
docker compose version   # must be v2
docker info | grep -i gpu
```

## Launch the Stack

### Step 0 — Configure credentials

Initialize the environment file and review the passwords and tokens before starting:

```bash
make init
```

All required credentials (`INFLUXDB_PASSWORD`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `GRAFANA_PASSWORD`, and `UAV_ID`) are automatically populated in `.env`. You can update them as needed.

> **Login username** — both Grafana and InfluxDB use the username `admin`
> (hardcoded in `docker-compose.yml`, not set via `.env`).

### Step 1 — Choose camera source (sim or USB)

Choose **one camera bridge mode** before starting. Both cannot run simultaneously.

**See [camera-modes.md](camera-modes.md)** for detailed guide on each mode, configuration, and troubleshooting.

#### Option A: Simulated Cameras (Gazebo) — Default

For development and testing without hardware:

```bash
# 1. Use default .env (if starting fresh)
make init

# 2. Start with simulated cameras
make up-sim-camera
```

Features:
- 3 cameras: nadir, forward, rear (416×416 @20fps)
- No hardware required
- Gazebo Harmonic simulator with vehicle physics

#### Option B: Real USB Camera

For real hardware field deployment:

```bash
# 1. Enumerate USB video devices
v4l2-ctl --list-devices

# 2. Update .env with your device
# Example output: C922 Pro Stream Webcam: /dev/video32
cp .env.example .env
nano .env
```

Set these variables in `.env`:

```env
# Device path from v4l2-ctl --list-devices above
USB_VIDEO_DEVICE=/dev/video32

# Which camera ID to publish as (must be one of: nadir, forward, rear)
USB_CAMERA_ID=nadir

# Capture parameters (should match your camera's native format)
USB_CAPTURE_WIDTH=1280
USB_CAPTURE_HEIGHT=720
USB_SENSOR_FPS=30
USB_CAPTURE_FORMAT=mjpeg       # Most USB cameras support MJPEG

# Only processes this one camera
VISION_CAMERA_IDS=nadir
```

Then start with USB camera profile:

```bash
# 3. Start with USB camera
make up-usb-camera
```

### Step 2 — Start core infrastructure

Once you've chosen a camera mode and configured `.env`, start the core PX4 + camera bridge stack:

**For Gazebo (simulated cameras)**:
```bash
make up-sim-camera
```

**For USB camera**:
```bash
make up-usb-camera
```

USB camera mode uses a lightweight PX4 SIH runtime (px4io/px4-sitl) instead of the Gazebo PX4 image.

**Both modes**:
- Start PX4 autopilot simulation
- Start appropriate camera bridge (sim or USB)
- Start companion telemetry bridge
- Start MQTT broker and MediaMTX RTSP server
- All shared infrastructure (InfluxDB, Grafana, metrics) starts automatically

First run builds all images (~10–15 min). Subsequent starts take ~30 seconds.

**Rebuilding without cache** — if base images, apt packages, or Dockerfile layers
need a clean rebuild (e.g. after a proxy change or stale dependency issue):
```bash
make build-nc   # rebuilds core infra + apps images with --no-cache
make up-sim-camera         # or make up-usb-camera
```

## Arm the UAV (activate cameras)

Cameras only stream when the UAV is armed:

```bash
curl -X POST http://localhost:8080/action/arm
```

## Troubleshooting

**USB camera not found** — verify your device path and update `.env`:
```bash
v4l2-ctl --list-devices
# Find your camera, update USB_VIDEO_DEVICE in .env, then restart
```

**No camera frames**:
- **If `VISION_CAMERA_IDS` doesn't match available cameras**, update `.env` and restart:
  ```bash
  nano .env                          # Fix VISION_CAMERA_IDS
  make down
  make up-sim-camera                 # or make up-usb-camera
  ```

**Cameras switching between modes fails**:
1. Ensure you ran `make down` to stop everything
2. Update `.env` with the new camera mode settings
3. Start fresh with appropriate `make up-sim-camera` or `make up-usb-camera`

**Camera frames stall/lag**:
- Check RTSP streams are being published:
  ```bash
  docker logs mediamtx | grep -E "rtsp.*announce|connected"
  ```

**No camera frames / RTSP 404** — UAV is not armed. Camera bridges only push RTSP streams while armed — streams disappear from MediaMTX when disarmed:
```bash
curl -X POST http://localhost:8080/action/arm
```

**PX4 restarted or camera bridge crashed** — reconnect bridges:
```bash
# Sim camera mode
docker compose restart companion-bridge camera-bridge

# USB camera mode
docker compose restart companion-bridge usb-camera-bridge
```

**Check logs**:
```bash
# Core infrastructure
docker logs px4-gazebo --tail 50
docker logs camera-bridge --tail 30          # Sim mode
docker logs usb-camera-bridge --tail 30      # USB mode

# Or follow all logs in real-time
make logs-infra    # Infrastructure
```

**Switching camera modes**:
See [camera-modes.md](camera-modes.md) → "Switching Between Modes" for step-by-step procedures.

## Ports

| Service | URL | Purpose |
|---|---|---|
| REST API (arm/takeoff/land) | http://localhost:8080 | Command interface for UAV control |
| MQTT broker | localhost:1884 | Publish/subscribe for telemetry + detections |
| Grafana dashboards | http://localhost:3000 | System metrics + performance monitoring |

---

## Quick Reference

### Development Workflows

**First-time setup**:
```bash
cd ~/edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk
make init           # Detect GPU, create .env
make up-sim-camera             # Start with simulated cameras
```

**Switch to USB camera**:
```bash
v4l2-ctl --list-devices              # Find your camera
nano .env                            # Update USB_VIDEO_DEVICE, VISION_CAMERA_IDS=nadir
make down && make up-usb-camera
```

**Switch back to sim**:
```bash
nano .env                            # Update VISION_CAMERA_IDS=nadir,forward,rear
make down && make up-sim-camera
```

**View RTSP streams directly**:
```bash
# Install ffmpeg if needed: sudo apt install ffmpeg
ffplay rtsp://localhost:8554/uav-1/nadir           # Raw feed (needs a local display)

# Headless alternative — record N seconds to a file instead of live-viewing
ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/uav-1/nadir -t 10 -c:v copy nadir.mkv
```

**Monitor system in real-time**:
```bash
make logs-infra              # Infrastructure (PX4, bridges, MQTT, etc)
docker compose ps            # Check container status
```

### Key Files for Developers

| Path | Purpose |
|------|---------|
| [camera-modes.md](camera-modes.md) | Complete camera modes guide (sim vs USB) |
| [how-it-works.md](how-it-works.md) | System design, data flows, component details |
| [../../Makefile](../../Makefile) | Build targets and task automation |
| [../../docker-compose.yml](../../docker-compose.yml) | Infrastructure services, profiles, networking |
| [../../sample-apps/docker-compose.yml](../../sample-apps/docker-compose.yml) | AI helper + dashboard services |
| [../../.env.example](../../.env.example) | All configurable environment variables |
| [../../infra/bridges/camera/](../../infra/bridges/camera/) | Gazebo camera source code (sim mode) |
| [../../infra/bridges/usb-camera/](../../infra/bridges/usb-camera/) | USB camera source code (real hardware) |
| [../../mcp-server/](../../mcp-server/) | Model Context Protocol server for integrations |
