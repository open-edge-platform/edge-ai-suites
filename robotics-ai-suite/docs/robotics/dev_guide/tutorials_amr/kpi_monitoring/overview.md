<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# ROS2 KPI Monitoring Overview

Monitor, analyze, and visualize Key Performance Indicators in ROS2 systems —
node latencies, CPU/memory usage, message flow, and thread-level resource
distribution.

## Features

- Real-time ROS2 graph monitoring: nodes, topics, message rates, processing delays
- Automatic **per-node** input→output processing delay for every node in the graph (no `--node` flag required)
- CPU, memory, and I/O monitoring via `pidstat` (thread-level or PID-only)
- Cross-machine monitoring via `--remote-ip` (DDS peer discovery + SSH)
- Interactive visualizations: heatmaps, timelines, core utilization, scatter plots
- ROS bag analysis with latency tracking and CPU-cycle estimation
- Organized session output with auto-generated visualizations

## Prerequisites

| Requirement | Details |
|-------------|---------|
| ROS2 Humble / Jazzy | See [Getting Started](../../gsg_robot/index.md) |
| Python 3.8+ | Included with Ubuntu 22.04+ |
| `pidstat` | `sudo apt-get install sysstat` |
| `psutil`, `matplotlib`, `numpy` | Installed via `uv sync` |

## Architecture

The monitoring stack uses a two-layer design:

```
                    ┌──────────────────────────────────┐
                    │     ROS2 System (Local/Remote)   │
                    │  Node A   Node B   Node C ...    │
                    └──────────┬──────────┬────────────┘
                               │ DDS      │ SSH
                    ┌──────────▼──────────▼────────────┐
                    │        Monitoring Stack          │
                    │  monitor_stack.py (Orchestrator) │
                    │  ├── ros2_graph_monitor.py       │
                    │  │       → graph_timing.csv      │
                    │  └── monitor_resources.py        │
                    │          → resource_usage.log    │
                    │  Auto-Visualization on exit      │
                    └──────────────────────────────────┘
```

**`monitor_stack.py`** orchestrates both monitors and saves all output to a
dated session folder, then auto-generates visualizations on exit.

**`ros2_graph_monitor.py`** subscribes to all ROS2 topics, measures message
rates and per-node input→output processing delays for every node in the graph,
and logs timing data to CSV.

**`monitor_resources.py`** detects ROS2 processes and uses `pidstat` to sample
CPU, memory, and I/O statistics at thread or process level.

## Scripts Overview

### monitor_stack.py — Unified Entry Point

```bash
uv run python src/monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Monitor a specific node (e.g. `/slam_toolbox`) |
| `--session NAME` | Session label (default: timestamp) |
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

### ros2_graph_monitor.py — Graph and Latency Monitor

Measures message rates and per-node input→output processing delays. Processing
delay is computed for each node automatically — no `--node` filter needed.

| Option | Description |
|--------|-------------|
| `-n, --node NAME` | Narrow graph discovery to one node |
| `-i, --interval SECS` | Update interval (default: 5) |
| `--log FILE` | Save timing data to CSV |
| `--show-processing` | Show per-node delay summary table |
| `--show-topics` | Show topic statistics table |
| `--remote-ip IP` | Configure DDS peer discovery for a remote host |

### monitor_resources.py — CPU / Memory / I/O Monitor

| Option | Description |
|--------|-------------|
| `-l, --list` | List detected ROS2 processes and exit |
| `-i, --interval SECS` | Sampling interval, integer ≥ 1 (default: 1) |
| `-m, --memory` | Include memory statistics |
| `-d, --io` | Include I/O statistics |
| `-t, --threads` | Per-thread statistics |
| `--log FILE` | Append output to log file |
| `--remote-ip IP` | Run `ps`/`pidstat` on remote host via SSH |

### Visualization Scripts

| Script | Purpose |
|--------|---------|
| `visualize_resources.py` | CPU/memory plots, heatmaps, thread-core mapping |
| `visualize_timing.py` | Message timestamps, frequencies, and delay plots |
| `visualize_graph.py` | Interactive ROS2 computation graph topology diagram |
| `view_average.py` | Aggregate statistics across multiple sessions |

### visualize_graph.py — Interactive Pipeline Graph

Renders the full ROS2 computation graph as a directed topology diagram. Nodes
are color-coded by category; topics are shown as labelled edges.

```bash
./src/visualize_graph.py SESSION_DIR [OPTIONS]
```

Run with `--show` to enable an interactive window where you can:

- Hover over nodes and topics for tooltips
- Click a node to see a detail popup with published/subscribed topics, message
  count, frequency (Hz), and latency mean ± std
- Color-coded health indicators (green / yellow / orange / red)

## Session Data Layout

All output is saved in timestamped session folders:

```
monitoring_sessions/
└── 20260306_154140/
    ├── session_info.txt          # Test configuration
    ├── graph_timing.csv          # Topic timing data
    ├── resource_usage.log        # CPU/memory usage
    └── visualizations/           # Auto-generated PNG plots
```
