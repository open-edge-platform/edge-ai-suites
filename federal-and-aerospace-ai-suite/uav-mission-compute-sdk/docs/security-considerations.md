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
  starting the stack (see [GETTING_STARTED.md](../GETTING_STARTED.md) and the
  env var reference in [docs/CAMERA-MODES.md](CAMERA-MODES.md)).

## Network Exposure / Port Binding

- All host-published ports (px4, px4-sih, mediamtx, mosquitto, influxdb,
  grafana) bind to `${HOST_IP:-127.0.0.1}` in
  [docker-compose.yml](../docker-compose.yml) — **loopback-only by default**.
- See [docs/PORTS.md](PORTS.md) for the full inventory of host-exposed vs.
  internal-only ports.
- Grafana is intended **only for simulation visualization when the drone is
  grounded** (see [docs/PORTS.md](PORTS.md)).

## Ethernet / Remote Flight Controller Mode

- [docs/ETHERNET-PX4.md](ETHERNET-PX4.md) carries the most explicit warning in
  the repo: the MAVLink UDP link (port `14541`) and the MQTT broker are
  **unauthenticated and unencrypted by default**.
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
  [docs/ARCHITECTURE.md](ARCHITECTURE.md)). This grants broad host access;
  only run it on trusted hosts.
- `metrics-manager`'s REST API sets `CORS_ORIGINS: "*"` — wide open, but the
  port (`9090`) is container-internal only and not host-published (see
  [docs/PORTS.md](PORTS.md)), so it's not reachable from outside the Docker
  network as shipped.

## Vulnerability Reporting

See [SECURITY.md](../SECURITY.md) for how to report vulnerabilities in this
project to Intel.
