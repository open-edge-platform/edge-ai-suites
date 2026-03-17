<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Summary of Improvements

##  March 2026 — Latest Updates

### CPU% Clarity in Resource Reports
`visualize_resources.py` now makes multi-core CPU% readings unambiguous:
- **`Avg Cores` column** in the summary table (value = CPU% ÷ 100, e.g. "5.63 cores" instead of "563%")
- **Context note** at the top of every report: *"100% = 1 full core. System has N logical cores (max: N×100%)"*
- **Reference line** at 100% (dashed gray, "= 1 core") on all CPU utilization and heatmap plots

### Interactive Pipeline Graph — Click to See Node Details
`visualize_graph.py` (`make pipeline-graph --show`) now supports clicking on nodes:
- Opens a **Tkinter popup** with publishers and subscribers for that node
- Each topic row shows: message count, frequency (Hz), latency mean ± std
- Color-coded health dots: green < 20 ms, yellow < 100 ms, orange < 500 ms, red ≥ 500 ms
- Re-clicking the same node refreshes the popup; clicking elsewhere closes it

### Grafana Node Detail Panels
The Grafana dashboard now includes a **Node Detail** row:
- `$node` dropdown variable auto-populated from `label_values(ros2_node_topic_frequency_hz, node)`
- **Publishes** and **Subscribes** table panels per node with latency threshold coloring
- New Prometheus metrics: `ros2_node_topic_frequency_hz`, `ros2_node_topic_latency_ms`, `ros2_node_topic_msg_count`, `ros2_node_proc_delay_ms`

### Exporter Port Changed to 9092
Prometheus runs in host-network mode and occupies port 9090. The KPI exporter now defaults to **port 9092** to avoid the conflict:
- `prometheus/prometheus.yml` scrape target updated to `localhost:9092`
- `Makefile` `grafana-export` and `grafana-export-live` targets updated
- `make grafana-export SESSION=<name>` auto-kills stale processes on that port before binding

---

##  What's New

Your ROS2 monitoring stack now has **3 cleaner ways to run**:

### 1.  Python Orchestrator (`monitor_stack.py`)
Single Python script that manages everything:
```bash
./monitor_stack.py --node /your_node
```

### 2.  Makefile Commands
Simple, memorable commands:
```bash
make monitor NODE=/your_node
make quick-check
make list-sessions
```

---

##  Before vs After

###  Before (The Old Way)
Required **4 separate terminals** and manual coordination:

```bash
# Terminal 1: Start graph monitor
./ros2_graph_monitor.py --node /slam_toolbox --log timing.csv

# Terminal 2: Start resource monitor
./monitor_resources.py --memory --threads --log resources.log

# Wait... monitor... Ctrl+C on both terminals

# Terminal 3: Manually visualize timing
./visualize_timing.py timing.csv --output-dir ./plots/ --delays --frequencies

# Terminal 4: Manually visualize resources
./visualize_resources.py resources.log --output-dir ./plots/ --cores --heatmap

# Manually organize files, create directories, etc.
```

**Problems:**
- Too many terminals to manage
- Easy to forget to start one monitor
- Manual file management
- Manual visualization steps
- No session organization
- Hard to reproduce

---

###  After (The New Way)

**Single command in one terminal:**

```bash
./monitor_stack.py --node /slam_toolbox
# Press Ctrl+C when done - everything is automatic!
```

**Or even simpler:**

```bash
make monitor NODE=/slam_toolbox
```

**Benefits:**
-  Single command does everything
-  Automatic file organization
-  Auto-generates visualizations on exit
-  Graceful shutdown handling
-  Session history and management
-  Easy to reproduce
-  Clean output structure

---

##  Key Features of the New Stack

### 1. Automatic Session Management
```
monitoring_sessions/
 20260209_143022/          # Auto-timestamped
     session_info.txt      # What you monitored
     graph_timing.csv      # Raw timing data
     resource_usage.log    # Raw CPU/memory data
     visualizations/       # Auto-generated plots
```

### 2. Concurrent Monitoring
- Both graph and resource monitors run simultaneously
- Output is properly multiplexed and labeled
- Both stop gracefully on Ctrl+C

### 3. Built-in Visualization
- Automatically generates all plots when you stop monitoring
- No need to remember visualization commands
- All plots saved in organized structure

