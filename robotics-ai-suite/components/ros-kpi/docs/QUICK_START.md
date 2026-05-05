<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Quick Reference Guide - ROS2 KPI Monitoring Stack

## 🚀 Fastest Way to Get Started

### 1. Simple Monitoring (All Defaults)
```bash
uv run python src/monitor_stack.py
```
Press `Ctrl+C` when done. Visualizations are auto-generated!

### 2. Monitor Specific Node
```bash
uv run python src/monitor_stack.py --node /your_node_name
```

### 3. Named Session
```bash
uv run python src/monitor_stack.py --node /slam_toolbox --session experiment_1
```

---

## 📊 Common Use Cases

### Quick Performance Check (30 seconds)
```bash
uv run python src/monitor_stack.py --duration 30
```

### Long-Term Monitoring of Specific Node
```bash
uv run python src/monitor_stack.py --node /controller_server --session long_term_test
```

### Debug Performance Issues
```bash
# 1. Start monitoring
uv run python src/monitor_stack.py --node /problematic_node --session debug

# 2. Let it run while reproducing the issue
# 3. Press Ctrl+C to stop and auto-generate visualizations
# 4. Check: monitoring_sessions/debug/visualizations/
```

### Monitor a Remote System
```bash
# Monitor a ROS2 pipeline running on another machine
uv run python src/monitor_stack.py --remote-ip 192.168.1.100

```
> Requires SSH key auth to the remote host and matching `ROS_DOMAIN_ID`.

### Compare Before/After Performance
```bash
# Baseline
uv run python src/monitor_stack.py --session baseline --duration 120

# After changes
uv run python src/monitor_stack.py --session after_optimization --duration 120

# Compare visualizations in monitoring_sessions/*/visualizations/
```

---

## 🔍 Thread vs PID Monitoring Modes

### Thread Mode (Default - More Detailed)
- Tracks individual threads (TIDs)
- Shows per-thread CPU usage and core affinity
- More overhead but detailed insights
- Use: `uv run python src/monitor_stack.py`, `uv run python src/monitor_stack.py --resources-only`

### PID Mode (Lighter - Process Level)
- Tracks processes (PIDs) only
- Lower monitoring overhead
- Good for production/long-term monitoring
- Use: `uv run python src/monitor_stack.py --pid-only`, `uv run python src/monitor_stack.py --resources-only --pid-only`

---

## 🎯 Quick Commands Cheat Sheet

| Command | What It Does |
|---------|-------------|
| `uv run python src/monitor_stack.py` | Start full monitoring with threads (graph + resources) |
| `uv run python src/monitor_stack.py --pid-only` | Start full monitoring with PIDs only (lighter) |
| `uv run python src/monitor_stack.py --node /node_name` | Monitor specific node with threads |
| `uv run python src/monitor_stack.py --remote-ip <ip>` | Monitor ROS2 pipeline on a remote machine |
| `uv run python src/monitor_stack.py --remote-ip <ip> --pid-only` | Remote monitoring, PID mode |
| `uv run python src/monitor_stack.py --duration 30` | 30-second performance check |
| `uv run python src/monitor_stack.py --duration 300` | Extended 5-minute monitoring with threads |
| `uv run python src/monitor_stack.py --duration 300 --pid-only` | Extended 5-minute monitoring with PIDs only |
| `uv run python src/monitor_stack.py --list-sessions` | Show all previous sessions |
| `uv run python src/visualize_timing.py <session>/graph_timing.csv --delays --frequencies --show` | Re-generate timing visualizations |
| `uv run python src/monitor_stack.py --graph-only` | Monitor only timing/graph data |
| `uv run python src/monitor_stack.py --resources-only` | Monitor only CPU/memory with thread details |
| `uv run python src/monitor_stack.py --resources-only --pid-only` | Monitor only CPU/memory with PIDs only |
| `make clean` | Delete all monitoring data |
| `make clean-last` | Delete the most recent session |

---

## 📁 Where to Find Your Data

All monitoring data goes to: `monitoring_sessions/<session_name>/`

```text
monitoring_sessions/
└── 20260209_143022/              # Auto-generated timestamp
    ├── session_info.txt          # Session details
    ├── graph_timing.csv          # Message timing data
    ├── resource_usage.log        # CPU/memory logs
    └── visualizations/           # All plots (auto-generated)
        ├── timing_delays.png
        ├── message_frequencies.png
        ├── cpu_usage_timeline.png
        └── cpu_heatmap.png
```

---

## 🔧 Advanced Options

### Custom Session Name
```bash
uv run python src/monitor_stack.py --session my_experiment_name
```

### Custom Output Directory
```bash
uv run python src/monitor_stack.py --output-dir /path/to/results
```

### Timed Monitoring (Auto-Stop)
```bash
uv run python src/monitor_stack.py --duration 300  # Stop after 5 minutes
```

### Faster Updates
```bash
uv run python src/monitor_stack.py --interval 1  # Update every second
```

### Disable Auto-Visualization
```bash
uv run python src/monitor_stack.py --no-visualize
```

### Monitor Only Timing (No CPU Overhead)
```bash
uv run python src/monitor_stack.py --graph-only --node /critical_node
```

---

## 🆚 Old Way vs New Way

### Old Way (Multiple Terminals)
```bash
# Terminal 1
./ros2_graph_monitor.py --node /slam_toolbox --log timing.csv

# Terminal 2
./monitor_resources.py --memory --threads --log resources.log

# Terminal 3 (after stopping)
./visualize_timing.py timing.csv --output-dir ./plots/

# Terminal 4
./visualize_resources.py resources.log --output-dir ./plots/
```

### New Way (Single Command!)
```bash
uv run python src/monitor_stack.py --node /slam_toolbox
# Press Ctrl+C when done - everything is automatic!
```

---

## 💡 Pro Tips

1. **Always name your sessions** for experiments:
   ```bash
   uv run python src/monitor_stack.py --node /node_name --session experiment_1
   ```

2. **Quick check** before long sessions to verify setup:
   ```bash
   uv run python src/monitor_stack.py --duration 30
   ```

3. **Review previous sessions** to track performance over time:
   ```bash
   uv run python src/monitor_stack.py --list-sessions
   ```

4. **Clean old data** to save disk space:
   ```bash
   make clean
   ```

5. **Re-visualize** if you want different plot options:
   ```bash
   uv run python src/visualize_timing.py <session>/graph_timing.csv --delays --frequencies --show
   ```

---

## 🐛 Troubleshooting

### No ROS2 processes found
- Make sure your ROS2 nodes are running before starting the monitor
- Check: `ros2 node list`

### Monitor exits immediately
- Verify ROS2 environment is sourced: `source /opt/ros/humble/setup.bash` (or `jazzy`)
- Check if the target node exists: `ros2 node list`

### Visualizations not generated
- Check if log files were created in the session directory
- Run visualization manually: `uv run python src/visualize_timing.py <session>/graph_timing.csv --delays --frequencies --show`

### Permission denied
- Run `chmod +x quickstart auto-setup.sh` for shell scripts
- Python scripts use `uv run python src/...` and do not need execute permission

---

## 📚 Need More Details?

See the full [README.md](README.md) for:
- Individual script documentation
- Detailed API reference
- ROS bag analysis
- Custom workflows
- Advanced use cases
