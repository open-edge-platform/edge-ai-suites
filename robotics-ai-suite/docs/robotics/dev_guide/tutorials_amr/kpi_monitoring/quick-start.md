<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Quick Start Guide

Complete the [installation](installation.md) before proceeding.

## Easiest Way — Interactive Launcher

The `quickstart` script provides a guided menu that handles ROS2 environment
setup automatically:

```bash
cd <ros-kpi-component-dir>
./quickstart
```

The menu guides you through:

- Monitoring your ROS2 application
- Running Wandering and Pick-n-Place simulations with rosbag recording
- Analyzing rosbag results
- Quick health checks
- Starting Grafana dashboards

Alternatively, use the `make` shortcut:

```bash
make start    # Same as ./quickstart
make quick    # Quick 30-second health check
```

## Common Tasks

### Monitor All Nodes

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

```bash
# Quick 30-second check
make quick-check

# Full 60-second session
make monitor

# Extended session (5 minutes)
make monitor-long DURATION=300
```

### Monitor a Specific Node

```bash
# By name
make monitor NODE=/slam_toolbox DURATION=120

# Or using Python directly
uv run python src/monitor_stack.py --node /slam_toolbox --session my_session --duration 120
```

### Remote Monitoring

```bash
# Basic remote session
make monitor-remote REMOTE_IP=192.168.1.100

# With specific node and user
make monitor-remote REMOTE_IP=192.168.1.100 REMOTE_USER=ubuntu NODE=/slam_toolbox
```

> **Note:** Allow 30–60 seconds for DDS discovery to complete before topic data
> starts flowing on remote sessions. Use `--duration` ≥ 90s for remote monitoring.

## Results

All output is saved in `monitoring_sessions/` under a timestamped folder:

```
monitoring_sessions/
└── 20260306_154140/
    ├── session_info.txt          # Test configuration
    ├── graph_timing.csv          # Topic timing data
    ├── resource_usage.log        # CPU/memory usage
    └── visualizations/           # Auto-generated PNG plots
        ├── timing_delays.png
        ├── message_frequencies.png
        ├── cpu_usage_timeline.png
        └── cpu_heatmap.png
```

Useful session commands:

```bash
make list-sessions              # List all previous sessions
make visualize-last             # Re-visualize the most recent session
make analyze-session SESSION=20260305_123456
```

## Advanced Usage

### Benchmarking

```bash
# Run Wandering benchmark (5 runs, 180s each)
make wandering-benchmark RUNS=5 TIMEOUT=180

# Run Pick-n-Place benchmark (5 runs)
make picknplace-benchmark RUNS=5
```

### Grafana Dashboard

```bash
make grafana-start              # Start Grafana + Prometheus
make grafana-export SESSION=20260306_154140   # Export session metrics
make grafana-open               # Open http://localhost:30000
make grafana-stop               # Stop the stack
```

See [Grafana Dashboard](grafana.md) for the full setup guide.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| ROS2 not found | `source /opt/ros/humble/setup.bash` (or `jazzy`) `&& export ROS_DOMAIN_ID=0` |
| No nodes detected | Ensure your ROS2 application is running first |
| `permission denied` on scripts | `chmod +x quickstart auto-setup.sh` |
| `uv` not found | `curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc` |
| Remote: no data | Verify SSH key auth and matching `ROS_DOMAIN_ID` on both machines |

For auto-setup of the ROS2 environment:

```bash
source ./auto-setup.sh
```
