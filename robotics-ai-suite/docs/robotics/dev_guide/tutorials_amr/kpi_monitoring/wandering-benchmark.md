<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Wandering AMR Pipeline Benchmark

This benchmark measures KPI performance of the
[Wandering Application](../simulation/launch-wandering-application-gazebo-sim-waffle.md)
— an AMR pipeline where a TurtleBot3 Waffle autonomously maps a Gazebo
environment using Nav2 and RTAB-Map.

The ROS2 KPI toolkit records timing, resource, and optionally GPU/NPU metrics
across repeated runs and produces aggregated KPI reports.

## Prerequisites

Complete the [Installation Guide](installation.md) and ensure the wandering
application runs successfully before benchmarking.

## Single Run

A single run starts the Gazebo wandering simulation, attaches the graph monitor
and latency trigger, and saves all output to
`monitoring_sessions/wandering/<timestamp>/`.

```bash
# Basic single run
make wandering

# Single run + record a KPI rosbag
make wandering-record
```

After the run, visualize results:

```bash
make visualize-last ALGORITHM=wandering
make pipeline-graph ALGORITHM=wandering
```

## Benchmark (Multiple Runs)

The benchmark target runs the simulation `RUNS` times (default: 5), pausing
between runs, and then aggregates KPI statistics across all sessions.

```bash
# Default benchmark (5 runs, 180s each)
make wandering-benchmark

# Custom parameters
make wandering-benchmark RUNS=10 TIMEOUT=180

# Re-aggregate KPIs from a completed benchmark directory
make analyze-benchmark BENCH=monitoring_sessions/wandering/bench_20260319_100421
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `RUNS` | Number of simulation runs | 5 |
| `TIMEOUT` | Max duration per run (seconds) | 180 |
| `PAUSE` | Pause between runs (seconds) | 30 |
| `NODE` | Narrow graph discovery to a specific node | — |

Sessions are stored in `monitoring_sessions/wandering/`.

## Remote Benchmark

To benchmark a wandering pipeline running on a remote machine:

```bash
# CPU + GPU monitoring
make monitor-remote REMOTE_IP=10.0.0.1 REMOTE_USER=intel DOMAIN_ID=46 \
    GPU=1 ALGORITHM=wandering DURATION=180

# CPU + NPU monitoring
make monitor-remote REMOTE_IP=10.0.0.1 REMOTE_USER=intel DOMAIN_ID=46 \
    NPU=1 ALGORITHM=wandering DURATION=180

# Combined GPU + NPU
make monitor-remote REMOTE_IP=10.0.0.1 REMOTE_USER=intel DOMAIN_ID=46 \
    GPU=1 NPU=1 ALGORITHM=wandering DURATION=180
```

> **Note:** DDS discovery on remote sessions typically takes 30–60 seconds.
> Use `DURATION=180` or longer to ensure meaningful data is captured.

For repeated remote runs:

```bash
make monitor-remote-repeat REMOTE_IP=<ip> REMOTE_USER=intel REPEAT=3 \
    GPU=1 ALGORITHM=wandering DOMAIN_ID=46
```

## Visualization

```bash
# Timeline, resource, and frequency plots
make visualize-last ALGORITHM=wandering

# Full GPU dashboard (engine/freq/power)
make visualize-gpu ALGORITHM=wandering

# NPU dashboard (busy%, clock, memory)
make visualize-npu ALGORITHM=wandering

# Interactive node topology graph
make pipeline-graph ALGORITHM=wandering
```

## Session Data Layout

```
monitoring_sessions/
└── wandering/
    ├── bench_20260319_100421/        # benchmark run directory
    │   ├── 20260319_100421/          # individual run session
    │   │   ├── session_info.txt
    │   │   ├── graph_timing.csv
    │   │   ├── resource_usage.log
    │   │   ├── gpu_usage.log         # present when GPU=1
    │   │   ├── npu_usage.log         # present when NPU=1
    │   │   └── visualizations/
    │   └── kpi_summary.txt           # aggregated KPIs across runs
    └── 20260319_183913/              # standalone single run
        └── ...
```