### 4. Session History
```bash
# See all past monitoring sessions
./monitor_stack.py --list-sessions

# Or with make
make list-sessions
```

### 5. Flexible Control
```bash
# Monitor for specific duration
./monitor_stack.py --duration 60

# Custom update interval
./monitor_stack.py --interval 2

# Graph only (lightweight)
./monitor_stack.py --graph-only

# Resources only (with threads)
./monitor_stack.py --resources-only

# Resources only (PIDs only)
./monitor_stack.py --resources-only --pid-only

# Named sessions for experiments
./monitor_stack.py --session my_experiment
```

---

##  Quick Start Examples

### Example 1: Quick Performance Check
```bash
make quick-check
```
Runs a 30-second monitoring session and shows you the results.

### Example 2: Debug a Node
```bash
make monitor NODE=/problematic_node
# Let it run while reproducing the issue
# Press Ctrl+C
# Check monitoring_sessions/*/visualizations/
```

### Example 3: Long-term Monitoring
```bash
./monitor_stack.py --node /critical_node --session production_test
# Run for hours or days
# All data is properly logged and organized
```

### Example 4: Compare Performance
```bash
# Before optimization
make monitor NODE=/controller_server SESSION=before

# After optimization
make monitor NODE=/controller_server SESSION=after

# Compare the visualization folders
```

---

##  File Structure

### New Files Added:
```
ros2-kpi/
 monitor_stack.py      # Main orchestrator (NEW!)
 Makefile              # Make targets (NEW!)
 QUICK_START.md        # Quick reference (NEW!)
 IMPROVEMENTS.md       # This file (NEW!)

 ros2_graph_monitor.py     # Original (still works standalone)
 monitor_resources.py      # Original (still works standalone)
 visualize_timing.py       # Original (still works standalone)
 visualize_resources.py    # Original (still works standalone)
 analyze_rosbag.py         # Original (still works standalone)
 README.md                 # Updated with new info
```

### Output Structure:
```
monitoring_sessions/
 20260209_143022/
    session_info.txt
    graph_timing.csv
    resource_usage.log
    visualizations/
        timing_delays.png
        message_frequencies.png
        cpu_usage_timeline.png
        cpu_heatmap.png
 20260209_150315/
    ... (another session)
 my_experiment/
     ... (named session)
```

---

##  Learning Curve

### For Quick Tasks:
Just remember: `make monitor`

### For Specific Nodes:
`make monitor NODE=/node_name`

### For Everything Else:
Check `./monitor_stack.py --help` or `make help`

---

##  Backward Compatibility

**All original scripts still work!** You can use them individually if needed:
```bash
./ros2_graph_monitor.py --node /my_node --log my_timing.csv
./monitor_resources.py --memory --log my_resources.log
```

The new stack is just a convenience layer on top.

---

##  Recommended Workflow

1. **Start your ROS2 system:**
   ```bash
   ros2 launch my_robot robot.launch.py
   ```

2. **Start monitoring (pick one):**
   ```bash
   # Option 1: Python
   ./monitor_stack.py --node /my_critical_node

   # Option 2: Make
   make monitor NODE=/my_critical_node
   ```

3. **Let it run, then press Ctrl+C**

4. **Check results:**
   ```bash
   # Automatically created in:
   # monitoring_sessions/<timestamp>/visualizations/
   ```

5. **Review session history:**
   ```bash
   make list-sessions
   ```

---

##  Benefits Summary

| Before | After |
|--------|-------|
| 4 terminals | 1 terminal |
| 6+ commands | 1 command |
| Manual file management | Automatic organization |
| Manual visualization | Auto-generated plots |
| Hard to reproduce | Session management built-in |
| Easy to forget steps | Single workflow |
| Scattered outputs | Organized sessions |

---

##  Documentation

- **Quick Start:** See [QUICK_START.md](QUICK_START.md)
- **Full Details:** See updated [README.md](README.md)
- **Help:** Run `./monitor_stack.py --help` or `make help`

---

##  Next Steps

1. Try a quick test:
   ```bash
   make quick-check
   ```

2. Monitor your specific node:
   ```bash
   make monitor NODE=/your_node_name
   ```

3. Explore the session outputs in `monitoring_sessions/`

4. Check out the auto-generated visualizations!

---

Enjoy your streamlined monitoring workflow! 
