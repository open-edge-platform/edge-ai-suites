<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Quick Reference Guide - ROS2 KPI Monitoring Stack

##  Fastest Way to Get Started

### 1. Simple Monitoring (All Defaults)
```bash
./monitor_stack.py
```
Press `Ctrl+C` when done. Visualizations are auto-generated!

### 2. Monitor Specific Node
```bash
./monitor_stack.py --node /your_node_name
```

### 3. Using Make (Even Easier!)
```bash
make monitor NODE=/slam_toolbox
```

---

##  Common Use Cases

### Quick Performance Check (30 seconds)
```bash
make quick-check
```

### Long-Term Monitoring of Specific Node
```bash
./monitor_stack.py --node /controller_server --session long_term_test
```

### Debug Performance Issues
```bash
# 1. Start monitoring
./monitor_stack.py --node /problematic_node --session debug

# 2. Let it run while reproducing the issue
# 3. Press Ctrl+C to stop and auto-generate visualizations
# 4. Check: monitoring_sessions/debug/visualizations/
```

### Monitor a Remote System
```bash
# Monitor a ROS2 pipeline running on another machine
./monitor_stack.py --remote-ip 192.168.1.100

# Or via make
make monitor-remote REMOTE_IP=192.168.1.100
make monitor-remote REMOTE_IP=192.168.1.100 NODE=/slam_toolbox
```
> Requires SSH key auth to the remote host and matching `ROS_DOMAIN_ID`.

### Compare Before/After Performance
```bash
# Baseline
./monitor_stack.py --session baseline --duration 120

# After changes
./monitor_stack.py --session after_optimization --duration 120

# Compare visualizations in monitoring_sessions/*/visualizations/
```

---

##  Thread vs PID Monitoring Modes

### Thread Mode (Default - More Detailed)
- Tracks individual threads (TIDs)
- Shows per-thread CPU usage and core affinity
- More overhead but detailed insights
- Use: `make monitor`, `make resources-threads`

### PID Mode (Lighter - Process Level)
- Tracks processes (PIDs) only
- Lower monitoring overhead
- Good for production/long-term monitoring
- Use: `make monitor-pid`, `make resources-pid`

---

##  Quick Commands Cheat Sheet

| Command | What It Does |
|---------|-------------|
| `make monitor` | Start full monitoring with threads (graph + resources) |
| `make monitor-pid` | Start full monitoring with PIDs only (lighter) |
| `make monitor-gpu` | Full monitoring + Intel GPU metrics |
| `make monitor NODE=/node_name` | Monitor specific node with threads |
| `make monitor-remote REMOTE_IP=<ip>` | Monitor ROS2 pipeline on a remote machine |
| `make monitor-remote REMOTE_IP=<ip> GPU=1 NPU=1` | Remote + GPU + NPU |
| `make monitor-remote-pid REMOTE_IP=<ip>` | Remote monitoring, PID mode |
| `make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3` | N back-to-back remote sessions |
| `make picknplace` | Single PicknPlace AMR simulation + monitor |
| `make picknplace-repeat REPEAT=3` | N PicknPlace runs back-to-back |
| `make quick-check` | 30-second performance check |
| `make list-sessions` | Show all previous sessions |
| `make visualize-last` | Re-generate visualizations for last session |
| `make visualize-last ALGORITHM=picknplace` | Visualize latest picknplace session |
| `make visualize-gpu` | GPU dashboard for last session |
| `make visualize-npu` | NPU dashboard for last session |
| `make pipeline-graph` | rqt_graph-style node→topic→node PNG |
| `make view-average` | Average KPIs across last 5 sessions |
| `make view-average-plot RUNS=3` | Average + bar-chart PNGs |
| `make graph-only` | Monitor only timing/graph data |
| `make resources-threads` | Monitor only CPU/memory with thread details |
| `make resources-pid` | Monitor only CPU/memory with PIDs only |
| `make gpu-pids` | One-shot Intel GPU snapshot (engines + per-PID) |
| `make gpu-pids-watch` | Live GPU refresh (Ctrl-C to stop) |
| `make clean` | Delete all monitoring data |
| `make clean-last` | Delete the most recent session |

