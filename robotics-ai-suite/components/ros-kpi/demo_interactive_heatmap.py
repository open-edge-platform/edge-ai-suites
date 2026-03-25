#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Demo script to show the interactive core heatmap with click functionality.
Displays detailed memory and performance stats when clicking on heatmap cells.
"""

import sys
sys.path.insert(0, 'src')

from visualize_resources import parse_pidstat_log, aggregate_core_utilization, plot_core_heatmap
import matplotlib.pyplot as plt

# Path to latest monitoring session
log_file = 'monitoring_sessions/20260303_164631/resource_usage.log'

print("=" * 80)
print("INTERACTIVE CORE HEATMAP DEMO")
print("=" * 80)
print()
print("Loading monitoring data...")
data, sessions = parse_pidstat_log(log_file)
core_data = aggregate_core_utilization(data)

print(f"✓ Loaded {len(data['threads'])} threads across {len(core_data)} cores")
print()
print("Instructions:")
print("  • HOVER over heatmap cells to see a quick preview")
print("  • CLICK on a cell to open a detailed performance window showing:")
print("    - CPU utilization")
print("    - Memory usage (RSS, VSZ, %)")
print("    - Page fault statistics")
print("    - All threads/processes on that core at that time")
print()
print("Opening interactive heatmap...")
print()

# Create the interactive heatmap
plot_core_heatmap(core_data, data)

# Show the plot
plt.show()

print()
print("Demo complete!")
