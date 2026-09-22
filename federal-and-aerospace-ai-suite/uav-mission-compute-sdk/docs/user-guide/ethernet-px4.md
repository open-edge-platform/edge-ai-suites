<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Real Hardware — PX4 over Ethernet

> **Evaluation Only** — The PX4 simulation deployment over Ethernet
> (`docker-compose.ethernet.yml`) is provided solely to simplify evaluation.
> This setup is intended only for validating companion compute capabilities.
> It is **not intended for production deployments**.

How to replace the local Gazebo simulation with a PX4 flight controller
running on a separate machine connected over Ethernet.

## Concept

Instead of running PX4 + Gazebo locally, the FC (flight controller) runs on a
**separate machine** on the same Ethernet subnet. A `mavlink-router` container
on the FC machine forwards the PX4 MAVLink stream to the companion computer over
UDP. The `companion-bridge` service on the companion computer connects to that
IP and port — everything upstream (MQTT, dashboards, sample apps) is unchanged.

```
FC Machine (<FC_IP>)                         Companion Machine (<COMPANION_IP>)
┌────────────────────────────┐               ┌─────────────────────────────────┐
│  px4 + Gazebo               │               │  companion-bridge                │
│    ↓ MAVLink :14540 UDP    │               │  mavsdk udpout://<FC_IP>:14541  │
│  mavlink-router            │  :14541 UDP   │    ↓                            │
│    ├─ Server :14540 ← PX4  │ ───────────►  │  Telemetry cache                │
│    └─ Server :14541        │ ◄───────────  │    ↓                            │
└────────────────────────────┘               │  MQTT + REST :8080               │
                                             └─────────────────────────────────┘
```

> **Network requirement**: both machines must be on the **same L2 subnet**
> (e.g. `192.168.1.0/24`). Cross-subnet UDP is blocked by corporate ACL policy.

> **Security recommendation**: the MAVLink UDP link (port `14541`) and the
> MQTT broker are unauthenticated and unencrypted by default. Since traffic
> now crosses a physical network between two machines instead of staying
> inside a single Docker host, it is recommended to enable authentication
> and encryption (e.g. a VPN/IPsec tunnel or link-layer encryption between
> the FC and companion machines, plus MQTT TLS + credentials) before using
> this setup outside of a fully trusted, isolated lab network.

---

## Prerequisites

- Two Linux machines on the same Ethernet subnet
- Docker Engine 24+ on both machines
- **Docker Compose v2 plugin on the FC machine** (`docker compose version` must work)
  ```bash
  # Install on FC machine if missing:
  sudo apt-get install -y docker-compose-plugin
  ```
- **FC machine user must be in the `docker` group**
  ```bash
  # Run on FC machine if missing:
  sudo usermod -aG docker $USER && newgrp docker
  ```
- SSH access from companion → FC machine (for the deploy script)
- If behind a corporate proxy, set `HTTP_PROXY` / `HTTPS_PROXY` before building

---

## Port Reference

| Port     | Protocol       | Machines                  | Purpose                              |
|----------|----------------|---------------------------|--------------------------------------|
| `14540`  | MAVLink v2 UDP | PX4 → mavlink-router      | PX4 onboard MAVLink output           |
| `14541`  | MAVLink v2 UDP | mavlink-router ↔ bridge   | Ethernet link to companion computer  |
| `8080`   | HTTP REST      | bridge → clients          | Companion REST API                   |

> Port `14541` is used (not `14550`) because PX4 internally binds its GCS stream
> to `localhost:14550`, which would conflict with mavlink-router if both used the
> same port.

---

## Step 1 — Deploy to the FC Machine

The `infra/px4-sim/` directory contains the same PX4 + Gazebo image used for
local simulation. On the FC machine it runs the same stack; mavlink-router
bridges PX4’s localhost MAVLink out to the network on port 14541.
Skip this step if using real hardware that already runs PX4 with mavlink-router.

**Option A — Automated deploy script** (run from companion machine):
```bash
bash infra/scripts/deploy_remote.sh <FC_IP> <FC_USER>
# e.g. bash infra/scripts/deploy_remote.sh 192.168.1.100 user
# Enter 'y' when prompted — scp + ssh handled automatically
```

**Option B — Manual deploy**:
```bash
# Create the target directory on the FC machine first
ssh <FC_USER>@<FC_IP> "mkdir -p ~/px4-sim"

# Copy files to FC machine
scp -r infra/px4-sim/ <FC_USER>@<FC_IP>:~/px4-sim/

# SSH in and start
ssh <FC_USER>@<FC_IP>
cd ~/px4-sim
docker compose up -d --build
```

Verify mavlink-router is routing:
```bash
docker logs mavlink-router 2>&1 | tail -10
```
Expected:
```
mavlink-router version 2362c62
Opened UDP Server [4]px4: 0.0.0.0:14540
Opened UDP Server [5]companion: 0.0.0.0:14541
```

---

## Step 2 — Start the Stack in Ethernet Mode

The main `docker-compose.yml` is extended by `docker-compose.ethernet.yml` which:
- Disables `px4` and `camera-bridge` (no local Gazebo sim)
- Switches `companion-bridge` to `network_mode: host` and `PX4_ADDRESS=udpout://FC_IP:14541`

```bash
export FC_IP=192.168.1.100   # IP of FC machine running mavlink-router

make init                    # Create .env and detect GPU (skip if already run)

# Option A — Makefile shortcut (also brings up InfluxDB/Grafana)
make up-ethernet FC_IP=$FC_IP

# Option B — Docker Compose directly
# --profile ethernet activates companion-bridge; add --profile observability for Grafana/InfluxDB
docker compose -f docker-compose.yml -f docker-compose.ethernet.yml --profile ethernet --profile observability up -d --build
docker logs companion-bridge -f
```

