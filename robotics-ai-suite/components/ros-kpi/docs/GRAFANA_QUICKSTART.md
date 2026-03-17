<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# ROS2 KPI Grafana Integration - Quick Reference

## Start Dashboard (3 steps)

```bash
# 1. Start Grafana & Prometheus
make grafana-start

# 2. Start monitoring (new terminal)
make monitor

# 3. Start exporter (new terminal)
make grafana-export

# 4. Open browser
make grafana-open
```

## One-Command Demo

```bash
make grafana-demo
```

## Common Commands

```bash
# Check status
make grafana-status

# View logs
make grafana-logs

# Stop services
make grafana-stop
```

## Manual Setup

```bash
# Start stack
./grafana/start_grafana.sh

# Run monitoring
./monitor_stack.py --session my_session

# Export metrics
./src/prometheus_exporter.py --session-dir monitoring_sessions/my_session
```

## Access Points

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9091
- **Metrics Endpoint**: http://localhost:9090/metrics

## Troubleshooting

**No data in Grafana?**
1. Check exporter is running: `curl http://localhost:9090/metrics`
2. Check Prometheus targets: http://localhost:9091/targets
3. Verify monitoring session has data: `ls monitoring_sessions/*/`

**Port conflicts?**
Edit `grafana/docker-compose.yml` to change ports.

**More help?**
See `docs/GRAFANA_SETUP.md`
