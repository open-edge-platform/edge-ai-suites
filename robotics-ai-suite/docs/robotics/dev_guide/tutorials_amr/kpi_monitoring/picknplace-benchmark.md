<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Pick & Place Pipeline Benchmark

This benchmark measures KPI performance of the
[Pick & Place Simulation](../simulation/picknplace.md)
— a stationary arm pipeline where two UR5 robotic arms coordinate with a
TurtleBot3 AMR on a conveyor belt using Nav2 and MoveIt2.

The ROS2 KPI toolkit automates the full experiment lifecycle: launching the
simulation, waiting for it to stabilize, capturing metrics, then cleanly
stopping the simulation and aggregating KPI results.

## Prerequisites

Complete the [Installation Guide](installation.md) and ensure the Pick & Place
simulation runs successfully before benchmarking.

## Single Run

`picknplace-run` launches `picknplace warehouse.launch.py`, waits 30 seconds
for the simulation to stabilize, captures GPU and resource metrics for 120
seconds, then sends `SIGINT` to stop the simulation cleanly.

```bash
# Basic single run
bash src/picknplace_run.sh

# Single run + record a KPI rosbag
bash src/picknplace_run.sh --record
```

Results land in `monitoring_sessions/picknplace/<timestamp>/` and can be
visualized immediately:

```bash
uv run python src/visualize_timing.py monitoring_sessions/picknplace/<session>/graph_timing.csv --show
uv run python src/visualize_graph.py monitoring_sessions/picknplace/<session>/graph_timing.csv --show
```

## Benchmark (Multiple Runs)

The benchmark target runs the simulation `RUNS` times (each up to
`PN_TIMEOUT` seconds), pauses between runs, then aggregates KPI statistics.

```bash
# Default benchmark (25 runs)
for i in $(seq 1 25); do bash src/picknplace_run.sh; done

# Custom parameters (5 runs)
for i in $(seq 1 5); do bash src/picknplace_run.sh --timeout 300; done

# Re-aggregate KPIs from a completed benchmark directory
uv run python src/aggregate_kpi.py monitoring_sessions/picknplace/bench_20260319_164521
```

| Parameter | Description | Default |
|-----------|-------------|--------|
| `--timeout N` | Max duration per run (seconds) | 300 |
| `--record` | Record KPI topics to a rosbag | — |
| `--plot` | Save trigger-timeline PNG plots | — |

Sessions are stored in `monitoring_sessions/picknplace/`.

## What the Benchmark Script Does

The `picknplace-run` script (`src/picknplace_run.sh`) automates:

1. Launches `ros2 launch picknplace warehouse.launch.py` in the background.
2. Waits **30 seconds** for the simulation to stabilize.
3. Starts `uv run python src/monitor_stack.py --gpu --duration 120` to capture GPU and resource metrics.
4. After 120 seconds, sends `SIGINT` to stop the simulation and waits for
   both processes to exit cleanly.

## Visualization

```bash
# Timeline, resource, and frequency plots
uv run python src/visualize_timing.py monitoring_sessions/picknplace/<session>/graph_timing.csv --show

# Full GPU dashboard (engine busy%, frequency, power)
uv run python src/visualize_gpu.py monitoring_sessions/picknplace/<session>/gpu_usage.log --show

# Interactive node topology graph
uv run python src/visualize_graph.py monitoring_sessions/picknplace/<session>/graph_timing.csv --show
```

For a specific benchmark directory:

```bash
uv run python src/aggregate_kpi.py monitoring_sessions/picknplace/bench_20260319_164521
uv run python src/visualize_gpu.py monitoring_sessions/picknplace/bench_20260319_164521/<session>/gpu_usage.log --show
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Simulation fails to launch | Ensure `picknplace-simulation` package is installed (see [Pick & Place tutorial](../simulation/picknplace.md)) |
| No GPU data in results | Use `--gpu` flag or verify `intel_gpu_top` is installed on the target |
| Benchmark stops early | Increase `PN_TIMEOUT` — the full pick-and-place cycle can take up to 5 minutes |
| MoveIt2 instability | Run with CycloneDDS: `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp bash src/picknplace_run.sh` |

## Session Data Layout

```
monitoring_sessions/
└── picknplace/
    ├── bench_20260319_164521/        # benchmark run directory
    │   ├── 20260319_164521/          # individual run session
    │   │   ├── session_info.txt
    │   │   ├── graph_timing.csv
    │   │   ├── resource_usage.log
    │   │   ├── gpu_usage.log         # present when GPU=1
    │   │   └── visualizations/
    │   └── kpi_summary.txt           # aggregated KPIs across runs
    └── 20260319_183913/              # standalone single run
        └── ...
```
