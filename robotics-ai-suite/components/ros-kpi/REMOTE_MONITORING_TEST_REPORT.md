<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Remote Monitoring Test Report
**Remote System:** intel@10.34.94.191 (kpi-mtl-1.ch.intel.com)
**Test Date:** February 27, 2026
**Test Location:** Local machine (sohair@local)

---

## Executive Summary

✅ **Remote resource monitoring is WORKING**
⚠️ **Remote graph monitoring requires local ROS2 installation**

The remote monitoring system successfully connects to intel@10.34.94.191 and monitors ROS2 processes. However, to enable full functionality (graph monitoring), ROS2 needs to be installed on the local monitoring machine.

---

## Test Results

### 1. ✅ SSH Connectivity Test
**Status:** PASSED

- SSH connection to `intel@10.34.94.191` successful
- SSH key authentication configured and working
- No password prompt required

```bash
# Test command:
ssh intel@10.34.94.191 'echo "SSH connection successful"'
# Result: SSH connection successful
```

### 2. ✅ Remote System Prerequisites
**Status:** PASSED

Remote system (intel@10.34.94.191) has all required components:

| Component | Status | Details |
|-----------|--------|---------|
| ROS2 Humble | ✅ Installed | `/opt/ros/humble/setup.bash` |
| pidstat | ✅ Installed | `/usr/bin/pidstat` |
| ROS2 Nodes | ✅ Running | 13 ROS2 processes detected |
| ROS_DOMAIN_ID | ⚠️ Not set | Defaults to 0 |

**Running ROS2 Processes:**
- `gzserver` (Gazebo simulator)
- `rviz2` (Visualization)
- Nav2 stack nodes:
  - `planner_server`
  - `bt_navigator`
  - `smoother_server`
  - `behavior_server`
  - `waypoint_follower`
  - `velocity_smoother`
  - `lifecycle_manager`
  - `robot_state_publisher`
- `wandering_gazebo_tutorial` launch file

### 3. ✅ Remote Resource Monitoring
**Status:** FULLY FUNCTIONAL

Successfully monitored remote ROS2 processes via SSH:

```bash
cd /home/sohair/Documents/GitHub/seanohair22/ros2-kpi
python3 src/monitor_resources.py \
  --remote-ip 10.34.94.191 \
  --remote-user intel \
  --interval 2 \
  --count 3 \
  --memory
```

**Results:**
- ✅ Connected to remote system via SSH
- ✅ Discovered 13 ROS2-related processes
- ✅ Successfully monitored CPU and memory usage
- ✅ Collected 3 samples at 2-second intervals
- ✅ Data shows realistic resource usage (gzserver at ~85-90% CPU, rviz2 at ~500% CPU)

**Sample Output:**
```
Time         UID    PID     %usr  %system  %CPU   RSS     %MEM  Command
04:18:15 PM  1000   102693  85.50  5.50   91.00  526960  0.80  gzserver
04:18:15 PM  1000   103330  555.50 7.00   562.50 257752  0.39  rviz2
04:18:15 PM  1000   103133  10.50  1.00   11.50  46600   0.07  planner_server
04:18:15 PM  1000   103137  11.00  1.50   12.50  50860   0.08  bt_navigator
...
```

### 4. ⚠️ Remote Graph Monitoring
**Status:** REQUIRES LOCAL ROS2 INSTALLATION

Graph monitoring (topic rates, latencies, message flow) currently fails due to missing local dependencies:

**Missing on Local Machine:**
- ❌ `rclpy` Python module (ROS2 Python bindings)
- ❌ `matplotlib` Python module (for visualizations)
- ❌ ROS2 installation (`/opt/ros/humble/setup.bash` not found)
- ❌ `uv` package manager

**Error Message:**
```
ModuleNotFoundError: No module named 'rclpy'
```

---

## Installation Requirements

### To Enable Full Remote Monitoring (Graph + Resources)

#### 1. Install `uv` Package Manager
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

#### 2. Install ROS2 Humble
```bash
# Add ROS2 repository
sudo apt update && sudo apt install -y software-properties-common curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
    http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | \
    sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Humble
sudo apt update
sudo apt install -y ros-humble-ros-base python3-rosdep

# Source ROS2 (add to ~/.bashrc for persistence)
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
```

