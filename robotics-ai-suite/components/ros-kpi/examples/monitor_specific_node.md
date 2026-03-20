<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Example: Monitor Specific Node

This example shows how to monitor a specific ROS2 node for performance analysis.

## Use Case

You want to analyze the performance of a specific node (e.g., `/slam_toolbox`) to:
- Understand processing delays
- Monitor CPU/memory usage
- Identify performance bottlenecks

## Steps

```bash
# 1. Identify the node you want to monitor
ros2 node list

# 2. Start monitoring that specific node
make monitor NODE=/slam_toolbox

# 3. Let it run while your system operates
#    (Run for as long as needed to collect representative data)

# 4. Press Ctrl+C to stop and auto-generate visualizations

# 5. Review the results
ls monitoring_sessions/*/visualizations/
```

## Alternative Methods

### Using Python directly:
```bash
uv run python src/monitor_stack.py --node /slam_toolbox --session slam_analysis
```

### Using the bash wrapper:
```bash
make monitor NODE=/slam_toolbox
```

### With custom duration:
```bash
make monitor NODE=/slam_toolbox DURATION=120  # 2 minutes
```

## Analyzing Results

The session folder will contain:
- Raw timing data (`graph_timing.csv`)
- Raw resource data (`resource_usage.log`)
- Session metadata (`session_info.txt`)
- Visualizations (auto-generated PNG files)

Look for:
- High processing delays in timing_delays.png
- CPU spikes in cpu_usage_timeline.png
- Uneven CPU distribution in cpu_heatmap.png
- Irregular message frequencies in message_frequencies.png
