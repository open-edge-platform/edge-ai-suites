<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Command Reference

## Monitoring Modes

| Mode | Tracks | Overhead | Use when |
|------|--------|----------|----------|
| **Thread** (default) | Individual threads (TIDs) | ~5–10% | Debugging, optimization |
| **PID** (`--pid-only`) | Processes only | ~2–3% | Production, long-term runs |

## Quick Reference

| Task | Command | Duration |
|------|---------|----------|
| Quick check | `make quick-check` | 30 s |
| Full monitor | `make monitor` | 60 s |
| Full monitor (PID mode) | `make monitor-pid` | 60 s |
| Monitor specific node | `make monitor NODE=/my_node` | 60 s |
| Extended session | `make monitor-long` | 5 min |
| Graph only | `make graph-only` | 60 s |
| Resources only (threads) | `make resources-threads` | 60 s |
| Resources only (PIDs) | `make resources-pid` | 60 s |
| Remote system | `make monitor-remote REMOTE_IP=<ip>` | 60 s |
| Remote system (PID mode) | `make monitor-remote-pid REMOTE_IP=<ip>` | 60 s |
| Pipeline graph (PNG) | `make pipeline-graph` | — |
| Pipeline graph (session) | `make pipeline-graph SESSION=<name>` | — |
| List sessions | `make list-sessions` | — |
| Re-visualize last session | `make visualize-last` | — |
| Clean all data | `make clean` | — |

All `make` targets accept optional variables: `NODE=`, `DURATION=`, `INTERVAL=`,
`SESSION=`, `REMOTE_IP=`, and `REMOTE_USER=`.

```bash
make monitor NODE=/slam_toolbox DURATION=120 INTERVAL=2
make monitor-remote REMOTE_IP=192.168.1.100 NODE=/slam_toolbox REMOTE_USER=ros
```

## monitor_stack.py

```bash
uv run python src/monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Narrow graph discovery to one node (proc delay measured for all nodes) |
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

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --session my_test --duration 120
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox
uv run python src/monitor_stack.py --resources-only --pid-only --duration 60
```

## ros2_graph_monitor.py

```bash
uv run python src/ros2_graph_monitor.py                           # All nodes
uv run python src/ros2_graph_monitor.py --node /slam_toolbox      # Scope to one node
uv run python src/ros2_graph_monitor.py --node /ctrl --log t.csv  # With CSV logging
uv run python src/ros2_graph_monitor.py --interval 2              # Custom interval
uv run python src/ros2_graph_monitor.py --remote-ip 192.168.1.100
```

## monitor_resources.py

```bash
uv run python src/monitor_resources.py                            # CPU only
uv run python src/monitor_resources.py --memory --threads         # CPU + memory + threads
uv run python src/monitor_resources.py --memory --log out.log     # With logging
uv run python src/monitor_resources.py --list                     # List ROS2 processes
uv run python src/monitor_resources.py --remote-ip 192.168.1.100 --memory
```

## visualize_timing.py

```bash
uv run python src/visualize_timing.py timing.csv --delays --frequencies --output-dir ./plots/
```

| Option | Description |
|--------|-------------|
| `--timestamps` | Message arrival scatter plot |
| `--frequencies` | Topic message rates over time |
| `--delays` | Processing delay over time |
| `--inter-arrival` | Inter-message timing / jitter |
| `--output-dir DIR` | Save plots as PNG (omit to display interactively) |
| `--summary` | Print statistics only, no plots |

## visualize_resources.py

```bash
uv run python src/visualize_resources.py resource.log --cores --heatmap --top 10 --output-dir ./plots/
uv run python src/visualize_resources.py resource.log --summary
```

| Option | Description |
|--------|-------------|
| `--cores` | CPU utilization per core over time |
| `--pids` | CPU utilization per PID/thread (top N) |
| `--heatmap` | Core utilization heatmap |
| `--mapping` | Thread-to-core scatter plot |
| `--top N` | Number of top threads to show (default: 10) |
| `--output-dir DIR` | Save plots as PNG |
| `--summary` | Print statistics only, no plots |

> **Note:** `pidstat` reports CPU% where 100% = 1 full core. On a 20-core
> system the maximum is 2000%. Use the **Avg Cores** column in `--summary`
> output for a human-readable reading.

## visualize_graph.py

Renders the ROS2 computation graph as a directed topology diagram.

```bash
# Headless PNG
uv run python src/visualize_graph.py monitoring_sessions/<name> --no-show --output graph.png

# Interactive (click nodes to see topic detail popups)
uv run python src/visualize_graph.py monitoring_sessions/<name> --show
```

Or via make:

```bash
make pipeline-graph
make pipeline-graph SESSION=20260306_154140
```

## Grafana Dashboard Commands

| Command | Description |
|---------|-------------|
| `make grafana-start` | Start Grafana + Prometheus (Docker) |
| `make grafana-stop` | Stop the stack |
| `make grafana-status` | Check services — shows URL http://localhost:30000 |
| `make grafana-export SESSION=<name>` | Export session metrics to Prometheus |
| `make grafana-export-live` | Continuously export live monitoring data |
| `make grafana-open` | Open dashboard in browser |

Metrics are exposed on **port 9092** (Prometheus occupies 9090 in
host-network mode). Prometheus is pre-configured to scrape `localhost:9092`.

## Remote Monitoring

| Component | How it works |
|-----------|-------------|
| Graph monitor | DDS peer discovery via `CYCLONEDDS_URI` / `ROS_STATIC_PEERS` |
| Resource monitor | Runs `ps` and `pidstat` over SSH |

Results are stored and visualized **locally** on the monitoring machine.

```bash
make monitor-remote REMOTE_IP=192.168.1.100
make monitor-remote REMOTE_IP=192.168.1.100 REMOTE_USER=ros NODE=/slam_toolbox
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --pid-only --duration 120
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No ROS2 processes found | Run `ros2 node list` to verify nodes are up |
| Monitor exits immediately | Source ROS2: `source /opt/ros/humble/setup.bash` |
| Visualizations not generated | Run `make visualize-last` manually |
| Permission denied | Run `uv sync` if modules are missing |
| Remote: no data | Check SSH auth and matching `ROS_DOMAIN_ID` |
| CPU shows e.g. "563%" | Normal — 100% = 1 core. Check **Avg Cores** column. |
| `grafana-export` port in use | `fuser -k 9092/tcp && make grafana-export SESSION=<name>` |
| Graph click does nothing | Use `--show` flag to enable TkAgg interactive mode |
