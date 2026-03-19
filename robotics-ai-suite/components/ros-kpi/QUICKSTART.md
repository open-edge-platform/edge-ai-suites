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
- Testing DDS/RTSP latency
- Quick health checks
- Starting Grafana dashboards
- Viewing results

### Option 2: Make Shortcuts
```bash
# Quick start
make start          # Same as ./quickstart

# Quick health check (30 seconds)
make quick

# Quick latency test
make test
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

### Test DDS/RTSP Latency

**Terminal 1:**
```bash
./quickstart         # Choose option 7 (hidden relay option)
# Or: make latency-test-relay
```

**Terminal 2:**
```bash
./quickstart         # Choose option 2
# Or: make latency-test-main RATE=1000 DURATION=60
```

### View Dashboards

```bash
# Start Grafana/Prometheus
make grafana-start

# Open in browser (http://localhost:3000)
make grafana-open

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

# Remote latency test
make latency-remote-main REMOTE_IP=192.168.1.100
```

### Custom Parameters
```bash
# Extended monitoring (5 minutes)
make monitor-long DURATION=300

# High-frequency benchmark (10 minutes)
make benchmark NODE=/critical_node

# Custom latency test
make latency-test-main RATE=2000 DURATION=60 RELIABILITY=RELIABLE

# Export to Grafana
make grafana-export SESSION=20260305_123456
```

### All Available Commands
```bash
make help           # Show all commands
```

## Troubleshooting

### ROS2 Not Found
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
```

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
chmod +x quickstart auto-setup.sh test_latency_improvements.sh
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

### Example 2: Benchmark DDS Performance
```bash
# Terminal 1: Start relay
make latency-test-relay

# Terminal 2: Test at 2000 Hz (like Intel ECI benchmark)
make latency-test-main RATE=2000 DURATION=30 RELIABILITY=RELIABLE
```

### Example 3: Compare Before/After Optimization
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
- **Latency improvements**: [docs/LATENCY_IMPROVEMENTS.md](docs/LATENCY_IMPROVEMENTS.md)
- **Quick reference**: [docs/LATENCY_TESTING_QUICK_REF.md](docs/LATENCY_TESTING_QUICK_REF.md)
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
