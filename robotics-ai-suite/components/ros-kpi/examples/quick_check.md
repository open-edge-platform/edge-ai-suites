<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Example: Quick Performance Check

This example demonstrates how to quickly check the performance of your ROS2 system.

## Prerequisites

- ROS2 system is running
- Monitoring stack is installed

## Steps

```bash
# 1. Make sure your ROS2 environment is sourced
source /opt/ros/humble/setup.bash

# 2. Launch your ROS2 system
ros2 launch my_robot robot.launch.py

# 3. In a new terminal, run a quick check (30 seconds)
cd /path/to/ros2-kpi
make quick-check

# 4. Wait 30 seconds for automatic completion

# 5. Check the results
ls -lh monitoring_sessions/*/visualizations/
```

## Expected Output

The monitoring session will automatically:
- Collect graph timing data
- Collect resource usage data
- Generate visualizations
- Save everything in a timestamped folder

## Analyzing Results

Open the visualization folder to see:
- `timing_delays.png` - Processing delays
- `message_frequencies.png` - Topic frequencies
- `cpu_usage_timeline.png` - CPU usage over time
- `cpu_heatmap.png` - CPU distribution across cores
