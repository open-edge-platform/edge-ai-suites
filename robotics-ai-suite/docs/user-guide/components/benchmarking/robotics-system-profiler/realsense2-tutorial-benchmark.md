<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# RealSense2 Tutorial Camera Benchmark

This benchmark measures KPI performance of the
[RealSense Camera with ROS 2 Sample Application](../../sensors/reference_applications/realsense-ros2.md)
— a live-camera streaming pipeline (camera driver + rviz2), supporting both a
USB-connected RealSense camera and a GMSL-connected RealSense Depth Camera D457.

Unlike the simulation benchmarks, this is a live-camera scenario: there's no
goal-based stop condition, so the Robotics System Profiler runs for a fixed
duration, capturing timing, resource, and optionally GPU metrics.

> **Note:** Currently USB cameras are the only supported cameras.

## Prerequisites

Complete the [Installation Guide](installation.md) and ensure the
[RealSense tutorial](../../sensors/reference_applications/realsense-ros2.md)
runs successfully before benchmarking. Run
`scripts/find_cameras.sh` (from the `realsense2_tutorial` package) first to
confirm whether a USB or GMSL camera is connected.

## Single Run

A single run launches `realsense2_tutorial.launch.py`, waits for the camera
driver and rviz2 to initialize, then monitors for a fixed timeout before
stopping cleanly.

```bash
# USB camera (default)
bash src/realsense2_tutorial_run.sh

# USB camera + record a KPI rosbag
bash src/realsense2_tutorial_run.sh --record

# GMSL D457 camera
bash src/benchmark_runner.sh --run-config config/realsense2_tutorial_gmsl_run.yaml --record
```

Results land in `monitoring_sessions/realsense2_tutorial/<timestamp>/` (or
`realsense2_tutorial_gmsl/<timestamp>/` for the GMSL run) and can be
visualized immediately:

```bash
uv run src/visualize_timing.py monitoring_sessions/realsense2_tutorial/<session>/graph_timing.csv --show
uv run src/visualize_graph.py monitoring_sessions/realsense2_tutorial/<session>/graph_timing.csv --show
```

| Parameter | Description | Default |
|-----------|-------------|--------|
| `--timeout N` | Max duration for the run (seconds) | 30 |
| `--record` | Record KPI topics to a rosbag | — |
| `--plot` | Save trigger-timeline PNG plots | — |
| `--output-parent DIR` | Session parent directory | `monitoring_sessions/realsense2_tutorial/` |

## What the Benchmark Script Does

`realsense2_tutorial_run.sh` is a thin wrapper around `benchmark_runner.sh`
using `config/realsense2_tutorial_run.yaml`. It automates:

1. Launches `ros2 launch realsense2_tutorial realsense2_tutorial.launch.py
   camera_type:=usb` in the background.
2. Waits `init_sleep` seconds (20s for USB, 8s for GMSL) before starting the
   monitor — the RealSense USB camera's device-detection delay measured
   ~15-16s even when already connected, so the USB config's `init_sleep`
   accounts for that.
3. Starts `uv run python src/monitor_stack.py` to capture graph timing and
   resource metrics for the configured timeout (default 30s).
4. Sends `SIGINT` to stop the camera driver and rviz2 cleanly.

To customize the launch command, camera type, bag topics, or timing, edit
`config/realsense2_tutorial_run.yaml` (USB) or
`config/realsense2_tutorial_gmsl_run.yaml` (GMSL). Do not edit the
`realsense2_tutorial_run.sh` wrapper file.

## Visualization

```bash
# Timeline, resource, and frequency plots
uv run src/visualize_timing.py monitoring_sessions/realsense2_tutorial/<session>/graph_timing.csv --show

# Full GPU dashboard (engine busy%, frequency, power)
uv run src/visualize_gpu.py monitoring_sessions/realsense2_tutorial/<session>/gpu_usage.log --show

# Interactive node topology graph
uv run src/visualize_graph.py monitoring_sessions/realsense2_tutorial/<session>/graph_timing.csv --show
```

## Session Data Layout

```text
monitoring_sessions/
└── realsense2_tutorial/
    └── 20260819_141351/
        ├── session_info.txt
        ├── graph_timing.csv
        ├── resource_usage.json
        ├── gpu_usage.log
        ├── kpi.json
        ├── report.html
        └── visualizations/
```
