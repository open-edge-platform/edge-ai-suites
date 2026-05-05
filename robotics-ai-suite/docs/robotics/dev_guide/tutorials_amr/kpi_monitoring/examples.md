<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Practical Examples

## Quick Performance Check

A 30-second snapshot to verify system health.

**Prerequisites:** ROS2 system running, monitoring stack installed.

1. Source your ROS2 environment:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
source /opt/ros/humble/setup.bash
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

2. Launch your ROS2 system:

```bash
ros2 launch my_robot robot.launch.py
```

3. In a new terminal, run the quick check (completes automatically):

```bash
uv run python src/monitor_stack.py --duration 30
```

4. Review auto-generated results:

```bash
ls monitoring_sessions/latest/visualizations/
```

**Output files:**

| File | Contents |
|------|---------|
| `timing_delays.png` | Processing delays per node |
| `message_frequencies.png` | Topic Hz over time |
| `cpu_usage_timeline.png` | CPU usage over time |
| `cpu_heatmap.png` | CPU distribution across cores |

## Monitor a Specific Node

Detailed monitoring of a single ROS2 node for performance analysis.

**Use when:** Analyzing a particular node's processing delays, CPU/memory usage,
or identifying bottlenecks.

```bash
# 1. Find available nodes
ros2 node list

# 2. Start monitoring (runs until Ctrl+C)
uv run python src/monitor_stack.py --node /slam_toolbox

# 3. Let it run while your system operates normally

# 4. Press Ctrl+C — visualizations are auto-generated
ls monitoring_sessions/latest/visualizations/
```

With a fixed duration:

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --duration 120   # 2 minutes
```

Using Python directly for a named session:

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --session slam_analysis
```

**What to look for in results:**

- `timing_delays.png` — High delays indicate callback bottlenecks
- `cpu_usage_timeline.png` — CPU spikes correlate with processing load
- `cpu_heatmap.png` — Uneven distribution may indicate single-threaded bottlenecks
- `message_frequencies.png` — Irregular rates can reveal queue or scheduling issues

## Debug a Performance Issue

Step-by-step guide to isolate and diagnose a performance problem.

**Scenario:** Your robot is running slowly and you suspect a specific node.

### Step 1 — Identify the Problematic Process

```bash
uv run python src/monitor_resources.py --list
```

Look for processes with unexpectedly high CPU usage.

### Step 2 — Start Detailed Monitoring

```bash
uv run python src/monitor_stack.py --node /problematic_node --session debug_session_1
```

### Step 3 — Reproduce the Issue

While monitoring is running, execute the operations that trigger the performance
problem. Let it run for at least 30–60 seconds to collect representative data.

### Step 4 — Stop and Analyze

```bash
# Press Ctrl+C — visualizations are auto-generated
ls monitoring_sessions/debug_session_1/visualizations/
```

For deeper inspection:

```bash
# Inspect raw timing data
cat monitoring_sessions/debug_session_1/graph_timing.csv

# Check resource patterns
tail -100 monitoring_sessions/debug_session_1/resource_usage.log
```

### Step 5 — Interpret Results

| Symptom | Possible causes | Next steps |
|---------|----------------|-----------|
| Spikes in `timing_delays.png` | Heavy callback computation, blocking I/O | Profile the node's code; check for synchronous I/O |
| Peaks in `cpu_usage_timeline.png` | Periodic heavy computation, message bursts | Review periodic timers; check queue sizes |
| Concentrated `cpu_heatmap.png` | Single-threaded bottleneck | Consider multi-threaded callbacks; review executor config |
| Irregular `message_frequencies.png` | Network latency, scheduler pressure | Check DDS QoS settings; review publisher rates |

### Step 6 — Validate a Fix

After making changes, record a second session and compare:

```bash
uv run python src/monitor_stack.py --node /problematic_node --session debug_session_2 --duration 60

# Compare visualizations side by side
diff -r monitoring_sessions/debug_session_1/visualizations/ \
         monitoring_sessions/debug_session_2/visualizations/
```

Compare visualizations side by side between sessions.

## Monitor a Navigation Stack

```bash
# Terminal 1: start the navigation stack
ros2 launch nav2_bringup tb3_simulation_launch.py

# Terminal 2: monitor interactively
./quickstart
# Choose: 1) Monitor my ROS2 application
```

## Before/After Optimization Comparison

```bash
# Before optimization
uv run python src/monitor_stack.py --node /my_node --duration 120

# Make your code changes, then run again
uv run python src/monitor_stack.py --node /my_node --duration 120

# Compare sessions
diff -r monitoring_sessions/<session_before>/visualizations/ \
         monitoring_sessions/<session_after>/visualizations/
```
