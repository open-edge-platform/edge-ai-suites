<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Benchmarking User Guide

This guide explains how to run and read the MAVLink to MQTT benchmarks in
`benchmarks/benchmark_mavlink_mqtt.py`.

## Prerequisites

- Repository dependencies installed once:

```bash
make deps
```

- Core stack running:

```bash
make up-sim-camera
```

You can also use `make up-usb-camera` or `make up-ethernet FC_IP=<IP>`.

- For benchmark modes that consume telemetry, ensure the UAV is publishing
  telemetry (armed or otherwise active).

## Quick Start

| Mode | Command |
|---|---|
| Passive telemetry observation | `make bench` |
| End-to-end bridge stress sweep | `make bench-bridge-sweep` |
| Client scaling sweep | `make bench-client-sweep` |

## Command Reference

All commands assume `make deps` has been run once.

### 1) Passive telemetry observation

```bash
make bench                                     # 20s window, 1 subscriber
make bench ARGS="--duration 60 --clients 5"    # 60s window, 5 subscribers
```

What it outputs per topic:

- Observed message rate (Hz)
- Average latency
- P99 latency
- Jitter (standard deviation of inter-arrival time)

### 2) Bridge stress sweep

Use this mode to test multiple publish caps in one run.

```bash
make bench-bridge-sweep
make bench-bridge-sweep BRIDGE_SWEEP_RATES="20,50,100,200,300" SWEEP_DURATION=15
```

Direct invocation:

```bash
.venv/bin/python benchmarks/benchmark_mavlink_mqtt.py \
  --bridge-sweep \
  --sweep-rates 20,50,100,200 \
  --sweep-duration 15 \
  --restart-wait 45
```

Optional compose override (repeatable):

```bash
.venv/bin/python benchmarks/benchmark_mavlink_mqtt.py \
  --bridge-sweep \
  --compose-file docker-compose.yml \
  --compose-file docker-compose.ethernet.yml
```

### 3) Client scaling sweep

Use this mode to measure behavior as subscriber count increases.

```bash
make bench-client-sweep
make bench-client-sweep CLIENT_SWEEP_COUNTS="1,2,5,10,25,50,100" SWEEP_DURATION=15
```

## HTML Report

Both the client sweep and bridge sweep benchmarks can write a self-contained HTML report.

For make targets, pass it via `ARGS`:

```bash
make bench-bridge-sweep ARGS="--html-report"
make bench-client-sweep ARGS="--html-report"
make bench-all ARGS="--html-report" # To run both the sweeps and create a combined report
```

```bash
# Auto-named file in current directory
.venv/bin/python benchmarks/benchmark_mavlink_mqtt.py --bridge-sweep --html-report

# Explicit path
.venv/bin/python benchmarks/benchmark_mavlink_mqtt.py --bridge-sweep --html-report /tmp/bench.html
```

Report includes:

- Run metadata (timestamp, broker host/port, UAV ID)
- System summary (host, OS, CPU, memory)
- Deployment health snapshot
- Charts and raw tables for each mode executed

## Key Options

| Option | Default | Description |
|---|---|---|
| `--duration` | `20` | Observation window (seconds) for passive mode |
| `--clients` | `1` | Number of concurrent subscribers in passive mode |
| `--bridge-sweep` | off | Enables bridge stress sweep |
| `--sweep-rates` | `20,50,100,200` | Requested caps for bridge sweep tiers |
| `--sweep-duration` | `10` | Duration per tier (seconds) |
| `--restart-wait` | `30` | Max wait after bridge restart for first telemetry |
| `--client-sweep` | off | Enables scaling sweep across client counts |
| `--client-sweep-counts` | `1,2,5,10,25,50,100` | Client tiers for scaling sweep |
| `--compose-file` | auto-detect | Compose file(s) used for bridge recreate; repeatable |
| `--html-report [PATH]` | off | Write HTML report (auto name if PATH omitted) |

## Environment Variables

These can be set in `.env` or exported in the shell.

| Variable | Default | Notes |
|---|---|---|
| `MQTT_BROKER_HOST` | `localhost` | Broker host |
| `MQTT_BROKER_PORT` | `1884` | Host-mapped broker port |
| `UAV_ID` | `uav-1` | Topic prefix |

CLI flags `--host` and `--port` override env values.

## Interpreting Results

Typical checks:

- Rates should be near configured caps for active telemetry topics.
- Average and P99 latency should stay stable across repeated runs.
- Jitter should remain low and not grow sharply with subscriber count.
- In client sweep mode, high rate CV indicates uneven fan-out delivery.

Suggested healthy baseline (local/loopback environments):

| Metric | Typical target |
|---|---|
| Avg latency | < 5 ms |
| P99 latency | < 20 ms |
| Jitter | < 5 ms |
| Rate CV (multi-client) | < 10% |

Based on the benchmark findings, you can tune the `RATE_*_HZ` environment variables for `companion-bridge` in `docker-compose.yml` and restart the deployment to apply the updated rates.

## Troubleshooting

### No telemetry received

- Verify core services are running:

```bash
make ps
```

- Verify broker reachable on host port:

```bash
docker ps | grep mqtt-broker
```

- Confirm UAV is producing telemetry.

### Bridge sweep fails during companion-bridge recreate

- Ensure `docker compose` is installed and available in `PATH`.
- If running ethernet mode, start with the expected `make up-ethernet FC_IP=<IP>` flow.
- Re-run once after verifying stack health:

```bash
make ps
make logs
```

### USB mode startup fails with missing `/dev/video*`

- If no physical USB camera is attached, use `make up-sim-camera` for benchmarking.
- Benchmark modes that only need telemetry can run without `usb-camera-bridge`.