Expected logs:
```
INFO  Connecting to udpout://192.168.1.100:14541 (attempt 1)
INFO  PX4 connected!
```

All configurable environment variables:

| Variable     | Default    | Description                              |
|--------------|------------|------------------------------------------|
| `FC_IP`      | required   | FC machine IP — **must be set**          |
| `UAV_ID`   | `uav-1`  | UAV identifier for MQTT topics         |
| `LOG_LEVEL`  | `INFO`     | Logging level (DEBUG / INFO)             |
| `HTTP_PROXY` | _(empty)_  | Build-time proxy (if required)           |

---

## Step 3 — Verify the Connection

```bash
# Smoke test — checks /health, /telemetry, /openapi.json
bash infra/scripts/test_api.sh http://localhost:8080
```

Expected:
```json
{ "status": "ok", "connected": true }
```

Full telemetry snapshot:
```bash
curl -s http://localhost:8080/telemetry | python3 -m json.tool
```
```json
{
    "connected": true,
    "armed": false,
    "mode": "HOLD",
    "stale": false,
    "flight_time_s": 0.0,
    "timestamp": "2026-08-19T11:03:01.765218+00:00",
    "home_lat": 37.4121731,
    "home_lon": -121.9988787,
    "home_alt_msl": 38.196
}
```
Position, velocity, attitude, battery, and GPS data are published to MQTT
(`uav/<id>/telemetry/*`), not to this REST endpoint.

---

## REST API Reference

Base URL: `http://<COMPANION_IP>:8080`

### Telemetry

| Method | Endpoint     | Description                                   |
|--------|--------------|-----------------------------------------------|
| GET    | `/health`    | `{"status":"ok","connected":bool}`            |
| GET    | `/telemetry` | Full state snapshot (position, attitude, etc) |

### Commands

| Method | Endpoint             | Description                          |
|--------|-----------------------|--------------------------------------|
| POST   | `/action/arm`        | Arm the UAV                          |
| POST   | `/action/disarm`     | Disarm the UAV                       |
| POST   | `/action/takeoff`    | Arm + takeoff (`altitude` in body)   |
| POST   | `/action/land`       | Land in place                        |
| POST   | `/action/return`     | Return to launch                     |

Example:
```bash
curl -X POST http://localhost:8080/action/takeoff
```

---

## mavlink-router Config Reference

Located at `infra/px4-sim/mavlink-router/main.conf`:

```ini
[General]
TcpServerPort=0           # TCP disabled — UDP only

[UdpEndpoint px4]
Mode=Server               # Listens for PX4 MAVLink stream
Address=0.0.0.0
Port=14540

[UdpEndpoint companion]
Mode=Server               # Listens for companion bridge connection
Address=0.0.0.0
Port=14541
```

To add a GCS (QGroundControl) connection, append:
```ini
[UdpEndpoint gcs]
Mode=Normal
Address=<GCS_IP>
Port=14550
```

---

## FC Machine — PX4 + Gazebo

The `infra/px4-sim/docker-compose.yml` deploys the same PX4 + Gazebo Harmonic
image used locally. The FC machine requires an Intel GPU and Docker Engine 24+.

---

## Project Structure

```
infra/px4-sim/                      # PX4 + Gazebo image (local and remote)
├── Dockerfile                      # Builds PX4 v1.17.0 with Gazebo Harmonic
├── start_px4.sh                    # Launches PX4 SITL + Gazebo
├── docker-compose.yml              # Remote FC deployment (px4 + mavlink-router)
├── mavlink-router/
│   ├── Dockerfile                  # Builds mavlink-router from source
│   └── main.conf                   # UDP endpoint config
├── models/                         # Gazebo camera models
└── worlds/                         # Gazebo worlds

infra/scripts/
├── deploy_remote.sh                # scp + ssh deploy helper (copies px4-sim/)
└── test_api.sh                     # Companion REST API smoke test
```

---

## Troubleshooting

**Bridge logs show `Connection failed` repeatedly**
- Verify FC machine is reachable: `nc -uvz <FC_IP> 14541`
- Check both machines are on the same subnet: `ip route`
- Confirm mavlink-router is running: `docker ps && docker logs mavlink-router`

**`connected: false` in `/health`**
- PX4 may still be initialising — wait 15–20s after `docker compose up`
- Check bridge logs: `docker logs companion-bridge | grep -i connect`

**`Connection refused` on MQTT in companion-bridge logs**
- In ethernet mode, `companion-bridge` runs with `network_mode: host` and must
  reach mosquitto via the published host port (`1884`), not the container port (`1883`).
  The ethernet override already sets `MQTT_BROKER_PORT=1884` — verify it is applied:
  `docker inspect companion-bridge | grep MQTT_BROKER_PORT`

**`FC_IP must be set` error on bridge startup**
- Set the variable before starting: `export FC_IP=<FC_IP> && docker compose up -d`

**`docker compose build` fails on FC machine**
- Set `HTTP_PROXY` / `HTTPS_PROXY` before building if behind a corporate proxy
- mavlink-router builds from source (Ubuntu 22.04) — requires internet on first build

**Port 14541 unreachable**
- Allow the port: `sudo ufw allow 14541/udp` on FC machine
- `network_mode: host` is required on both sides — bridge networking will not work
