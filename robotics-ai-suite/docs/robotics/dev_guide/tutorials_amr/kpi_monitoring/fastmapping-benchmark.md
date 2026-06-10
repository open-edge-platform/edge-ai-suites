<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# FastMapping RGB-D Benchmark

This benchmark measures KPI performance of the FastMapping RGB-D SLAM pipeline
— a depth-camera mapping scenario that processes a bundled Intel&trade; spinning RGB-D
bag (`~12 s`, 175 depth frames) and reports real-time frame throughput, compute
latency, and timing jitter.

The ROS2 KPI toolkit automates the full experiment lifecycle: launching the
pipeline, waiting for it to stabilize, capturing timing and resource metrics,
then aggregating KPI results across multiple runs.

## Prerequisites

Complete the [Installation Guide](installation.md) and ensure the
`fast_mapping` ROS2 package is installed and functional:

```bash
ros2 launch fast_mapping fast_mapping.launch.py
```

The bundled bag file must be present at:

```
/opt/ros/<ROS_DISTRO>/share/bagfiles/spinning/
```

## Single Run

`make fastmapping` launches `ros2 launch fast_mapping fast_mapping.launch.py`,
which starts `fast_mapping_node`, `rviz2`, and replays the bundled spinning
RGB-D bag. After the bag finishes, `analyze_fastmapping_log.py` parses the
node's shutdown timing table and writes `kpi.json`.

```bash
# Basic single run
make fastmapping

# Single run with trigger-timeline plots
make fastmapping-plot

# Override the run profile
make fastmapping RUN_CONFIG=config/fastmapping_run.yaml
```

Results land in `monitoring_sessions/fastmapping/<timestamp>/` and can be
visualized immediately:

```bash
uv run python src/visualize_timing.py monitoring_sessions/fastmapping/<session>/graph_timing.csv --show
uv run python src/visualize_kpi.py --session monitoring_sessions/fastmapping/<session>
```

## Benchmark (Multiple Runs)

The benchmark target runs the pipeline `RUNS` times and aggregates KPI
statistics across all runs, providing mean, median, p95, and standard
deviation for each metric.

```bash
# Default benchmark (10 runs)
make fastmapping-benchmark

# Custom number of runs
make fastmapping-benchmark RUNS=25

# With trigger-timeline plots
make fastmapping-plot

# Re-aggregate KPIs from a completed benchmark directory
uv run python src/aggregate_kpi.py monitoring_sessions/fastmapping/bench_<timestamp>
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `RUNS` | Number of benchmark repetitions | `10` |
| `RATE` | Bag playback rate multiplier | `1.0` |
| `PAUSE` | Seconds to pause between runs | `10` |
| `RUN_CONFIG` | Path to a YAML run profile override | `config/fastmapping_run.yaml` |

## KPI Outputs

After each run, `analyze_fastmapping_log.py` parses the `fast_mapping_node`
shutdown log and patches `kpi.json` with the following metrics:

| KPI | Description |
|-----|-------------|
| `throughput_hz` | Frame processing rate |
| `mean_latency_ms` | Compute time excluding wait-for-frame |
| `mean_jitter_ms` | Window-to-window timing variation |

The Level-2 file `kpi_level2.json` contains chained per-frame statistics.

## What the Benchmark Script Does

`fastmapping_run.sh` is a thin wrapper around `benchmark_runner.sh` with the
scenario configuration sourced from `config/fastmapping_run.yaml`. It:

1. Launches `ros2 launch fast_mapping fast_mapping.launch.py` in the background.
2. Starts `uv run python src/monitor_stack.py --gpu` to capture resource
   and GPU metrics.
3. Waits for the bag replay to complete (auto-detected via the stop condition
   defined in the YAML profile).
4. Sends `SIGINT` to stop the pipeline cleanly.
5. Runs `analyze_fastmapping_log.py` to patch `kpi.json` with timing KPIs.
6. Generates trigger-timeline plots if `--plot` was passed.

## Visualization

```bash
# KPI summary charts (latency histogram, resource utilization)
uv run python src/visualize_kpi.py --session monitoring_sessions/fastmapping/<session>

# Timeline and frequency plots
uv run python src/visualize_timing.py monitoring_sessions/fastmapping/<session>/graph_timing.csv --show

# GPU dashboard (busy%, frequency, power)
uv run python src/visualize_gpu.py monitoring_sessions/fastmapping/<session> --show

# Thermal dashboard (CPU/GPU temperature, throttle, power)
uv run python src/visualize_thermal.py monitoring_sessions/fastmapping/<session> --show

# Interactive node topology graph
uv run python src/visualize_graph.py monitoring_sessions/fastmapping/<session> --show
```

For a completed benchmark directory:

```bash
uv run python src/aggregate_kpi.py monitoring_sessions/fastmapping/bench_<timestamp>
uv run python src/summarize_benchmark.py monitoring_sessions/fastmapping/bench_<timestamp>
```

## Session Data Layout

```
monitoring_sessions/
└── fastmapping/
    ├── bench_<timestamp>/            # benchmark run directory
    │   ├── <timestamp_run_1>/        # individual run session
    │   │   ├── session_info.txt
    │   │   ├── graph_timing.csv
    │   │   ├── resource_usage.log
    │   │   ├── gpu_usage.log         # present when GPU monitoring enabled
    │   │   ├── kpi.json              # per-run KPI (patched by analyze script)
    │   │   ├── kpi_level2.json       # chained per-frame statistics
    │   │   ├── fastmapping_procedures.json
    │   │   └── visualizations/
    │   └── kpi_summary.txt           # aggregated KPIs across runs
    └── <timestamp>/                  # single-run session
        ├── kpi.json
        └── visualizations/
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `fast_mapping` package not found | Install `ros-<distro>-benchmark-framework` (see [Installation](installation.md)) |
| Bag file missing | Check `/opt/ros/$ROS_DISTRO/share/bagfiles/spinning/` exists |
| `throughput_hz` is 0 or missing | The node may have crashed before logging — check `ros2 launch` output |
| GPU data absent from results | Pass `--gpu` explicitly or verify `qmassa` is installed (`make install-qmassa`) |
| `kpi.json` not patched | Run `uv run python src/analyze_fastmapping_log.py <session_dir>` manually |
| Runs complete but no aggregate | Run `uv run python src/aggregate_kpi.py monitoring_sessions/fastmapping/bench_<timestamp>` |
