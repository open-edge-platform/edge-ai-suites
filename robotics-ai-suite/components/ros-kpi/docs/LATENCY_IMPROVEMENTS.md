<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Latency Measurement Improvements

## Overview

The ROS2 KPI monitoring stack has been enhanced with improved latency measurement capabilities that align with the Intel ECI `performance_test` tool methodology.

## What Changed

### 1. New Roundtrip Latency Tester (`latency_tester.py`)

A new standalone tool for measuring roundtrip latency similar to `performance_test`:

**Features:**
- **Roundtrip measurement**: Embeds timestamps in messages and measures full cycle
- **Statistical tracking**: Min, max, mean, variance, std dev, percentiles (99th, 99.9th)
- **Main/Relay modes**: Just like performance_test
- **CSV logging**: Detailed per-message logs
- **Industrial evaluation**: Automatic pass/fail against timing budgets
- **Configurable QoS**: BEST_EFFORT/RELIABLE, VOLATILE/TRANSIENT_LOCAL

### 2. Enhanced `ros2_graph_monitor.py`

The existing monitor now tracks comprehensive latency statistics for each topic:

**New Features:**
- **LatencyStatistics class**: Tracks min/max/mean/variance like performance_test
- **Real-time display**: Shows latency stats (min/max/mean) during monitoring
- **Enhanced CSV output**: Includes latency_min_ms, latency_max_ms, latency_mean_ms, latency_variance_ms
- **Better processing delay tracking**: Statistics for input→output delays

## Usage

### Roundtrip Latency Testing (performance_test-style)

#### Terminal 1 - Main Node (Measures Latency)
```bash
source /opt/ros/humble/setup.bash
cd ~/Documents/ros2-kpi

# Basic test (1000 Hz, 60 seconds)
uv run latency-tester --mode Main --rate 1000 --max-runtime 60

# With CSV logging
uv run latency-tester --mode Main --rate 1000 --max-runtime 60 \
  --logfile roundtrip_test.csv

# High-frequency test (2000 Hz like ECI example)
uv run latency-tester --mode Main --rate 2000 --max-runtime 30 \
  --reliability RELIABLE --logfile 2khz_test.csv
```

#### Terminal 2 - Relay Node (Echoes Back)
```bash
source /opt/ros/humble/setup.bash
cd ~/Documents/ros2-kpi

uv run latency-tester --mode Relay
```

### Enhanced Monitoring with Latency Stats

```bash
# Monitor a specific node with improved latency tracking
source /opt/ros/humble/setup.bash
cd ~/Documents/ros2-kpi

uv run python src/ros2_graph_monitor.py \
  --node /your_node \
  --log-file timing_with_stats.csv

# The CSV will now include these columns:
# - latency_min_ms
# - latency_max_ms  
# - latency_mean_ms
# - latency_variance_ms
```

### Example Output

#### Roundtrip Latency Test Results
```
======================================================================
FINAL RESULTS
======================================================================

Test Configuration:
  Mode:        Main
  Rate:        1000 Hz
  Runtime:     60.00 s
  Message Size: 1024 bytes

Message Statistics:
  Sent:        60000
  Received:    59998
  Lost:        2 (0.00%)

Latency Statistics (ms):
  Samples:     59998
  Min:         0.0391
  Max:         0.6492
  Mean:        0.0724
  Std Dev:     0.0103
  Variance:    0.000106
  99th %:      0.1234
  99.9th %:    0.2456

======================================================================
INDUSTRIAL EVALUATION (1000 Hz → 1.000ms budget)
======================================================================
  Failures (>1.000ms): 0 / 59998 (0.0%)
  Worst case: 0.6492 ms

   EXCELLENT - Even worst case within 1.000ms budget

  Jitter (CoV): 14.2%
      Moderate jitter
======================================================================
```

