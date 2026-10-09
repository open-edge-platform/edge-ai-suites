<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Security Considerations

This SDK is a development kit and reference solution for evaluating Intel Edge
AI capabilities on UAV platforms. It is **designed for local, single-user
development**. This page consolidates the security-relevant configuration and
recommendations that are otherwise scattered across the repo.

## Scope / Intended Use

- Single-user, local development system (see [README.md](../README.md)).
- Default network exposure is loopback-only; anything beyond that (LAN
  exposure, remote FC over Ethernet) is opt-in and shifts more of the
  responsibility for securing the link onto the operator.

## Secrets Management

- `INFLUXDB_PASSWORD`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, and `GRAFANA_PASSWORD`
  have **no defaults** in [.env.example](../.env.example) and are required via
  `${VAR:?...}` in [docker-compose.yml](../docker-compose.yml) — the stack
  refuses to start until you set real values in `.env`.
- `.env` and `*.secret` are excluded from version control via
  [.gitignore](../.gitignore); never commit real credentials.
- Set strong, unique values for all of the above before running `make init` /
  starting the stack (see [user-guide/get-started.md](user-guide/get-started.md) and the
  env var reference in [user-guide/camera-modes.md](user-guide/camera-modes.md)).

## Network Exposure / Port Binding

- All host-published ports (px4, px4-sih, mediamtx, mosquitto, influxdb,
  grafana) bind to `${HOST_IP:-127.0.0.1}` in
  [docker-compose.yml](../docker-compose.yml) — **loopback-only by default**.
- See [user-guide/ports.md](user-guide/ports.md) for the full inventory of
  host-exposed vs. internal-only ports.
- Grafana is intended **only for simulation visualization when the drone is
  grounded** (see [user-guide/ports.md](user-guide/ports.md)).

## Deployment Scenario — Exposed Ports (Grafana, InfluxDB, etc.)

Grafana, InfluxDB, and the telemetry/MQTT/RTSP services are exposed
differently depending on deployment mode — the Ethernet override widens
exposure for one service beyond what local mode allows.

### Local Host Deployment (default, `docker-compose.yml`)

All host-published ports bind to `${HOST_IP:-127.0.0.1}` — loopback-only.

- Exposed ports: `1884` (MQTT), `8080` (REST API), `8554`/`8888`/`8889`
  (MediaMTX RTSP/HLS/WebRTC), `5002` (edge-ai-showcase), `14540`/`14580` UDP
  (MAVLink), `8086` (InfluxDB, `observability` profile), `3000` (Grafana,
  `observability` profile).
- Full table: [user-guide/ports.md](user-guide/ports.md).

### Ethernet Deployment (`docker-compose.ethernet.yml` override)

- `px4` and `camera-bridge` are disabled entirely — not exposed.
- `mosquitto`, `influxdb`, `grafana` are unchanged from local mode — still
  bound to `${HOST_IP:-127.0.0.1}` (ports `1884`, `8086`, `3000`).
- **`companion-bridge` switches to `network_mode: host`**.
  Host networking bypasses Docker's port-publish/`HOST_IP` scoping entirely,
  so **port `8080` becomes reachable on every network interface of the
  companion machine — not just loopback — even though `HOST_IP` still
  defaults to `127.0.0.1`**. This is wider exposure than local mode and
  should be accounted for (e.g., a host firewall rule) before running
  ethernet mode on a shared or externally reachable machine.

## Ethernet / Remote Flight Controller Mode

- [user-guide/ethernet-px4.md](user-guide/ethernet-px4.md) carries the most
  explicit warning in the repo: the MAVLink UDP link (port `14541`) and the
  MQTT broker are **unauthenticated and unencrypted by default**.
- Once traffic crosses a physical network between two machines (instead of
  staying inside one Docker host), it's recommended to add a VPN/IPsec tunnel
  or link-layer encryption between the FC and companion machines, plus MQTT
  TLS + credentials — unless you're on a fully trusted, isolated lab network.
- [docker-compose.ethernet.yml](../docker-compose.ethernet.yml) runs
  `companion-bridge` with `network_mode: host`, which broadens host network
  exposure compared to the default bridge-networked setup — factor this in
  when deciding whether to enable the `ethernet`/`observability` profiles on a
  shared machine.

## Container Privileges

- `metrics-manager` runs with `privileged: true` and `pid: host` in
  [docker-compose.yml](../docker-compose.yml) — required for GPU/NPU/host
  metrics collection via qmassa/sysfs (see
  [user-guide/how-it-works.md](user-guide/how-it-works.md)). This grants
  broad host access; only run it on trusted hosts.
- `metrics-manager`'s REST API sets `CORS_ORIGINS: "*"` — wide open, but the
  port (`9090`) is container-internal only and not host-published (see
  [user-guide/ports.md](user-guide/ports.md)), so it's not reachable from
  outside the Docker network as shipped.

## Vulnerability Reporting

See [SECURITY.md](../SECURITY.md) for how to report vulnerabilities in this
project to Intel.
