<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Example: Debug Performance Issue

This example walks through debugging a performance issue in your ROS2 system.

## Scenario

Your robot is running slowly, and you suspect a specific node is causing issues.

## Investigation Steps

### Step 1: Identify Problematic Process

```bash
# List all ROS2 processes and their CPU usage
./src/monitor_resources.py --list
```

Look for processes with high CPU usage.

### Step 2: Monitor the Suspicious Node

```bash
# Start detailed monitoring of the problematic node
uv run python src/monitor_stack.py --node /problematic_node --session debug_session_1
```

### Step 3: Reproduce the Issue

While monitoring is running:
- Execute the operations that trigger the performance issue
- Let it run for at least 30-60 seconds
- Observe the real-time output in the terminal

### Step 4: Stop and Analyze

```bash
# Press Ctrl+C to stop monitoring
# Visualizations are auto-generated

# Check the results
ls monitoring_sessions/debug_session_1/visualizations/
```

### Step 5: Review Visualizations

Open and analyze:
- **timing_delays.png**: Are there spikes in processing delays?
- **message_frequencies.png**: Are message rates irregular?
- **cpu_usage_timeline.png**: When do CPU spikes occur?
- **cpu_heatmap.png**: Is CPU distributed evenly?

### Step 6: Correlate with Logs

```bash
# Check session timing data
cat monitoring_sessions/debug_session_1/graph_timing.csv

# Check resource usage patterns
tail -100 monitoring_sessions/debug_session_1/resource_usage.log
```

## Common Issues and Solutions

### High Processing Delays
**Symptom**: Large gaps in timing_delays.png
**Possible causes**:
- Heavy computation in callback
- Blocking operations
- Insufficient CPU resources

**Next steps**:
- Profile the node's code
- Check for synchronous I/O operations
- Consider multi-threading

### CPU Spikes
**Symptom**: Sharp peaks in cpu_usage_timeline.png
**Possible causes**:
- Periodic heavy computation
- Message bursts
- Memory allocation

**Next steps**:
- Review periodic timers
- Check message queue sizes
- Profile memory usage

### Uneven CPU Distribution
**Symptom**: Concentration in cpu_heatmap.png
**Possible causes**:
- Single-threaded bottleneck
- Lack of parallelization
- Poor CPU affinity

**Next steps**:
- Consider multi-threaded callbacks
- Review executor configuration
- Set CPU affinity

## Comparative Analysis

After making changes, run another session:

```bash
# After optimization
uv run python src/monitor_stack.py --node /problematic_node --session debug_session_2 --duration 60

# Compare results
diff -r monitoring_sessions/debug_session_1/visualizations/ \
        monitoring_sessions/debug_session_2/visualizations/
```

## Advanced: Continuous Monitoring

For long-running systems:

```bash
# Start monitoring in background
nohup uv run python src/monitor_stack.py --node /production_node \
    --session production_monitoring > /dev/null 2>&1 &

# Save the PID
echo $! > monitor.pid

# Stop later
kill -SIGINT $(cat monitor.pid)
```