#### Enhanced Monitor Output
```
[10:30:15.123456] Output on /cmd_vel: Delay = 0.0852 ms [ID matched] 
    (min=0.0391, max=0.1486, mean=0.0724)
[10:30:15.223789] Output on /cmd_vel: Delay = 0.0765 ms [ID matched] 
    (min=0.0391, max=0.1486, mean=0.0718)
```

## Comparison with performance_test

| Feature | performance_test | Our Implementation |
|---------|------------------|-------------------|
| Roundtrip measurement |  |  (latency_tester.py) |
| Min/Max/Mean/Variance |  |  |
| Main/Relay modes |  |  |
| Configurable rates |  |  |
| QoS configuration |  |  |
| CSV logging |  |  |
| Industrial evaluation |  |  |
| Message ID matching |  |  (via header stamps) |
| Live monitoring |  |  (ros2_graph_monitor) |
| Multi-topic tracking |  |  (ros2_graph_monitor) |

## Integration with Existing Tools

The improvements integrate seamlessly:

1. **Standalone testing**: Use `latency-tester` for baseline performance validation
2. **Live monitoring**: Use `ros2_graph_monitor` for real-world application monitoring
3. **Compare results**: Benchmark with `latency-tester`, then monitor production with `ros2_graph_monitor`

### Workflow Example

```bash
# 1. Baseline with latency-tester (Terminal 1 & 2)
uv run latency-tester --mode Main --rate 1000 --logfile baseline.csv
uv run latency-tester --mode Relay

# 2. Monitor real application
ros2 launch your_package your_launch_file.py

# 3. Track performance (Terminal 3)
uv run python src/ros2_graph_monitor.py \
  --node /your_critical_node \
  --log-file production.csv

# 4. Compare baseline vs production
python3 << EOF
import pandas as pd

baseline = pd.read_csv('baseline.csv', skiprows=6)
production = pd.read_csv('production.csv')

print(f"Baseline latency:    {baseline['latency_ms'].mean():.4f} ms")
print(f"Production latency:  {production['latency_mean_ms'].mean():.4f} ms")
print(f"Overhead:            {(production['latency_mean_ms'].mean() - baseline['latency_ms'].mean()):.4f} ms")
EOF
```

## Technical Details

### Latency Statistics Class

The `LatencyStatistics` class tracks:
- **Samples**: Total count of latency measurements
- **Min/Max**: Best and worst case latency
- **Values**: Rolling window of last 1000 samples
- **Mean**: Calculated from all samples in window
- **Variance/Std Dev**: Statistical spread
- **Reset**: Can clear stats for new test runs

### Message ID Matching

The improved monitor uses ROS2 header timestamps to match input→output messages:
1. Input message arrives with `header.stamp`
2. Timestamp stored in `input_msg_ids` dictionary
3. Output message echoes same `header.stamp`  
4. Match found → precise delay calculation
5. No match → fallback to most recent input timestamp

### CSV Format

Enhanced CSV includes comprehensive statistics:
```csv
timestamp,wall_time,topic_name,msg_type,is_input,is_output,message_count,
delta_time_ms,frequency_hz,processing_delay_ms,latency_min_ms,latency_max_ms,
latency_mean_ms,latency_variance_ms
```

## Files Changed

1. **src/latency_tester.py** - New roundtrip latency measurement tool
2. **src/ros2_graph_monitor.py** - Enhanced with LatencyStatistics class
3. **pyproject.toml** - Added `latency-tester` script entry point

## Next Steps

Consider these enhancements:
- Add CPU affinity and RT priority to `latency_tester` (like ECI performance_test)
- Implement percentile tracking in `LatencyStatistics`
- Add Prometheus metrics for latency statistics
- Create visualization tool for comparing baseline vs production latency

## References

- [Intel ECI DDS/RTSP Benchmark Documentation](https://eci.intel.com/docs/3.1/development/performance/benchmarks.html)
- [Apex.AI performance_test](https://gitlab.com/ApexAI/performance_test)
