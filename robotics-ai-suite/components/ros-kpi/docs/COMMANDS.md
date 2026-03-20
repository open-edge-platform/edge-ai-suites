<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Command Reference

## Monitoring Modes

| Mode | Tracks | Overhead | Use when |
|------|--------|----------|----------|
| **Thread** (default) | Individual threads (TIDs) | ~5-10% | Debugging, optimization |
| **PID** (`--pid-only`) | Processes only | ~2-3% | Production, long-term |

---

## Quick Reference

| Task | Command | Duration |
|------|---------|----------|
| Quick check | `make quick-check` | 30s |
| Full monitor | `make monitor` | 60s |
| Full monitor, PID mode | `make monitor-pid` | 60s |
| Monitor specific node | `make monitor NODE=/my_node` | 60s |
| Extended session | `make monitor-long` | 5 min |
| Graph only | `make graph-only` | 60s |
| Resources only (threads) | `make resources-threads` | 60s |
| Resources only (PIDs) | `make resources-pid` | 60s |
| Remote system | `make monitor-remote REMOTE_IP=<ip>` | 60s |
| Remote system, PID mode | `make monitor-remote-pid REMOTE_IP=<ip>` | 60s |
| Pipeline graph (PNG) | `make pipeline-graph` | — |
| Pipeline graph (specific) | `make pipeline-graph SESSION=<name>` | — |
| List sessions | `make list-sessions` | — |
| Re-visualize last session | `make visualize-last` | — |
| Clean all data | `make clean` | — |

---

## monitor_stack.py Options

```bash
uv run python src/monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Narrow graph discovery to one node (proc delay measured for all nodes regardless) |
| `--session NAME` | Name for this session (default: timestamp) |
| `--duration SECS` | Auto-stop after N seconds |
| `--interval SECS` | Update interval (default: 5) |
| `--output-dir PATH` | Where to save results |
| `--graph-only` | Skip resource monitoring |
| `--resources-only` | Skip graph monitoring |
| `--pid-only` | Process-level only, no thread details |
| `--no-visualize` | Skip auto-visualization on exit |
| `--remote-ip IP` | Monitor a remote machine |
| `--remote-user USER` | SSH user for remote machine (default: ubuntu) |
| `--list-sessions` | List previous sessions and exit |

**Examples:**

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --session my_test --duration 120
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox
uv run python src/monitor_stack.py --resources-only --pid-only --duration 60
```

---

## Make Targets

All targets accept optional `NODE=`, `DURATION=`, `INTERVAL=`, `SESSION=`,
`REMOTE_IP=`, and `REMOTE_USER=` variables.

```bash
make monitor NODE=/slam_toolbox DURATION=120 INTERVAL=2
make monitor-remote REMOTE_IP=192.168.1.100 NODE=/slam_toolbox REMOTE_USER=ros
```

---

## Individual Scripts

### ros2_graph_monitor.py

```bash
uv run python src/ros2_graph_monitor.py                           # All nodes, proc delay for each
uv run python src/ros2_graph_monitor.py --node /slam_toolbox      # Scope discovery to one node
uv run python src/ros2_graph_monitor.py --node /ctrl --log t.csv  # With CSV logging
uv run python src/ros2_graph_monitor.py --interval 2              # Custom interval
uv run python src/ros2_graph_monitor.py --remote-ip 192.168.1.100
```

### monitor_resources.py

```bash
uv run python src/monitor_resources.py                            # CPU only
uv run python src/monitor_resources.py --memory --threads         # CPU + memory + threads
uv run python src/monitor_resources.py --memory --log out.log     # With logging
uv run python src/monitor_resources.py --list                     # List ROS2 processes
uv run python src/monitor_resources.py --remote-ip 192.168.1.100 --memory
```

### visualize_timing.py

```bash
uv run python src/visualize_timing.py timing.csv --delays --frequencies --output-dir ./plots/
```

### visualize_resources.py

```bash
uv run python src/visualize_resources.py resource.log --cores --heatmap --top 10 --output-dir ./plots/
uv run python src/visualize_resources.py resource.log --summary   # text table only
```

> CPU% scale: 100% = 1 full core. Use the **Avg Cores** column in `--summary` output for a human-readable reading.

### visualize_graph.py

Renders the ROS2 computation graph as a directed topology diagram.

```bash
# Headless PNG
uv run python src/visualize_graph.py monitoring_sessions/<name> --no-show --output graph.png

# Interactive (click nodes to see topic detail popup)
uv run python src/visualize_graph.py monitoring_sessions/<name> --show
```

Or via make:
```bash
make pipeline-graph
make pipeline-graph SESSION=20260306_154140
```

---

## Grafana Dashboard

| Command | Description |
|---------|-------------|
| `make grafana-start` | Start Grafana + Prometheus (Docker) |
| `make grafana-stop` | Stop stack |
| `make grafana-status` | Check running services — shows URL `http://localhost:30000` (admin/admin) |

Metrics are exposed on **port 9092** (Prometheus occupies 9090 in host-network mode). Prometheus is pre-configured to scrape `localhost:9092`.

## Remote Monitoring

Monitor a ROS2 pipeline running on a **separate machine**.

**Requirements:**
- SSH key-based auth to the remote host (passwordless)
- Matching `ROS_DOMAIN_ID` on both machines
- Same RMW (CycloneDDS or FastDDS) installed locally

```bash
make monitor-remote REMOTE_IP=192.168.1.100
make monitor-remote REMOTE_IP=192.168.1.100 REMOTE_USER=ros NODE=/slam_toolbox
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --pid-only --duration 120
```

| Component | How it works |
|-----------|-------------|
| Graph monitor | DDS peer discovery via `CYCLONEDDS_URI` / `ROS_STATIC_PEERS` |
| Resource monitor | Runs `ps` and `pidstat` over SSH |

Results are stored and visualized **locally** on the monitoring machine.

---

## Session Data Layout

```
monitoring_sessions/
└── 20260209_143022/
    ├── session_info.txt
    ├── graph_timing.csv
    ├── resource_usage.log
    └── visualizations/
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No ROS2 processes found | Run `ros2 node list` to verify nodes are up |
| Monitor exits immediately | Source ROS2: `source /opt/ros/humble/setup.bash` |
| Visualizations not generated | Run `make visualize-last` manually |
| Permission denied | Scripts invoke via `uv run python src/...` — run `uv sync` if modules are missing |
| Remote: no data | Check SSH auth and matching `ROS_DOMAIN_ID` |
| CPU shows e.g. "563%" | Normal — `pidstat` reports 100% = 1 core. Check **Avg Cores** column. |
| `grafana-export` port in use | `fuser -k 9092/tcp && make grafana-export SESSION=<name>` |
| Graph click does nothing | Use `--show` flag (not `--no-show`) to enable TkAgg interactive mode |
