<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Interactive Core Heatmap Feature

## Overview

The enhanced core heatmap visualization now provides interactive click functionality to display detailed performance metrics for any core at any time point during monitoring.

## Features

### Hover Preview
- **Move your mouse** over any cell in the heatmap
- See a quick preview showing:
  - Time and core number
  - Total CPU utilization
  - Top 3 active threads/processes
  - Quick hint to click for more details

### Click for Details
- **Click on any cell** to open a detailed performance window showing:
  
  **CPU Statistics**
  - CPU utilization percentage
  
  **Memory Statistics**
  - RSS (Resident Set Size) in MB - actual physical memory used
  - VSZ (Virtual Size) in MB - total virtual memory allocated
  - Memory percentage of total system RAM
  - Minor page faults per second
  - Major page faults per second
  
  **Process/Thread Details**
  - Complete list of all threads/processes on that core at that time
  - Individual CPU and memory usage for each thread
  - Command names for identification

## Usage

### Via Makefile (Recommended)
```bash
# After running a monitoring session
make interactive-heatmap
```

### Via Python Script
```bash
uv run python demo_interactive_heatmap.py
```

### Via Visualization Tool
```bash
uv run python src/visualize_resources.py monitoring_sessions/<session_name>/resource_usage.log \
    --output-dir monitoring_sessions/<session_name>/visualizations \
    --heatmap --show
```

## Example Workflow

```bash
# 1. Run monitoring
make monitor

# 2. Open interactive heatmap
make interactive-heatmap

# 3. Explore the data:
#    - Hover over different cores to see activity
#    - Click on high-utilization cells (red/orange)
#    - Review memory usage patterns
#    - Identify which threads are using which cores
```

## Understanding the Data

### CPU Utilization Colors
- **Dark Red**: High CPU usage (>80%)
- **Orange/Yellow**: Moderate usage (20-80%)
- **Light Yellow**: Low usage (<20%)
- **White**: No activity (0%)

### Memory Metrics Explained

**RSS (Resident Set Size)**
- Physical RAM actually being used
- Most important metric for memory consumption
- Measured in MB

**VSZ (Virtual Size)**
- Total virtual memory allocated
- Includes swap and memory-mapped files
- Often larger than RSS

**Memory %**
- Percentage of total system RAM being used
- Sum of all threads on a core

**Page Faults**
- **Minor faults (minflt/s)**: Page was in RAM but not mapped (fast)
- **Major faults (majflt/s)**: Page had to be loaded from disk (slow, indicates memory pressure)

## Tips

1. **Look for patterns**: Consistent high utilization on specific cores may indicate thread affinity settings
2. **Memory spikes**: High RSS with high major faults suggests memory pressure
3. **Core migration**: Threads jumping between cores show up in the detailed view
4. **Idle cores**: All-white columns indicate cores not used by ROS2 processes

## Technical Details

The feature parses `pidstat -u -r -t` output which includes:
- CPU utilization per thread
- Memory usage statistics
- Page fault counters
- Core affinity tracking

All data is captured at the configured monitoring interval (default 5 seconds).
