<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Getting Started

## Prerequisites

- Docker Engine 24+ with Docker Compose v2
- Intel GPU (Arc / iGPU) with drivers installed
- 16 GB RAM, 20 GB free disk space

Verify Docker is ready:
```bash
docker compose version   # must be v2
docker info | grep -i gpu
```

## Launch the Stack

### Step 0 — Configure credentials

Copy the example environment file and set your own passwords/tokens before starting:

```bash
make init
# or manually:
cp .env.example .env
```

Then edit `.env`:

```env
# InfluxDB admin password and API token
INFLUXDB_PASSWORD=your-strong-password
INFLUXDB_TOKEN=your-long-random-token

# Grafana admin password
GRAFANA_PASSWORD=your-strong-password

# UAV identifier used in MQTT topics (optional, default: uav-1)
UAV_ID=uav-1
```

> **Note** — `.env` is gitignored and never committed. If you skip this step, Docker Compose falls back to the placeholder defaults (`change-me`) which work for local development but should not be used in any shared or networked environment.

### Step 1 — Start core infrastructure

```bash
make up
```

First run builds all images (~10–15 min). Subsequent starts take ~30 seconds.

**Rebuilding without cache** — if base images, apt packages, or Dockerfile layers
need a clean rebuild (e.g. after a proxy change or stale dependency issue):
```bash
make build-nc   # rebuilds core infra + apps images with --no-cache
make up         # then start as usual
```

### Step 2 — Wait for PX4 to be healthy

```bash
docker compose ps px4
```

Wait until status shows `(healthy)` — takes ~60–90 seconds.

### Step 3 — Start AI helpers + sample apps

```bash
make apps
```

Open **http://localhost:5002**

The dashboard shows all three camera feeds (nadir, forward, rear) with live vehicle detections once the UAV is armed.

## Arm the UAV (activate cameras)

Cameras only stream when the UAV is armed. Arm it from the dashboard or:

```bash
curl -X POST http://localhost:8080/action/arm
```

## Troubleshooting

**App keeps restarting** — infra stack isn't up yet. Start Step 1 first, wait for healthy, then Step 3.

**No camera frames** — UAV is not armed. Use the arm button in the dashboard or the curl command above.

**PX4 restarted** — bridges lose connection. Reconnect them:
```bash
docker compose restart companion-bridge camera-bridge
```

**Check logs**:
```bash
docker logs px4-gazebo --tail 50
docker logs edge-ai-showcase --tail 30
docker logs vision-processor-multicam --tail 30
```

## Ports

| Service | URL |
|---|---|
| Edge AI Showcase | http://localhost:5002 |
| REST API (arm/takeoff/land) | http://localhost:8080 |
| MQTT broker | localhost:1884 |
| Grafana dashboards | http://localhost:3000 |