---

##  Where to Find Your Data

All monitoring data goes to: `monitoring_sessions/<session_name>/`

```
monitoring_sessions/
 <timestamp>/              # flat layout (no --algorithm)
    session_info.txt
    graph_timing.csv
    graph_topology.json
    resource_usage.log
    gpu_usage.log             # present when --gpu / GPU=1
    npu_usage.log             # present when --npu / NPU=1
    visualizations/           # Auto-generated plots
 picknplace/               # algorithm-grouped layout
     <timestamp>/
     average_3/               # cross-run averages after picknplace-repeat
```

---

##  Advanced Options

### Custom Session Name
```bash
./monitor_stack.py --session my_experiment_name
```

### Custom Output Directory
```bash
./monitor_stack.py --output-dir /path/to/results
```

### Timed Monitoring (Auto-Stop)
```bash
./monitor_stack.py --duration 300  # Stop after 5 minutes
```

### Faster Updates
```bash
./monitor_stack.py --interval 1  # Update every second
```

### Disable Auto-Visualization
```bash
./monitor_stack.py --no-visualize
```

### Monitor Only Timing (No CPU Overhead)
```bash
./monitor_stack.py --graph-only --node /critical_node
```

---

##  PicknPlace AMR Simulation

```bash
# Single run
make picknplace

# Repeat N times (cross-run averages auto-saved)
make picknplace-repeat             # 3 runs, 10s pause (default)
make picknplace-repeat REPEAT=5 PAUSE=15
```

Results are organized under `monitoring_sessions/picknplace/`. After a repeat run, cross-session averages are saved to `monitoring_sessions/picknplace/average_N/`.

---

##  Repeat Runs

Run N monitoring sessions back-to-back (useful for benchmarking):

```bash
make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3
make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=5 DURATION=120 PAUSE=10
make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3 GPU=1 NPU=1 ALGORITHM=slam
```

After all runs complete, cross-session averaged KPIs and bar-charts are saved automatically.

---

##  Intel GPU / NPU Monitoring

```bash
# Local GPU monitoring
make monitor-gpu

# Remote GPU and/or NPU
make monitor-remote REMOTE_IP=<ip> GPU=1
make monitor-remote REMOTE_IP=<ip> NPU=1
make monitor-remote REMOTE_IP=<ip> GPU=1 NPU=1

# GPU PID analysis (standalone)
make gpu-pids             # One-shot snapshot
make gpu-pids-watch       # Live refresh

# Visualize
make visualize-gpu        # GPU dashboard (last session)
make visualize-npu        # NPU dashboard (last session)
```

Requires: `sudo setcap cap_perfmon+eip $(which intel_gpu_top)` on the target machine (or `make setup-remote-gpu REMOTE_IP=<ip>`).

---

##  Old Way vs New Way

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
./monitor_stack.py --node /slam_toolbox
# Press Ctrl+C when done - everything is automatic!
```

---

##  Pro Tips

1. **Always name your sessions** for experiments:
   ```bash
   make monitor NODE=/node_name SESSION=experiment_1
   ```

2. **Use quick-check** before long sessions to verify setup:
   ```bash
   make quick-check
   ```

3. **Review previous sessions** to track performance over time:
   ```bash
   make list-sessions
   ```

4. **Clean old data** to save disk space:
   ```bash
   make clean
   ```

5. **Re-visualize** if you want different plot options:
   ```bash
   make visualize-last
   ```

---

##  Troubleshooting

### No ROS2 processes found
- Make sure your ROS2 nodes are running before starting the monitor
- Check: `ros2 node list`

### Monitor exits immediately
- Verify ROS2 environment is sourced: `source /opt/ros/humble/setup.bash`
- Check if the target node exists: `ros2 node list`

### Visualizations not generated
- Check if log files were created in the session directory
- Run visualization manually: `make visualize-last`

### Permission denied
- Make scripts executable: `chmod +x src/*.py monitor_stack.py grafana/*.sh scripts/*.sh`

---

##  Need More Details?

See the full [README.md](README.md) for:
- Individual script documentation
- Detailed API reference
- ROS bag analysis
- Custom workflows
- Advanced use cases
