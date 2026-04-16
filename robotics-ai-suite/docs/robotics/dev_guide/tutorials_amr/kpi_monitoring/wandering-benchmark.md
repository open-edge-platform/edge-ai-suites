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
bash src/wandering_run.sh

# Single run + record a KPI rosbag
bash src/wandering_run.sh --record
```

After the run, visualize results:

```bash
uv run python src/visualize_timing.py monitoring_sessions/wandering/<session>/graph_timing.csv --show
uv run python src/visualize_graph.py monitoring_sessions/wandering/<session>/graph_timing.csv --show
```

## Benchmark (Multiple Runs)

The benchmark target runs the simulation `RUNS` times (default: 25), pausing
between runs, and then aggregates KPI statistics across all sessions.

```bash
# Default benchmark (25 runs, 120s each)
for i in $(seq 1 25); do bash src/wandering_run.sh --timeout 120; done

# Custom parameters (10 runs, 120s each)
for i in $(seq 1 10); do bash src/wandering_run.sh --timeout 120; done

# Re-aggregate KPIs from a completed benchmark directory
uv run python src/aggregate_kpi.py monitoring_sessions/wandering/bench_20260319_100421
```

| Parameter | Description | Default |
|-----------|-------------|--------|
| `--timeout N` | Max duration per run (seconds) | off |
| `--record` | Record KPI topics to a rosbag | — |
| `--plot` | Save trigger-timeline PNG plots | — |

Sessions are stored in `monitoring_sessions/wandering/`.

## Remote Benchmark

To benchmark a wandering pipeline running on a remote machine:

```bash
# CPU + GPU monitoring
./grafana-monitor.sh --remote-ip 10.0.0.1 --remote-user intel --domain-id 46 \
    --gpu --algorithm wandering --duration 180

# CPU + NPU monitoring
./grafana-monitor.sh --remote-ip 10.0.0.1 --remote-user intel --domain-id 46 \
    --npu --algorithm wandering --duration 180

# Combined GPU + NPU
./grafana-monitor.sh --remote-ip 10.0.0.1 --remote-user intel --domain-id 46 \
    --gpu --npu --algorithm wandering --duration 180
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
uv run python src/visualize_timing.py monitoring_sessions/wandering/<session>/graph_timing.csv --show

# Full GPU dashboard (engine/freq/power)
uv run python src/visualize_gpu.py monitoring_sessions/wandering/<session>/gpu_usage.log --show

# NPU dashboard (busy%, clock, memory)
uv run python src/visualize_npu.py monitoring_sessions/wandering/<session>/npu_usage.log --show

# Interactive node topology graph
uv run python src/visualize_graph.py monitoring_sessions/wandering/<session>/graph_timing.csv --show
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
