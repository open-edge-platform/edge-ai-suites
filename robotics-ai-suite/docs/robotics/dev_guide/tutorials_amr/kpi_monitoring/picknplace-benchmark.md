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
make picknplace-run

# Single run + record a KPI rosbag
make picknplace-record
```

Results land in `monitoring_sessions/picknplace/<timestamp>/` and can be
visualized immediately:

```bash
make visualize-last
make pipeline-graph
```

## Benchmark (Multiple Runs)

The benchmark target runs the simulation `RUNS` times (each up to
`PN_TIMEOUT` seconds), pauses between runs, then aggregates KPI statistics.

```bash
# Default benchmark
make picknplace-benchmark

# Custom parameters
make picknplace-benchmark RUNS=5

# Re-aggregate KPIs from a completed benchmark directory
make analyze-benchmark BENCH=monitoring_sessions/picknplace/bench_20260319_164521
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `RUNS` | Number of simulation runs | 5 |
| `PN_TIMEOUT` | Max duration per run (seconds) | 300 |
| `PAUSE` | Pause between runs (seconds) | 30 |
| `NODE` | Narrow graph discovery to a specific node | — |

Sessions are stored in `monitoring_sessions/picknplace/`.

## What the Benchmark Script Does

The `picknplace-run` script (`src/picknplace_run.sh`) automates:

1. Launches `ros2 launch picknplace warehouse.launch.py` in the background.
2. Waits **30 seconds** for the simulation to stabilize.
3. Starts `make monitor-gpu DURATION=120` to capture GPU and resource metrics.
4. After 120 seconds, sends `SIGINT` to stop the simulation and waits for
   both processes to exit cleanly.

## Visualization

```bash
# Timeline, resource, and frequency plots
make visualize-last

# Full GPU dashboard (engine busy%, frequency, power)
make visualize-gpu

# Interactive node topology graph
make pipeline-graph
```

For a specific session:

```bash
make visualize-last ALGORITHM=picknplace
make visualize-gpu SESSION=monitoring_sessions/picknplace/bench_20260319_164521
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Simulation fails to launch | Ensure `picknplace-simulation` package is installed (see [Pick & Place tutorial](../simulation/picknplace.md)) |
| No GPU data in results | Use `GPU=1` flag or verify `intel_gpu_top` is installed on the target |
| Benchmark stops early | Increase `PN_TIMEOUT` — the full pick-and-place cycle can take up to 5 minutes |
| MoveIt2 instability | Run with CycloneDDS: `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp make picknplace-run` |

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
