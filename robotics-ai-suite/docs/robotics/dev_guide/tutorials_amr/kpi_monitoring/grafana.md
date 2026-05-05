<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Grafana Dashboard

The ROS2 KPI toolkit integrates with **Grafana** and **Prometheus** to provide
real-time and historical visualization of ROS2 metrics — topic frequencies,
processing delays, CPU/memory usage, and more.

## Prerequisites

Complete the [KPI Framework Installation Guide](installation.md) before continuing.

Install Docker and Docker Compose:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER   # log out and back in after this
```

## Quick Start (3 Steps)

```bash
# 1. Start Grafana and Prometheus
make grafana-start

# 2. In a new terminal — run monitoring
uv run python src/monitor_stack.py

# 3. In a new terminal — start the metrics exporter
make grafana-export SESSION=<session-name-from-step-2>

# Open browser
make grafana-open   # → http://localhost:30000
```

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:30000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Metrics endpoint | http://localhost:9092/metrics | — |

> **Note:** The exporter uses **port 9092** because Prometheus runs in
> host-network mode and binds port 9090 itself.

## Dashboard Panels

### Topic Message Frequencies
Line chart showing message rates (Hz) for all topics over time. Color-coded by
topic with separate lines for input/output.

### Processing Delays
Input→output processing delays in milliseconds with threshold indicators
(green/yellow/red) to identify bottlenecks.

### Inter-Message Timing (Jitter)
Track timing consistency between messages to detect irregular patterns or
network issues.

### CPU and Memory Usage
Real-time CPU usage gauges per process/thread, and stacked-area memory charts
to track consumption and detect leaks.

### I/O Throughput
Bidirectional I/O visualization — read rates above baseline, write rates below.

### Node Detail — `$node`
Select any node from the dashboard dropdown to see two table panels:

- **Publishes**: topic, frequency (Hz), latency (ms), message count
- **Subscribes**: same layout for input topics
- Latency cells color-coded: green < 20 ms, yellow < 100 ms, red ≥ 100 ms

## Common Commands

```bash
make grafana-start              # Start Grafana + Prometheus
make grafana-status             # Check running services
make grafana-logs               # View service logs
make grafana-stop               # Stop services
make grafana-export SESSION=<name>      # Export a completed session
make grafana-export-live                # Continuous live export
```

Manual operation:

```bash
# Start the stack
./grafana/start_grafana.sh

# Export a session
uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/<name>

# Or run live
uv run python src/prometheus_exporter.py --live
```

## Configuration

### Change the Exporter Port

```bash
uv run python src/prometheus_exporter.py --port 9095 --session-dir monitoring_sessions/latest
```

Then update `prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'ros2-kpi'
    static_configs:
      - targets: ['localhost:9095']
```

Restart Prometheus: `docker restart ros2-prometheus`

### Change Scrape Interval

Edit `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 10s   # default: 5s
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No data in Grafana | Check exporter: `curl http://localhost:9092/metrics` |
| Prometheus not scraping | Check targets: http://localhost:9090/targets |
| No session data | Verify: `ls monitoring_sessions/*/` |
| Port 9092 in use | `fuser -k 9092/tcp && make grafana-export SESSION=<name>` |
| Port conflicts | Edit `grafana/docker-compose.yml` to change ports |
