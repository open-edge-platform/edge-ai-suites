<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# ROS2 KPI Monitoring Toolkit - Quick Start Guide

## Installation

```bash
# Clone the repository
cd ~/Documents
git clone <your-repo-url> ros2-kpi
cd ros2-kpi

# Install dependencies
make install
```

## Easiest Way to Use

### Option 1: Interactive Launcher (Recommended)
```bash
./quickstart
```

This interactive menu guides you through:
- Monitoring your ROS2 application
- Running Wandering and Pick-n-Place simulations with rosbag recording
- Analyzing rosbag results
- Quick health checks
- Starting Grafana dashboards

### Option 2: Make Shortcuts
```bash
# Quick start
make start          # Same as ./quickstart

# Quick health check (30 seconds)
make quick
```

## Common Tasks

### Monitor Your ROS2 Application

**Simplest:**
```bash
./quickstart         # Choose option 1
```

**Command line:**
```bash
# Monitor all nodes for 60 seconds
make monitor

# Monitor specific node
make monitor NODE=/your_node_name DURATION=120

# Quick 30-second check
make quick
```

### View Dashboards

```bash
# Start Grafana/Prometheus
make grafana-start

# Check status / open http://localhost:30000 (admin/admin)
make grafana-status

# Stop when done
make grafana-stop
```

## What Gets Measured

- **Message frequencies** - Hz for each topic
- **Latency statistics** - Min/max/mean/variance
- **Processing delays** - Input→output timing
- **Resource usage** - CPU, memory per thread/process
- **System metrics** - Overall performance

## Results Location

All results are saved in timestamped folders:
```
monitoring_sessions/
└── YYYYMMDD_HHMMSS/
    ├── graph_timing.csv         # Topic timing data
    ├── resource_usage.log        # CPU/memory usage
    ├── session_info.txt          # Test configuration
    └── visualizations/           # Auto-generated plots
```

View results:
```bash
# List all sessions
make list-sessions

# Re-visualize last session
make visualize-last

# Analyze specific session
make analyze-session SESSION=20260305_123456
```

## Advanced Usage

### Remote Monitoring
```bash
# Monitor remote system
make monitor-remote REMOTE_IP=192.168.1.100
```

### Custom Parameters
```bash
# Extended monitoring (5 minutes)
make monitor-long DURATION=300

# Wandering benchmark (5 runs)
make wandering-benchmark RUNS=5 TIMEOUT=180

# Pick-n-Place benchmark (5 runs)
make picknplace-benchmark RUNS=5
```

### All Available Commands
```bash
make help           # Show all commands
```

## Troubleshooting

### ROS2 Not Found
```bash
# Source ROS2 (Humble or Jazzy)
source /opt/ros/humble/setup.bash   # or /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0
```

See the [Intel Robotics AI Suite Getting Started Guide](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html) for installation instructions.

Or use the auto-setup script:
```bash
source ./auto-setup.sh
```

### No Nodes Detected
Make sure your ROS2 application is running first:
```bash
# Example: Start turtlesim for testing
ros2 run turtlesim turtlesim_node
```

Then run the monitoring in another terminal.

### Permission Denied
```bash
chmod +x quickstart auto-setup.sh
```

### UV Not Found
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

## Examples

### Example 1: Monitor Navigation Stack
```bash
# Terminal 1: Start your robot navigation
ros2 launch nav2_bringup tb3_simulation_launch.py

# Terminal 2: Monitor it
./quickstart
# Choose: 1) Monitor my ROS2 application
# Select the node you want to monitor
```

### Example 2: Compare Before/After Optimization
```bash
# Before optimization
make monitor NODE=/my_node DURATION=120

# Note the session name, then optimize your code

# After optimization
make monitor NODE=/my_node DURATION=120

# Compare
make compare-sessions
```

## Documentation

- **Full documentation**: See `docs/` folder
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Support

For issues or questions:
1. Check `make help` for all available commands
2. Review documentation in `docs/` folder
3. Run `make check-deps` to verify installation

---

**TL;DR:**
```bash
./quickstart    # Interactive menu - easiest way!
make quick      # Quick health check
make start      # Same as ./quickstart
make help       # Show all commands
```
