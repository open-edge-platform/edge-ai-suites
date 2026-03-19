<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Latency Testing - Quick Reference

## Make Targets for Latency Testing

### Local Testing

#### Terminal 1 - Start Relay Node
```bash
cd ~/Documents/ros2-kpi
source /opt/ros/humble/setup.bash
make latency-test-relay
```

#### Terminal 2 - Run Latency Test
```bash
cd ~/Documents/ros2-kpi
source /opt/ros/humble/setup.bash

# Default test (1000 Hz, 60 seconds)
make latency-test-main

# Custom parameters
make latency-test-main RATE=2000 DURATION=30 LOGFILE=my_test.csv

# Quick 30-second test
make latency-quick

# With RELIABLE QoS
make latency-test-main RATE=1000 DURATION=60 RELIABILITY=RELIABLE
```

### Remote Testing

#### Remote System - Start Relay Node
```bash
# On remote machine (192.168.1.100)
cd ~/Documents/ros2-kpi
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
make latency-test-relay
```

#### Local System - Run Remote Latency Test
```bash
cd ~/Documents/ros2-kpi

# Test with remote relay
make latency-remote-main REMOTE_IP=192.168.1.100

# Custom parameters
make latency-remote-main REMOTE_IP=192.168.1.100 RATE=2000 DURATION=60

# With specific user
make latency-remote-main REMOTE_IP=192.168.1.100 REMOTE_USER=username
```

### Or Run Relay on Remote
```bash
# Local machine - start relay
make latency-test-relay

# Remote machine - run test
make latency-remote-main REMOTE_IP=<local_ip>
```

## Available Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `RATE` | Publishing rate (Hz) | 1000 | `RATE=2000` |
| `DURATION` | Test runtime (seconds) | 60 | `DURATION=30` |
| `MSGSIZE` | Message size (bytes) | 1024 | `MSGSIZE=4096` |
| `LOGFILE` | CSV output file | Auto-generated | `LOGFILE=test.csv` |
| `RELIABILITY` | QoS reliability | BEST_EFFORT | `RELIABILITY=RELIABLE` |
| `DURABILITY` | QoS durability | VOLATILE | `DURABILITY=TRANSIENT_LOCAL` |
| `REMOTE_IP` | Remote machine IP | - | `REMOTE_IP=192.168.1.100` |
| `REMOTE_USER` | Remote SSH user | Current user | `REMOTE_USER=intel` |
| `ROS_DOMAIN_ID` | ROS domain ID | 0 | `ROS_DOMAIN_ID=42` |

## Complete Examples

### 1. Basic Local Test
```bash
# Terminal 1
make latency-test-relay

# Terminal 2
make latency-test-main DURATION=60
```

### 2. High-Frequency Test (2000 Hz like ECI benchmark)
```bash
# Terminal 1
make latency-test-relay

# Terminal 2
make latency-test-main RATE=2000 DURATION=30 RELIABILITY=RELIABLE LOGFILE=2khz_test.csv
```

### 3. Remote Testing
```bash
# Remote machine (192.168.1.100)
make latency-test-relay

# Local machine
make latency-remote-main REMOTE_IP=192.168.1.100 RATE=1000 DURATION=60
```

### 4. Compare with performance_test

#### Using performance_test (Intel ECI):
```bash
# Terminal 1
ros2 run performance_test perf_test --roundtrip-mode Relay

# Terminal 2
ros2 run performance_test perf_test \
  --roundtrip-mode Main \
  --rate 1000 \
  --msg Array1k \
  --max-runtime 60 \
  --print-to-console
```

#### Using our tool (equivalent):
```bash
# Terminal 1
make latency-test-relay

# Terminal 2
make latency-test-main RATE=1000 DURATION=60 MSGSIZE=1024
```

## Analyzing Results

### View Last Test Results
```bash
# Find the CSV file
ls -lt *.csv | head -1

# Analyze with Python
python3 << 'EOF'
import pandas as pd

# Read the CSV (skip metadata header)
df = pd.read_csv('latency_test_20260305_123456.csv', skiprows=6)

print("Latency Summary:")
print(df['latency_ms'].describe())

# Check failures (for 1000 Hz)
failures = (df['latency_ms'] > 1.0).sum()
print(f"\nFailures (>1ms): {failures} / {len(df)}")
EOF
```

### Compare with Regular Monitoring

Run both tools simultaneously:

```bash
# Terminal 1 - Relay
make latency-test-relay

# Terminal 2 - Monitor
make monitor

# Terminal 3 - Latency test
make latency-test-main RATE=1000 DURATION=60
```

Results:
- `latency_test_*.csv` - Roundtrip latency benchmarks
- `monitoring_sessions/*/graph_timing.csv` - Real-world monitoring data

## Troubleshooting

### Relay not receiving messages
```bash
# Check ROS_DOMAIN_ID matches
echo $ROS_DOMAIN_ID

# Set explicitly
export ROS_DOMAIN_ID=0
make latency-test-relay
```

### Remote connection issues
```bash
# Test SSH connection
ssh user@192.168.1.100 'echo OK'

# Verify ROS2 on remote
ssh user@192.168.1.100 'source /opt/ros/humble/setup.bash && ros2 node list'

# Check network connectivity
ros2 topic list  # Should see test_topic and test_topic_reply
```

### No data in CSV
Ensure Relay node is running BEFORE starting Main node:
1. Start Relay first: `make latency-test-relay`
2. Wait for "Latency Tester (Relay mode) started"
3. Then start Main: `make latency-test-main`

## Integration with Performance Monitoring

### Workflow: Baseline → Real-world → Compare

```bash
# Step 1: Establish baseline with latency-tester
make latency-test-relay &
sleep 2
make latency-test-main RATE=1000 DURATION=60 LOGFILE=baseline.csv

# Step 2: Run real application
ros2 launch your_package your_app.launch.py &

# Step 3: Monitor real performance
make monitor NODE=/your_critical_node DURATION=120

# Step 4: Compare
python3 << 'EOF'
import pandas as pd

baseline = pd.read_csv('baseline.csv', skiprows=6)
monitor = pd.read_csv('monitoring_sessions/latest/graph_timing.csv')

print(f"Baseline mean latency: {baseline['latency_ms'].mean():.4f} ms")
print(f"Real-world mean delay: {monitor['processing_delay_ms'].mean():.4f} ms")
print(f"Overhead: {monitor['processing_delay_ms'].mean() - baseline['latency_ms'].mean():.4f} ms")
EOF
```

This gives you:
- **Baseline**: Theoretical DDS performance limit
- **Real-world**: Actual application performance
- **Gap**: Processing overhead from your application logic
