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
| Monitor + Intel GPU | `make monitor-gpu` | 60s |
| Monitor specific node | `make monitor NODE=/my_node` | 60s |
| Graph only | `make graph-only` | 60s |
| Resources only (threads) | `make resources-threads` | 60s |
| Resources only (PIDs) | `make resources-pid` | 60s |
| Remote system | `make monitor-remote REMOTE_IP=<ip>` | 60s |
| Remote + GPU | `make monitor-remote REMOTE_IP=<ip> GPU=1` | 60s |
| Remote + NPU | `make monitor-remote REMOTE_IP=<ip> NPU=1` | 60s |
| Remote system, PID mode | `make monitor-remote-pid REMOTE_IP=<ip>` | 60s |
| Repeat remote runs | `make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3` | N×60s |
| PicknPlace single run | `make picknplace` | demo |
| PicknPlace repeat runs | `make picknplace-repeat REPEAT=3` | N×demo |
| Pipeline graph (PNG) | `make pipeline-graph` | — |
| Pipeline graph (specific) | `make pipeline-graph SESSION=<name>` | — |
| Pipeline graph (algorithm) | `make pipeline-graph ALGORITHM=<name>` | — |
| Visualize GPU session | `make visualize-gpu` | — |
| Visualize NPU session | `make visualize-npu` | — |
| Average KPIs (last 5) | `make view-average` | — |
| Average KPIs (N runs) | `make view-average RUNS=<n>` | — |
| Average plots | `make view-average-plot RUNS=<n>` | — |
| Export to Grafana | `make grafana-export SESSION=<name>` | — |
| Export latest to Grafana | `make grafana-export` | — |
| Live Grafana export | `make grafana-export-live` | — |
| List sessions | `make list-sessions` | — |
| Re-visualize last session | `make visualize-last` | — |
| Re-visualize (algorithm) | `make visualize-last ALGORITHM=<name>` | — |
| GPU PID snapshot | `make gpu-pids` | — |
| GPU PID live watch | `make gpu-pids-watch` | — |
| GPU PID to CSV (60s) | `make gpu-pids-csv` | 60s |
| Check dependencies | `make check-deps` | — |
| Check domain IDs | `make check-domain REMOTE_IP=<ip>` | — |
| Clean all data | `make clean` | — |

---

## monitor_stack.py Options

```bash
./monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Narrow graph discovery to one node (proc delay measured for all nodes regardless) |
| `--session NAME` | Name for this session (default: timestamp) |
| `--algorithm NAME` | Group session under `monitoring_sessions/<name>/` |
| `--duration SECS` | Auto-stop after N seconds |
| `--interval SECS` | Update interval (default: 5) |
| `--output-dir PATH` | Where to save results |
| `--graph-only` | Skip resource monitoring |
| `--resources-only` | Skip graph monitoring |
| `--pid-only` | Process-level only, no thread details |
| `--no-visualize` | Skip auto-visualization on exit |
| `--remote-ip IP` | Monitor a remote machine |
| `--remote-user USER` | SSH user for remote machine (default: ubuntu) |
| `--ros-domain-id ID` | Override `ROS_DOMAIN_ID` for the session |
| `--gpu` | Collect Intel GPU metrics via `intel_gpu_top` |
| `--npu` | Collect Intel NPU metrics via sysfs |
| `--list-sessions` | List previous sessions and exit |

**Examples:**

```bash
./monitor_stack.py --node /slam_toolbox --session my_test --duration 120
./monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox
./monitor_stack.py --resources-only --pid-only --duration 60
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
./ros2_graph_monitor.py                           # All nodes, proc delay for each
./ros2_graph_monitor.py --node /slam_toolbox      # Scope discovery to one node
./ros2_graph_monitor.py --node /ctrl --log t.csv  # With CSV logging
./ros2_graph_monitor.py --interval 2              # Custom interval
./ros2_graph_monitor.py --remote-ip 192.168.1.100
```

### monitor_resources.py

```bash
./monitor_resources.py                            # CPU only
./monitor_resources.py --memory --threads         # CPU + memory + threads
./monitor_resources.py --memory --log out.log     # With logging
./monitor_resources.py --list                     # List ROS2 processes
./monitor_resources.py --remote-ip 192.168.1.100 --memory
```

### visualize_timing.py

```bash
./visualize_timing.py timing.csv --delays --frequencies --output-dir ./plots/
```

### visualize_resources.py

```bash
./visualize_resources.py resource.log --cores --heatmap --top 10 --output-dir ./plots/
./visualize_resources.py resource.log --summary   # text table only
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
| `make grafana-status` | Check running services |
| `make grafana-open` | Open `http://localhost:3000` in browser |
| `make grafana-export SESSION=<name>` | Serve a session's metrics on port 9092 |
| `make grafana-export` | Same, using the latest session |
| `make grafana-export-live` | Live mode (updates as monitoring runs) |

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
./monitor_stack.py --remote-ip 192.168.1.100 --pid-only --duration 120
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
 <timestamp>/                   # flat layout (no --algorithm)
    session_info.txt
    graph_timing.csv
    graph_topology.json
    resource_usage.log
    gpu_usage.log              # present when --gpu / GPU=1
    npu_usage.log              # present when --npu / NPU=1
    visualizations/
 <algorithm>/                   # grouped layout (--algorithm <name>)
     <timestamp>/
         ...
         average_N/              # after picknplace-repeat / monitor-remote-repeat
