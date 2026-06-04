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
| ROS2 Humble / Jazzy | See [Getting Started](../../../gsg_robot/index.md) |
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
| `--gpu` | Enable Intel GPU monitoring (uses `qmassa`; falls back to sysfs remotely) |
| `--npu` | Enable Intel NPU monitoring via sysfs |
| `--remote-ip IP` | Monitor a remote machine |
| `--remote-user USER` | SSH user for remote machine (default: ubuntu) |
| `--ros-domain-id ID` | Explicitly set `ROS_DOMAIN_ID` (skips auto-detection) |
| `--algorithm LABEL` | Group sessions under `monitoring_sessions/<label>/` |
| `--use-sim-time` | Pass `--use-sim-time` to the graph monitor (auto-detected for Gazebo) |
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
| `visualize_gpu.py` | Intel GPU busy%, frequency, temperature, power, and per-PID usage |
| `visualize_npu.py` | Intel NPU busy%, clock frequency, and memory utilization |
| `visualize_thermal.py` | CPU/GPU temperature, throttle state, and package power |
| `visualize_kpi.py` | KPI summary plots across benchmark sessions |
| `view_average.py` | Aggregate statistics across multiple sessions |
| `compare_kpi.py` | Side-by-side comparison of KPI results across runs |
| `generate_report.py` | Generate a combined benchmark report |

### Analysis Scripts

| Script | Purpose |
|--------|--------|
| `analyze_rosbag.py` | Per-topic statistics and latency analysis from SQLite3 bag files |
| `analyze_bag_e2e.py` | End-to-end latency analysis across a ROS2 bag |
| `analyze_fastmapping_log.py` | Parse fast_mapping shutdown log and patch `kpi.json` |
| `analyze_picknplace_log.py` | Parse pick-and-place log and patch `kpi.json` |
| `analyze_pipeline_latency.py` | Pipeline latency analysis from graph timing CSV |
| `analyze_trigger_latency.py` | Trigger-based latency breakdown per benchmark run |
| `aggregate_kpi.py` | Aggregate KPI results across multiple benchmark sessions |
| `summarize_benchmark.py` | Print a summary table for a completed benchmark directory |

### Benchmark Runner Scripts

| Script | Purpose |
|--------|--------|
| `wandering_run.sh` | Single run or benchmark of the Wandering AMR simulation |
| `picknplace_run.sh` | Single run or benchmark of the Pick & Place simulation |
| `fastmapping_run.sh` | Single run or benchmark of the FastMapping RGB-D scenario |
| `bag_replay_run.sh` | Offline bag-replay benchmarking (reproducible, CI-friendly) |
| `benchmark_runner.sh` | Generic benchmark runner used by the scenario-specific wrappers |

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

All output is saved in timestamped session folders. When `--algorithm` is
provided, sessions are grouped by algorithm label:

```
monitoring_sessions/
└── <algorithm>/                  # optional: set by --algorithm
    └── 20260306_154140/
        ├── session_info.txt      # Test configuration
        ├── graph_timing.csv      # Topic timing data
        ├── graph_topology.json   # Node/topic topology snapshot
        ├── resource_usage.log    # CPU/memory usage (pidstat)
        ├── gpu_usage.log         # GPU metrics (if --gpu)
        ├── npu_usage.log         # NPU metrics (if --npu)
        ├── cpu_power.log         # CPU temperature/power (if available)
        ├── kpi.json              # Level-1 KPI summary
        ├── kpi_level2.json       # Level-2 chained KPI (if applicable)
        └── visualizations/       # Auto-generated PNG plots
```
