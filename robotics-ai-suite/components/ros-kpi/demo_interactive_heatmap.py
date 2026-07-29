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

import argparse
import sys
sys.path.insert(0, 'src')  # noqa: E402

from visualize_resources import parse_pidstat_log, aggregate_core_utilization, plot_core_heatmap  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Interactive CPU core heatmap — click cells for detailed thread/memory stats."
    )
    parser.add_argument(
        "session_dir",
        metavar="SESSION_DIR",
        nargs="?",
        help="Path to a monitoring session directory containing resource_usage.log. "
             "Defaults to the most recent session under monitoring_sessions/.",
    )
    return parser.parse_args()


def find_latest_session():
    import os  # noqa: E402
    import glob  # noqa: E402
    candidates = sorted(
        glob.glob("monitoring_sessions/[0-9]*/resource_usage.log")
        + glob.glob("monitoring_sessions/*/[0-9]*/resource_usage.log"),
        key=os.path.getmtime,
        reverse=True,
    )
    if not candidates:
        return None
    return os.path.dirname(candidates[0])


args = parse_args()
session_dir = args.session_dir

if session_dir is None:
    session_dir = find_latest_session()
    if session_dir is None:
        print("Error: no monitoring sessions found. Run monitor_stack.py first or pass SESSION_DIR.")
        sys.exit(1)

log_file = f"{session_dir}/resource_usage.log"

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