```

PicknPlace sessions are always grouped under `monitoring_sessions/picknplace/` because `picknplace_run.sh` passes `--algorithm picknplace`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No ROS2 processes found | Run `ros2 node list` to verify nodes are up |
| Monitor exits immediately | Source ROS2: `source /opt/ros/humble/setup.bash` |
| Visualizations not generated | Run `make visualize-last` manually |
| Permission denied | Run `chmod +x src/*.py monitor_stack.py grafana/*.sh scripts/*.sh` |
| Remote: no data | Check SSH auth and matching `ROS_DOMAIN_ID` |
| CPU shows e.g. "563%" | Normal — `pidstat` reports 100% = 1 core. Check **Avg Cores** column. |
| `grafana-export` port in use | `fuser -k 9092/tcp && make grafana-export SESSION=<name>` |
| Graph click does nothing | Use `--show` flag (not `--no-show`) to enable TkAgg interactive mode |
| GPU log empty | Run `make setup-remote-gpu REMOTE_IP=<ip>` to grant `CAP_PERFMON` |
| NPU log empty | Verify `/sys/class/accel/accel0/` exists on the target machine |

---

## PicknPlace Simulation

```bash
make picknplace                          # Single run
make picknplace-repeat                   # 3 runs, 10s pause (default)
make picknplace-repeat REPEAT=5 PAUSE=15 # Custom repeat count and pause
```

Sessions are saved under `monitoring_sessions/picknplace/<timestamp>/`.
After `picknplace-repeat`, cross-run averages are saved to `monitoring_sessions/picknplace/average_N/`.

Visualize results:
```bash
make visualize-last ALGORITHM=picknplace
make visualize-gpu  ALGORITHM=picknplace
make pipeline-graph ALGORITHM=picknplace
make view-average-plot RUNS=3
```

---

## Intel GPU & NPU Monitoring

### GPU PID Analysis

```bash
make gpu-pids                            # One-shot snapshot
make gpu-pids-watch                      # Live refresh (Ctrl-C to stop)
make gpu-pids-csv                        # 60s capture → CSV
make gpu-pids INTERVAL=1                 # Custom sampling interval
make gpu-pids-remote REMOTE_IP=<ip>      # Remote GPU analysis
```

Collected: Render/3D, Blitter, Video, VE engine busy%, freq (MHz), temp (°C), power (W), per-PID breakdown.

### Enabling PMU (richer metrics)

```bash
# Grant CAP_PERFMON once on the remote machine
make setup-remote-gpu REMOTE_IP=<ip> [REMOTE_USER=<user>]
```

### Monitoring with GPU / NPU

```bash
make monitor-gpu                                              # Local GPU
make monitor-remote REMOTE_IP=<ip> GPU=1                      # Remote GPU
make monitor-remote REMOTE_IP=<ip> NPU=1                      # Remote NPU
make monitor-remote REMOTE_IP=<ip> GPU=1 NPU=1                # Both
make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3 GPU=1 NPU=1 ALGORITHM=slam
```

Visualize:
```bash
make visualize-gpu                       # Latest session GPU dashboard
make visualize-gpu ALGORITHM=<name>      # Latest session for an algorithm
make visualize-npu                       # Latest session NPU dashboard
make visualize-gpu-pid-bar               # Per-PID engine breakdown bar chart
```

---

## Cross-Session Averages (view-average)

```bash
make view-average                        # Timing + resources, last 5 sessions
make view-average RUNS=10                # Last N sessions
make view-average-timing                 # Timing only
make view-average-resources              # Resources only
make view-average-plot                   # Save bar-chart PNGs
make view-average-plot RUNS=10 SHOW=show # Open windows too
# Scope to an algorithm sub-directory:
make view-average ALGORITHM=picknplace RUNS=5
```