#### 3. Install Python Dependencies
```bash
cd /home/sohair/Documents/GitHub/seanohair22/ros2-kpi
make install
# or manually:
uv sync
```

#### 4. Verify Installation
```bash
# Source ROS2
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0

# Check Python packages
uv run python -c "import matplotlib, numpy, psutil, rclpy; print('✅ All modules OK')"
```

---

## Current Workaround: Resource Monitoring Only

While waiting for full installation, you can still use **resource monitoring** (which works perfectly):

### Method 1: Direct Script Execution
```bash
cd /home/sohair/Documents/GitHub/seanohair22/ros2-kpi

# Monitor remote system resources
python3 src/monitor_resources.py \
  --remote-ip 10.34.94.191 \
  --remote-user intel \
  --interval 2 \
  --memory \
  --threads \
  --continuous \
  --log monitoring.log
```

### Method 2: Monitor Stack (Resources Only)
```bash
cd /home/sohair/Documents/GitHub/seanohair22/ros2-kpi

# After installing dependencies, use:
python3 src/monitor_stack.py \
  --remote-ip 10.34.94.191 \
  --remote-user intel \
  --resources-only \
  --duration 60 \
  --session remote_monitor
```

---

## Quick Reference Commands

### List Running ROS2 Processes on Remote System
```bash
python3 src/monitor_resources.py --remote-ip 10.34.94.191 --remote-user intel --list
```

### Monitor Specific Time Period
```bash
python3 src/monitor_resources.py \
  --remote-ip 10.34.94.191 \
  --remote-user intel \
  --interval 5 \
  --count 12 \
  --memory \
  --threads
# Monitors for 60 seconds (5s interval × 12 samples)
```

### Continuous Monitoring with Logging
```bash
python3 src/monitor_resources.py \
  --remote-ip 10.34.94.191 \
  --remote-user intel \
  --continuous \
  --memory \
  --threads \
  --log "$(date +%Y%m%d_%H%M%S)_remote_monitor.log"
```

---

## ROS_DOMAIN_ID Configuration

⚠️ **Important:** Ensure `ROS_DOMAIN_ID` matches on both machines for graph monitoring!

### On Local Machine:
```bash
export ROS_DOMAIN_ID=0
```

### On Remote Machine (intel@10.34.94.191):
```bash
ssh intel@10.34.94.191 "echo 'export ROS_DOMAIN_ID=0' >> ~/.bashrc"
```

Or add to the remote system's launch files.

---

## Troubleshooting

### Issue: "Permission denied (publickey,password)"
**Solution:** SSH keys are now configured and working ✅

### Issue: "ModuleNotFoundError: No module named 'rclpy'"
**Solution:** Install ROS2 locally (see Installation Requirements above)

### Issue: "ModuleNotFoundError: No module named 'matplotlib'"
**Solution:** Install Python packages via `make install` or `uv sync`

### Issue: Cannot discover remote ROS2 nodes
**Possible causes:**
1. ROS_DOMAIN_ID mismatch between local and remote
2. Firewall blocking DDS discovery (UDP ports 7400-7700)
3. Network segmentation preventing multicast

**Check:**
```bash
# On local machine (after ROS2 is installed):
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
ros2 node list

# Should eventually show remote nodes if discovery works
```

---

## Next Steps

1. ✅ **SSH connectivity is confirmed and working**
2. ✅ **Remote resource monitoring is fully functional**
3. ⚠️ **Install ROS2 and dependencies on local machine to enable full monitoring**
4. 🔲 **Test full remote monitoring after installation:**
   ```bash
   make monitor-remote REMOTE_IP=10.34.94.191 REMOTE_USER=intel DURATION=60
   ```

---

## Summary

The remote monitoring infrastructure is **working correctly** for resource monitoring. The remote system (intel@10.34.94.191) has all necessary components and is running a full ROS2 Nav2 stack with Gazebo simulation.

To unlock the full monitoring capability (including graph/topic monitoring), install ROS2 and Python dependencies on the local monitoring machine as described in the Installation Requirements section.

**Remote Resource Monitoring: ✅ VERIFIED AND WORKING**
**Remote Graph Monitoring: ⚠️ REQUIRES LOCAL ROS2 INSTALLATION**
