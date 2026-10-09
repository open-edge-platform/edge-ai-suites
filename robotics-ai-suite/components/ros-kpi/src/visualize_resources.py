#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Visualize ROS2 resource monitoring data from resource_usage.json (written by
_psutil_probe.py via monitor_resources.py).
Creates interactive plots showing CPU utilization per core and per PID/thread over time.
"""

import re
import json
import argparse
from datetime import datetime
from collections import defaultdict

from monitor_resources import is_ros2_process

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from log_config import get_logger

logger = get_logger(__name__)
try:
    from ._accel import np  # type: ignore[import-not-found]
except ImportError:  # running as a script (e.g., `python src/visualize_resources.py`)
    from _accel import np  # Intel dpnp/numpy shim


def parse_resource_log(log_file):
    """
    Parse resource_usage.json, a single JSON document written by
    _psutil_probe.py (see monitor_resources.py):
    `{"num_cpus": N, "ros2_pids": [...], "started_at": "...", "ended_at":
    "...", "samples": [{"ts": "...", "processes": [{"pid", "cpu_pct",
    "rss_kb", ...}]}, ...]}`.

    Returns:
        dict: Parsed data with timestamps, PIDs, CPU cores, and utilization
    """
    data = {
        'timestamps': [],
        'pids': defaultdict(list),
        'cores': defaultdict(list),
        'threads': defaultdict(list),
        'tgid_commands': {},
        'num_cpus': 0,
        'ros2_pids': set(),
        'ros2_node_map': {},
        'has_memory': False,
        'has_io': False,
        'has_ctx': False,
    }

    monitoring_sessions = []

    with open(log_file, 'r') as f:
        try:
            document = json.load(f)
        except json.JSONDecodeError:
            return data, monitoring_sessions

    data['num_cpus'] = document.get('num_cpus', 0) or 0
    data['ros2_pids'].update(document.get('ros2_pids') or [])
    data['ros2_node_map'].update(document.get('ros2_node_map') or {})

    started_at = document.get('started_at')
    if started_at:
        monitoring_sessions.append({'start': started_at, 'data_points': []})

    for rec in document.get('samples', []):
        ts_iso = rec.get('ts')
        if not ts_iso:
            continue
        try:
            time_str = datetime.fromisoformat(ts_iso).strftime('%H:%M:%S')
        except ValueError:
            continue
        if time_str not in data['timestamps']:
            data['timestamps'].append(time_str)

        for p in rec.get('processes', []):
            pid = str(p.get('pid'))
            command = p.get('cmdline') or p.get('name') or ''
            data['tgid_commands'][pid] = command
            if 'rss_kb' in p:
                data['has_memory'] = True
            if 'io_read_bytes' in p or 'io_write_bytes' in p:
                data['has_io'] = True
            if 'ctx_switches_voluntary' in p or 'ctx_switches_involuntary' in p:
                data['has_ctx'] = True
            data['pids'][pid].append({
                'time':    time_str,
                'cpu':     p.get('cpu_pct', 0.0),
                'core':    p.get('core') if p.get('core') is not None else 0,
                'command': command,
                'minflt':  0,
                'majflt':  0,
                'vsz':     p.get('vsz_kb', 0),
                'rss':     p.get('rss_kb', 0),
                'mem_pct': p.get('mem_pct', 0),
                'io_read':  p.get('io_read_bytes', 0),
                'io_write': p.get('io_write_bytes', 0),
                'ctx_voluntary':   p.get('ctx_switches_voluntary', 0),
                'ctx_involuntary': p.get('ctx_switches_involuntary', 0),
            })
            for t in p.get('threads', []) or []:
                tid = str(t.get('tid'))
                data['threads'][tid].append({
                    'time':    time_str,
                    'cpu':     t.get('cpu_pct', 0.0),
                    'core':    p.get('core') if p.get('core') is not None else 0,
                    'command': command,
                    'tgid':    pid,
                    'minflt':  0,
                    'majflt':  0,
                    'vsz':     p.get('vsz_kb', 0),
                    'rss':     p.get('rss_kb', 0),
                    'mem_pct': p.get('mem_pct', 0),
                })

    return data, monitoring_sessions


def aggregate_core_utilization(data):
    """
    Aggregate CPU utilization by core over time.
    Works with both thread mode and PID-only mode.

    Returns:
        dict: core -> list of (timestamp, total_cpu%)
    """
    core_usage = defaultdict(lambda: defaultdict(float))

    # Aggregate thread data by core and timestamp (if available)
    for _, records in data['threads'].items():
        for record in records:
            time_str = record['time']
            core = record['core']
            cpu_pct = record['cpu']
            core_usage[time_str][core] += cpu_pct

    # Aggregate PID data by core and timestamp (if threads not available)
    if not data['threads'] and data['pids']:
        for _, records in data['pids'].items():
            for record in records:
                time_str = record['time']
                core = record['core']
                cpu_pct = record['cpu']
                core_usage[time_str][core] += cpu_pct

    # Convert to final structure
    result = defaultdict(list)
    for time_str in sorted(core_usage.keys()):
        for core, total_cpu in core_usage[time_str].items():
            result[core].append((time_str, total_cpu))

    return result


def plot_core_utilization(core_data, output_file=None):
    """
    Plot CPU utilization per core over time.
    """
    fig, ax = plt.subplots(figsize=(14, 8))

    colors = plt.cm.tab20(np.linspace(0, 1, len(core_data)))

    for idx, (core, records) in enumerate(sorted(core_data.items())):
        times = [r[0] for r in records]
        cpus = [r[1] for r in records]

        ax.plot(range(len(times)), cpus, marker='o', label=f'Core {core}',
                color=colors[idx], linewidth=1.5, markersize=3, alpha=0.7)

    ax.axhline(100, color='gray', linestyle='--', linewidth=1.2, alpha=0.6, label='100% = 1 core')
    ax.set_xlabel('Time Index', fontsize=12)
    ax.set_ylabel('CPU Utilization (%)', fontsize=12)
    ax.set_title(
        'ROS2 CPU Utilization by Core Over Time\n'
        '(Click legend to toggle lines  |  Dashed line = 1 full core = 100%)',
        fontsize=14, fontweight='bold'
    )
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', ncol=2)

    # Make legend interactive
    lined = {}
    for legline, origline in zip(legend.get_lines(), ax.get_lines()):
        legline.set_picker(5)  # 5 pts tolerance
        lined[legline] = origline

    def on_pick(event):
        legline = event.artist
        origline = lined[legline]
        visible = not origline.get_visible()
        origline.set_visible(visible)
        legline.set_alpha(1.0 if visible else 0.2)
        fig.canvas.draw()

    fig.canvas.mpl_connect('pick_event', on_pick)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Core utilization plot saved to {output_file}")


def plot_pid_utilization(data, top_n=10, output_file=None):
    """
    Plot CPU utilization for top N PIDs/threads over time.
    Works with both thread mode and PID-only mode.
    """
    # Calculate average CPU usage for each thread/PID to find top N
    item_avg = {}

    # Use threads if available, otherwise use PIDs
    source_data = data['threads'] if data['threads'] else data['pids']
    item_type = 'TID' if data['threads'] else 'PID'

    for item_id, records in source_data.items():
        if records:
            avg_cpu = sum(r['cpu'] for r in records) / len(records)
            item_avg[item_id] = (avg_cpu, records[0]['command'])

    if not item_avg:
        logger.warning("No data to plot")
        return

    # Get top N items
    top_items = sorted(item_avg.items(), key=lambda x: x[1][0], reverse=True)[:top_n]

    fig, ax = plt.subplots(figsize=(14, 8))

    colors = plt.cm.tab20(np.linspace(0, 1, len(top_items)))

    for idx, (item_id, (avg_cpu, command)) in enumerate(top_items):
        records = source_data[item_id]
        times = list(range(len(records)))
        cpus = [r['cpu'] for r in records]

        # Use full command name for legend
        label = f'{item_type} {item_id} ({command}) - avg: {avg_cpu:.1f}%'

        ax.plot(times, cpus, marker='o', label=label,
                color=colors[idx], linewidth=1.5, markersize=3, alpha=0.7)

    ax.axhline(100, color='gray', linestyle='--', linewidth=1.2, alpha=0.6, label='100% = 1 core')
    ax.set_xlabel('Time Index', fontsize=12)
    ax.set_ylabel('CPU Utilization (%)', fontsize=12)
    title = (
        f'Top {top_n} ROS2 {"Threads" if data["threads"] else "Processes"} by CPU Utilization\n'
        f'(Click legend to toggle lines  |  Dashed line = 1 full core = 100%)'
    )
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)

    # Make legend interactive
    lined = {}
    for legline, origline in zip(legend.get_lines(), ax.get_lines()):
        legline.set_picker(5)  # 5 pts tolerance
        lined[legline] = origline

    def on_pick(event):
        legline = event.artist
        origline = lined[legline]
        visible = not origline.get_visible()
        origline.set_visible(visible)
        legline.set_alpha(1.0 if visible else 0.2)
        fig.canvas.draw()

    fig.canvas.mpl_connect('pick_event', on_pick)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"{'PID' if not data['threads'] else 'Thread'} utilization plot saved to {output_file}")


def plot_disk_io(data, top_n=10, output_file=None):
    """
    Plot per-process disk I/O (read/write) over time for the top N processes
    by total bytes transferred.

    Each process's io_read/io_write records are delta-since-last-tick byte
    counts (see _psutil_probe.py's --disk-io), plotted here in KB per sample
    tick -- absolute bytes/sec would require also knowing the sampling
    interval, which parse_resource_log() doesn't track per-record.
    """
    if not data.get('has_io'):
        logger.warning("No disk I/O data to plot (monitor with --io/-d to collect it)")
        return

    item_total = {}
    for pid, records in data['pids'].items():
        total = sum(r.get('io_read', 0) + r.get('io_write', 0) for r in records)
        if total > 0:
            item_total[pid] = (total, records[0]['command'])

    if not item_total:
        logger.warning("No non-zero disk I/O activity found")
        return

    top_items = sorted(item_total.items(), key=lambda x: x[1][0], reverse=True)[:top_n]

    fig, ax = plt.subplots(figsize=(14, 8))
    colors = plt.cm.tab20(np.linspace(0, 1, len(top_items)))

    for idx, (pid, (_total, command)) in enumerate(top_items):
        records = data['pids'][pid]
        times = list(range(len(records)))
        reads = [r.get('io_read', 0) / 1024.0 for r in records]
        writes = [r.get('io_write', 0) / 1024.0 for r in records]

        label_base = f'PID {pid} ({command})'
        ax.plot(times, reads, marker='o', linestyle='-', color=colors[idx],
                linewidth=1.5, markersize=3, alpha=0.7, label=f'{label_base} read')
        ax.plot(times, writes, marker='x', linestyle='--', color=colors[idx],
                linewidth=1.2, markersize=4, alpha=0.7, label=f'{label_base} write')

    ax.set_xlabel('Time Index', fontsize=12)
    ax.set_ylabel('Disk I/O (KB per sample tick)', fontsize=12)
    ax.set_title(
        f'Top {top_n} Processes by Disk I/O\n(solid = read, dashed = write  |  Click legend to toggle lines)',
        fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)

    lined = {}
    for legline, origline in zip(legend.get_lines(), ax.get_lines()):
        legline.set_picker(5)
        lined[legline] = origline

    def on_pick(event):
        legline = event.artist
        origline = lined[legline]
        visible = not origline.get_visible()
        origline.set_visible(visible)
        legline.set_alpha(1.0 if visible else 0.2)
        fig.canvas.draw()

    fig.canvas.mpl_connect('pick_event', on_pick)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Disk I/O plot saved to {output_file}")


def plot_ctx_switches(data, top_n=10, output_file=None):
    """
    Plot per-process involuntary context-switch counts over time for the top
    N processes by total involuntary switches.

    Involuntary switches (the process was preempted by the scheduler, not
    voluntarily yielding e.g. via a blocking syscall) are a privilege-free
    signal of CPU oversubscription/contention -- relevant on constrained
    hardware (see _psutil_probe.py's --ctx-switches). Voluntary switches are
    plotted too (dashed) for context but aren't used for ranking, since a
    process doing lots of blocking I/O/sleeping isn't necessarily contended.
    """
    if not data.get('has_ctx'):
        logger.warning("No context-switch data to plot (monitor with --ctx-switches/-x to collect it)")
        return

    item_total = {}
    for pid, records in data['pids'].items():
        total = sum(r.get('ctx_involuntary', 0) for r in records)
        if total > 0:
            item_total[pid] = (total, records[0]['command'])

    if not item_total:
        logger.warning("No non-zero involuntary context switches found")
        return

    top_items = sorted(item_total.items(), key=lambda x: x[1][0], reverse=True)[:top_n]

    fig, ax = plt.subplots(figsize=(14, 8))
    colors = plt.cm.tab20(np.linspace(0, 1, len(top_items)))

    for idx, (pid, (_total, command)) in enumerate(top_items):
        records = data['pids'][pid]
        times = list(range(len(records)))
        involuntary = [r.get('ctx_involuntary', 0) for r in records]
        voluntary = [r.get('ctx_voluntary', 0) for r in records]

        label_base = f'PID {pid} ({command})'
        ax.plot(times, involuntary, marker='o', linestyle='-', color=colors[idx],
                linewidth=1.5, markersize=3, alpha=0.7, label=f'{label_base} involuntary')
        ax.plot(times, voluntary, marker='x', linestyle='--', color=colors[idx],
                linewidth=1.0, markersize=3, alpha=0.4, label=f'{label_base} voluntary')

    ax.set_xlabel('Time Index', fontsize=12)
    ax.set_ylabel('Context switches per sample tick', fontsize=12)
    ax.set_title(
        f'Top {top_n} Processes by Involuntary Context Switches\n'
        '(solid = involuntary/preempted, dashed = voluntary  |  Click legend to toggle lines)',
        fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)

    lined = {}
    for legline, origline in zip(legend.get_lines(), ax.get_lines()):
        legline.set_picker(5)
        lined[legline] = origline

    def on_pick(event):
        legline = event.artist
        origline = lined[legline]
        visible = not origline.get_visible()
        origline.set_visible(visible)
        legline.set_alpha(1.0 if visible else 0.2)
        fig.canvas.draw()

    fig.canvas.mpl_connect('pick_event', on_pick)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Context-switch plot saved to {output_file}")


def plot_core_heatmap(core_data, data, output_file=None):
    """
    Create a heatmap showing CPU utilization across cores over time.
    Works with both thread mode and PID-only mode.
    """
    # Get all unique cores and times
    all_cores = sorted(set(core_data.keys()))
    all_times = sorted(set(t for records in core_data.values() for t, _ in records))

    if not all_times or not all_cores:
        logger.warning("No data to plot heatmap")
        return

    # Use threads if available, otherwise use PIDs
    source_data = data['threads'] if data['threads'] else data['pids']
    item_type = 'Thread' if data['threads'] else 'Process'
    item_label = 'TID' if data['threads'] else 'PID'

    # Build lookup table: (time, core) -> list of (id, cpu%, command, memory stats)
    core_item_map = defaultdict(list)
    for item_id, records in source_data.items():
        for record in records:
            key = (record['time'], record['core'])
            core_item_map[key].append({
                'id': item_id,
                'cpu': record['cpu'],
                'command': record['command'],
                'mem_pct': record.get('mem_pct', 0),
                'rss': record.get('rss', 0),
                'vsz': record.get('vsz', 0),
                'minflt': record.get('minflt', 0),
                'majflt': record.get('majflt', 0)
            })

    # Create matrix
    matrix = np.zeros((len(all_cores), len(all_times)))

    for core_idx, core in enumerate(all_cores):
        time_to_cpu = {t: cpu for t, cpu in core_data[core]}
        for time_idx, time in enumerate(all_times):
            matrix[core_idx, time_idx] = time_to_cpu.get(time, 0)

    fig, ax = plt.subplots(figsize=(16, 8))

    im = ax.imshow(matrix, aspect='auto', cmap='YlOrRd', interpolation='nearest')

    # Set ticks
    ax.set_yticks(range(len(all_cores)))
    ax.set_yticklabels([f'Core {c}' for c in all_cores])

    # Set x-axis to show every Nth time
    step = max(1, len(all_times) // 20)
    ax.set_xticks(range(0, len(all_times), step))
    ax.set_xticklabels([all_times[i] for i in range(0, len(all_times), step)],
                       rotation=45, ha='right', fontsize=8)

    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('CPU Core', fontsize=12)
    title = (
        'ROS2 CPU Core Utilization Heatmap\n'
        '(Hover to preview | Click for detailed stats | Color scale: 100% = 1 full core)'
    )
    ax.set_title(title, fontsize=14, fontweight='bold')

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('CPU Utilization (%)', rotation=270, labelpad=20)

    # Add hover annotation for interactivity
    annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                        bbox=dict(boxstyle="round", fc="w", alpha=0.95),
                        arrowprops=dict(arrowstyle="->"),
                        fontsize=8)
    annot.set_visible(False)

    def on_hover(event):
        if event.inaxes == ax:
            x, y = int(event.xdata + 0.5), int(event.ydata + 0.5)
            if 0 <= x < len(all_times) and 0 <= y < len(all_cores):
                cpu_val = matrix[y, x]
                time_val = all_times[x]
                core_val = all_cores[y]

                # Get items running on this core at this time
                items = core_item_map.get((time_val, core_val), [])

                # Sort by CPU usage
                items_sorted = sorted(items, key=lambda t: t['cpu'], reverse=True)

                # Build text
                text = f"Time: {time_val}\nCore: {core_val}\nTotal CPU: {cpu_val:.1f}%\n"

                if items_sorted:
                    text += f"\nTop {item_type}s ({len(items_sorted)} total):\n"
                    # Show top 3 items for hover
                    for item in items_sorted[:3]:
                        text += f"  {item_label} {item['id']}: {item['cpu']:.1f}% CPU\n"
                    if len(items_sorted) > 3:
                        text += f"  ... and {len(items_sorted) - 3} more\n"
                    text += "\nClick for detailed stats"
                else:
                    text += f"\nNo active {item_type.lower()}s"

                annot.xy = (x, y)
                annot.set_text(text)
                annot.set_visible(True)
                fig.canvas.draw_idle()
            else:
                annot.set_visible(False)
                fig.canvas.draw_idle()
        else:
            if annot.get_visible():
                annot.set_visible(False)
                fig.canvas.draw_idle()

    # Add click event for detailed popup
    detail_window = None

    def on_click(event):
        nonlocal detail_window
        if event.inaxes == ax and event.button == 1:  # Left click
            x, y = int(event.xdata + 0.5), int(event.ydata + 0.5)
            if 0 <= x < len(all_times) and 0 <= y < len(all_cores):
                cpu_val = matrix[y, x]
                time_val = all_times[x]
                core_val = all_cores[y]

                # Get items running on this core at this time
                items = core_item_map.get((time_val, core_val), [])
                items_sorted = sorted(items, key=lambda t: t['cpu'], reverse=True)

                # Build detailed popup text
                detail_text = "═══════════════════════════════════════════════════\n"
                detail_text += f"  CORE {core_val} PERFORMANCE @ {time_val}\n"
                detail_text += "═══════════════════════════════════════════════════\n\n"
                detail_text += f"CPU Utilization: {cpu_val:.2f}%\n\n"

                if items_sorted:
                    # Calculate aggregate memory
                    total_rss = sum(item['rss'] for item in items_sorted) / 1024  # MB
                    total_vsz = sum(item['vsz'] for item in items_sorted) / 1024  # MB
                    total_mem_pct = sum(item['mem_pct'] for item in items_sorted)
                    total_minflt = sum(item['minflt'] for item in items_sorted)
                    total_majflt = sum(item['majflt'] for item in items_sorted)

                    detail_text += "Memory Statistics:\n"
                    detail_text += f"  RSS (Resident):  {total_rss:8.1f} MB\n"
                    detail_text += f"  VSZ (Virtual):   {total_vsz:8.1f} MB\n"
                    detail_text += f"  Memory %:        {total_mem_pct:8.2f}%\n"
                    detail_text += f"  Minor Faults/s:  {total_minflt:8.2f}\n"
                    detail_text += f"  Major Faults/s:  {total_majflt:8.2f}\n\n"

                    detail_text += f"Active {item_type}s ({len(items_sorted)}): \n"
                    detail_text += f"{'─' * 49}\n"
                    detail_text += f"{item_label:<8} {'CPU%':>6} {'MEM%':>6} {'RSS(MB)':>10} {'Command'}\n"
                    detail_text += f"{'─' * 49}\n"

                    # Show all items
                    for item in items_sorted:
                        rss_mb = item['rss'] / 1024
                        cmd = item['command'][:25] + "..." if len(item['command']) > 25 else item['command']
                        detail_text += f"{item['id']:<8} {item['cpu']:>6.2f} {item['mem_pct']:>6.2f} {rss_mb:>10.1f} {cmd}\n"
                else:
                    detail_text += f"No active {item_type.lower()}s on this core at this time.\n"

                detail_text += f"\n{'─' * 49}\n"
                detail_text += "Click elsewhere to close\n"

                # Create or update detail window
                if detail_window is None or not plt.fignum_exists(detail_window.number):
                    detail_window = plt.figure(figsize=(8, 10))
                    detail_window.canvas.manager.set_window_title('Core Performance Details')
                else:
                    detail_window.clear()

                ax_detail = detail_window.add_subplot(111)
                ax_detail.axis('off')
                ax_detail.text(0.05, 0.95, detail_text,
                              transform=ax_detail.transAxes,
                              verticalalignment='top',
                              fontfamily='monospace',
                              fontsize=9,
                              bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
                detail_window.canvas.draw()
                detail_window.show()

    fig.canvas.mpl_connect('motion_notify_event', on_hover)
    fig.canvas.mpl_connect('button_press_event', on_click)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Core heatmap saved to {output_file}")


def aggregate_core_by_node(data, top_cores=8, top_nodes_per_core=6):
    """
    Group per-core CPU utilization by ROS2 node name
    instead of raw PID, to distinguish "core-bound due to poor affinity/
    scheduling" (one node dominating a core) from "generally CPU-heavy" (many
    nodes sharing it). Complements plot_core_heatmap()'s raw per-core total.

    Returns a list of (core, times, node_series) tuples for the top_cores
    busiest cores (by total CPU across the session), sorted by core number.
    node_series is {label: [cpu_pct_per_tick, ...]} aligned to `times`.
    PIDs absent from ros2_node_map are bucketed under '(non-ROS2)'; within
    each core, only the top_nodes_per_core busiest labels are kept
    individually and the remainder are summed into '(other)'.

    Returns [] if ros2_node_map is empty (older session, or non-ROS2 host).
    """
    node_map = data.get('ros2_node_map') or {}
    if not node_map:
        return []

    # Use threads if available, otherwise PIDs -- same source as plot_core_heatmap.
    source_data = data['threads'] if data['threads'] else data['pids']

    per_core_time_node = defaultdict(lambda: defaultdict(float))
    core_totals = defaultdict(float)
    for pid, records in source_data.items():
        for record in records:
            # Thread records are keyed by TID but carry their parent PID in
            # 'tgid'; ros2_node_map is keyed by PID, so look that up instead.
            node_pid = record.get('tgid', pid)
            node_label = node_map.get(node_pid, '(non-ROS2)')
            per_core_time_node[(record['core'], record['time'])][node_label] += record['cpu']
            core_totals[record['core']] += record['cpu']

    if not core_totals:
        return []

    all_times = sorted(set(record['time'] for records in source_data.values() for record in records))
    busiest_cores = sorted(core_totals, key=core_totals.get, reverse=True)[:top_cores]

    result = []
    for core in sorted(busiest_cores):
        node_totals = defaultdict(float)
        for time_str in all_times:
            for node_label, cpu in per_core_time_node.get((core, time_str), {}).items():
                node_totals[node_label] += cpu

        top_nodes = sorted(node_totals, key=node_totals.get, reverse=True)[:top_nodes_per_core]
        top_nodes_set = set(top_nodes)

        node_series = {node: [] for node in top_nodes}
        other_series = []
        for time_str in all_times:
            cell = per_core_time_node.get((core, time_str), {})
            for node in top_nodes:
                node_series[node].append(cell.get(node, 0.0))
            other_series.append(sum(cpu for label, cpu in cell.items() if label not in top_nodes_set))

        if any(v > 0 for v in other_series):
            node_series['(other)'] = other_series

        result.append((core, all_times, node_series))

    return result


def plot_core_node_stacking(data, top_n=10, output_file=None):
    """
    Stacked-area CPU utilization by node, one subplot per busiest core --
    a stack dominated by a single node signals affinity/scheduling
    contention on that core; an even mix signals generally CPU-heavy load.
    """
    core_series = aggregate_core_by_node(data, top_cores=top_n)
    if not core_series:
        logger.warning("No per-node core data to plot (requires ros2_node_map -- "
                        "re-capture with a monitor_resources.py version that writes it)")
        return

    fig, axes = plt.subplots(len(core_series), 1, figsize=(14, 3.2 * len(core_series)), sharex=True)
    if len(core_series) == 1:
        axes = [axes]

    all_nodes = sorted({node for _core, _times, series in core_series for node in series})
    colors = dict(zip(all_nodes, plt.cm.tab20(np.linspace(0, 1, max(len(all_nodes), 1)))))

    for ax, (core, times, node_series) in zip(axes, core_series):
        x = list(range(len(times)))
        y_stack = np.zeros(len(times))
        for node, values in node_series.items():
            vals = np.array(values)
            ax.fill_between(x, y_stack, y_stack + vals, alpha=0.7, color=colors[node], label=node)
            y_stack += vals
        ax.set_ylabel(f'Core {core}\nCPU %', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=7, ncol=2)

    axes[-1].set_xlabel('Time Index', fontsize=11)
    fig.suptitle(
        f'Per-Core CPU by Node (top {len(core_series)} busiest cores)\n'
        'Stack dominated by one node = affinity/scheduling hot spot; even mix = generally CPU-heavy',
        fontsize=13, fontweight='bold')
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=200, bbox_inches='tight')
        logger.info(f"Per-core node stacking plot saved to {output_file}")


def plot_pid_to_core_mapping(data, output_file=None):
    """
    Visualize which PIDs/threads run on which cores over time.
    Works with both thread mode and PID-only mode.
    """
    # Use threads if available, otherwise use PIDs
    source_data = data['threads'] if data['threads'] else data['pids']
    item_type = 'TID' if data['threads'] else 'PID'

    # Get top items by average CPU usage
    item_avg = {}
    for item_id, records in source_data.items():
        if records:
            avg_cpu = sum(r['cpu'] for r in records) / len(records)
            if avg_cpu > 1.0:  # Only show items with >1% avg CPU
                item_avg[item_id] = (avg_cpu, records[0]['command'])

    top_items = sorted(item_avg.items(), key=lambda x: x[1][0], reverse=True)[:15]

    if not top_items:
        logger.info(f"No significant {'thread' if data['threads'] else 'process'} data to plot")
        return

    fig, ax = plt.subplots(figsize=(16, 10))

    colors = plt.cm.tab20(np.linspace(0, 1, len(top_items)))

    y_pos = 0
    item_positions = {}

    for idx, (item_id, (avg_cpu, command)) in enumerate(top_items):
        records = source_data[item_id]
        item_positions[item_id] = y_pos

        for record in records:
            core = record['core']
            time_idx = data['timestamps'].index(record['time']) if record['time'] in data['timestamps'] else 0

            # Draw a point
            ax.scatter(time_idx, y_pos, c=[colors[idx]], s=50, alpha=0.6, marker='s')

            # Add core number as text for high CPU usage
            if record['cpu'] > 5.0:
                ax.text(time_idx, y_pos, str(core), fontsize=6, ha='center', va='center')

        y_pos += 1

    ax.set_yticks(range(len(top_items)))
    ax.set_yticklabels([f"{item_type} {item_id}\n{item_avg[item_id][1]}"
                        for item_id, _ in top_items], fontsize=7)
    ax.set_xlabel('Time Index', fontsize=12)
    ax.set_ylabel(f'{item_type}', fontsize=12)
    title = f'{"Thread" if data["threads"] else "Process"}-to-Core Mapping Over Time\n(Numbers indicate CPU core, hover for details)'
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')

    # Add hover annotation for interactivity
    annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                        bbox=dict(boxstyle="round", fc="yellow", alpha=0.9),
                        arrowprops=dict(arrowstyle="->"))
    annot.set_visible(False)

    # Store data for hover lookup
    hover_data = {}
    for idx, (item_id, (avg_cpu, command)) in enumerate(top_items):
        records = source_data[item_id]
        y_position = item_positions[item_id]
        for record in records:
            time_idx = data['timestamps'].index(record['time']) if record['time'] in data['timestamps'] else 0
            hover_data[(time_idx, y_position)] = {
                'id': item_id,
                'time': record['time'],
                'core': record['core'],
                'cpu': record['cpu'],
                'command': command
            }

    def on_hover(event):
        if event.inaxes == ax:
            # Find nearest point
            x, y = event.xdata, event.ydata
            closest = None
            min_dist = float('inf')

            for (time_idx, y_pos), info in hover_data.items():
                dist = ((time_idx - x)**2 + (y_pos - y)**2)**0.5
                if dist < min_dist and dist < 0.5:  # Within half a unit
                    min_dist = dist
                    closest = ((time_idx, y_pos), info)

            if closest:
                (time_idx, y_pos), info = closest
                annot.xy = (time_idx, y_pos)
                text = f"{item_type}: {info['id']}\nTime: {info['time']}\nCore: {info['core']}\nCPU: {info['cpu']:.1f}%\n{info['command'][:40]}"
                annot.set_text(text)
                annot.set_visible(True)
                fig.canvas.draw_idle()
            else:
                if annot.get_visible():
                    annot.set_visible(False)
                    fig.canvas.draw_idle()
        else:
            if annot.get_visible():
                annot.set_visible(False)
                fig.canvas.draw_idle()

    fig.canvas.mpl_connect('motion_notify_event', on_hover)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"{'Thread' if data['threads'] else 'Process'}-to-core mapping plot saved to {output_file}")


def aggregate_by_node(data):
    """
    Group per-PID resource records by ROS2 node name, using
    data['ros2_node_map'] (PID -> node name, written by monitor_resources.py'
    get_ros2_pid_node_map()). PIDs absent from the map (e.g.
    non-ROS2 system processes) are skipped -- this view is ROS2-node-scoped
    by design, mirroring the "ALL ROS2 PIDS" tables in print_summary().

    Returns:
        dict: node_name -> list of per-PID record lists (one list per
        contributing PID), so callers can pick whichever aggregation (sum,
        mean, max) is appropriate to the metric. A node backed by more than
        one process (e.g. component containers) has more than one entry.
    """
    node_map = data.get('ros2_node_map') or {}
    by_node = defaultdict(list)
    for pid, records in data['pids'].items():
        node_name = node_map.get(pid)
        if node_name and records:
            by_node[node_name].append(records)
    return by_node


def print_node_summary(data, top=10):
    """
    Print a per-ROS2-node CPU/memory summary. Complements print_summary()'s
    per-PID/per-TID tables with a coarser, node-name-scoped view -- e.g.
    "controller_server" instead of a bare PID -- so customers can see which
    *node* is resource-hungry without cross-referencing PIDs by hand.

    Requires the session to have been captured with a monitor_resources.py
    version that writes ros2_node_map; sessions captured before that are
    reported as unavailable rather than silently showing an empty table.
    """
    by_node = aggregate_by_node(data)
    if not by_node:
        logger.info(f"\n{'='*80}")
        logger.info("PER-NODE ATTRIBUTION: not available for this session "
                     "(re-capture with a monitor_resources.py version that "
                     "writes ros2_node_map)")
        logger.info(f"{'='*80}")
        return

    node_stats = []
    for node_name, pid_record_lists in by_node.items():
        # Average CPU per contributing PID over time, then sum across PIDs --
        # consistent with how "Total system CPU %" is computed in
        # print_summary() (sum of each process's own time-average).
        avg_cpu_total = sum(sum(r['cpu'] for r in records) / len(records) for records in pid_record_lists)
        max_cpu_total = max((max(r['cpu'] for r in records) for records in pid_record_lists), default=0.0)
        avg_rss_total_mb = sum(
            sum(r.get('rss', 0) for r in records) / len(records) for records in pid_record_lists
        ) / 1024.0
        node_stats.append((node_name, avg_cpu_total, max_cpu_total, avg_rss_total_mb, len(pid_record_lists)))

    node_stats.sort(key=lambda x: x[1], reverse=True)

    logger.info(f"\n{'='*80}")
    logger.info(f"PER-NODE ATTRIBUTION ({len(node_stats)} nodes)")
    logger.info(f"{'='*80}")
    logger.info(f"{'Node':<40} {'Avg CPU %':<12} {'Max CPU %':<12} {'Avg RSS (MB)':<14} {'PIDs':<6}")
    logger.info("-"*80)
    for node_name, avg_cpu, max_cpu, avg_rss, pid_count in node_stats[:top]:
        logger.info(f"{node_name:<40} {avg_cpu:<12.2f} {max_cpu:<12.2f} {avg_rss:<14.1f} {pid_count:<6}")
    logger.info("\n")


def print_summary(data, core_data, by_tid=False, top=10):
    """
    Print summary statistics.

    ROS2 attribution uses data['ros2_pids'] (PIDs classified via a one-time
    `ps aux` scan at capture time, see monitor_resources.py) when available.
    Falls back to name-matching each entry's Command field via
    is_ros2_process() for sessions captured without that marker line --
    less accurate, since the Command field may be a bare executable name,
    not a full command line.

    Defaults to PID (process-level) granularity even when the log was
    captured with --threads -- each process's own summary is always recorded
    in data['pids'] regardless of whether per-thread data exists. Pass
    by_tid=True to instead show the individual per-thread (TID) breakdown.
    """
    num_cpus = data.get('num_cpus', 0)
    cpu_note = (
        f"Note: CPU% is on a 100%=1 full core scale. "
        f"System has {num_cpus} logical cores (theoretical max: {num_cpus * 100}%)."
        if num_cpus else
        "Note: CPU% is on a 100%=1 full core scale (values >100% = multi-core usage)."
    )

    logger.info("\n" + "="*80)
    logger.info("RESOURCE UTILIZATION SUMMARY")
    logger.info("="*80)
    logger.info(f"\n{cpu_note}")

    # Number of unique threads/PIDs
    logger.info(f"\nTotal unique threads monitored: {len(data['threads'])}")
    logger.info(f"Total unique PIDs monitored: {len(data['pids'])}")
    logger.info(f"Total time samples: {len(data['timestamps'])}")

    # Core statistics
    logger.info(f"\n{'='*80}")
    logger.info("CPU CORE STATISTICS")
    logger.info(f"{'='*80}")
    logger.info(f"{'Core':<8} {'Avg CPU %':<12} {'Max CPU %':<12} {'Avg Cores':<12} {'Samples':<10}")
    logger.info("-"*80)

    for core in sorted(core_data.keys()):
        records = core_data[core]
        cpus = [r[1] for r in records]
        avg_cpu = sum(cpus) / len(cpus) if cpus else 0
        max_cpu = max(cpus) if cpus else 0
        avg_cores = avg_cpu / 100.0
        logger.info(f"{core:<8} {avg_cpu:<12.2f} {max_cpu:<12.2f} {avg_cores:<12.2f} {len(records):<10}")

    # Top threads/processes by average CPU. Defaults to PID (process-level)
    # granularity; pass by_tid=True to break down by individual thread instead.
    use_threads = by_tid and bool(data['threads'])
    source_data = data['threads'] if use_threads else data['pids']
    label = "THREADS" if use_threads else "PROCESSES"
    id_label = "TID" if use_threads else "PID"

    thread_stats = []
    for tid, records in source_data.items():
        if records:
            cpus = [r['cpu'] for r in records]
            cores = sorted(set(r['core'] for r in records))
            avg_cpu = sum(cpus) / len(cpus)
            max_cpu = max(cpus)
            command = records[0]['command']
            core_affinity = '[' + ','.join(map(str, cores)) + ']'
            # Prefer the parent TGID (process) for attribution when this row
            # is a thread; PID-mode rows already key on the process itself.
            pid_for_attribution = records[0].get('tgid', tid)
            thread_stats.append((tid, avg_cpu, max_cpu, core_affinity, command, pid_for_attribution))

    # ROS2 vs. system-wide attribution (this log covers ALL processes, see #55).
    # Prefer PID cross-reference against data['ros2_pids'] (captured via a
    # `ps aux` full-command-line scan); fall back to name-matching the
    # (truncated) Command field for older sessions without that marker line.
    ros2_pid_set = data.get('ros2_pids') or set()

    def _is_ros2(entry):
        if ros2_pid_set:
            try:
                return int(entry[5]) in ros2_pid_set
            except (ValueError, TypeError):
                return False
        return is_ros2_process(entry[4])

    attribution_method = "PID cross-reference" if ros2_pid_set else "name-matched (less accurate)"
    total_cpu = sum(s[1] for s in thread_stats)
    ros2_cpu = sum(s[1] for s in thread_stats if _is_ros2(s))
    ros2_share = (ros2_cpu / total_cpu * 100) if total_cpu > 0 else 0.0
    logger.info(f"\n{'='*80}")
    logger.info("RESOURCE ATTRIBUTION: ROS2 vs. SYSTEM")
    logger.info(f"{'='*80}")
    logger.info(f"Total system CPU %  (sum of avg CPU across all {label.lower()}): {total_cpu:.2f}")
    logger.info(f"ROS2-attributed CPU %  ({attribution_method}):        {ros2_cpu:.2f}")
    logger.info(f"ROS2 share of total system CPU:                              {ros2_share:.1f}%")

    thread_stats.sort(key=lambda x: x[1], reverse=True)

    logger.info(f"\n{'='*80}")
    logger.info(f"TOP {top} {label} BY AVERAGE CPU UTILIZATION")
    logger.info(f"{'='*80}")
    logger.info(f"{id_label:<10} {'Avg CPU %':<12} {'Avg Cores':<12} {'Max CPU %':<12} {'Core Affinity':<17} {'Command'}")
    logger.info("-"*80)

    for tid, avg_cpu, max_cpu, core_affinity, command, _pid in thread_stats[:top]:
        avg_cores = avg_cpu / 100.0
        logger.info(f"{tid:<10} {avg_cpu:<12.2f} {avg_cores:<12.2f} {max_cpu:<12.2f} {core_affinity:<17} {command}")

    # All ROS2-attributed PIDs (process-level, regardless of by_tid) -- unlike
    # the TOP N table above, this always lists every ROS2 process so none are
    # hidden behind a top-N cutoff.
    ros2_pid_stats = []
    for pid, records in data['pids'].items():
        if not records:
            continue
        cpus = [r['cpu'] for r in records]
        cores = sorted(set(r['core'] for r in records))
        avg_cpu = sum(cpus) / len(cpus)
        max_cpu = max(cpus)
        command = records[0]['command']
        core_affinity = '[' + ','.join(map(str, cores)) + ']'
        if _is_ros2((pid, avg_cpu, max_cpu, core_affinity, command, pid)):
            ros2_pid_stats.append((pid, avg_cpu, max_cpu, core_affinity, command))
    ros2_pid_stats.sort(key=lambda x: x[1], reverse=True)

    logger.info(f"\n{'='*80}")
    logger.info(f"ALL ROS2 PIDS ({len(ros2_pid_stats)}) BY AVERAGE CPU UTILIZATION")
    logger.info(f"{'='*80}")
    logger.info(f"{'PID':<10} {'Avg CPU %':<12} {'Avg Cores':<12} {'Max CPU %':<12} {'Core Affinity':<17} {'Command'}")
    logger.info("-"*80)

    for pid, avg_cpu, max_cpu, core_affinity, command in ros2_pid_stats:
        avg_cores = avg_cpu / 100.0
        logger.info(f"{pid:<10} {avg_cpu:<12.2f} {avg_cores:<12.2f} {max_cpu:<12.2f} {core_affinity:<17} {command}")

    # Memory (RSS/%MEM) summary -- only meaningful when the capture included
    # memory stats (monitor_resources.py --memory). data['has_memory'] is
    # detected from the "Running: ..." line at parse time.
    if not data.get('has_memory'):
        logger.info(f"\n{'='*80}")
        logger.info("MEMORY UTILIZATION: not collected for this session "
                     "(re-run monitor_resources.py with --memory)")
        logger.info(f"{'='*80}")
    else:
        mem_stats = []
        for tid, records in source_data.items():
            if not records:
                continue
            rss_mb_vals = [r.get('rss', 0) / 1024.0 for r in records]
            mem_pct_vals = [r.get('mem_pct', 0) for r in records]
            avg_rss = sum(rss_mb_vals) / len(rss_mb_vals)
            max_rss = max(rss_mb_vals)
            avg_mem_pct = sum(mem_pct_vals) / len(mem_pct_vals)
            command = records[0]['command']
            mem_stats.append((tid, avg_rss, max_rss, avg_mem_pct, command))
        mem_stats.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"\n{'='*80}")
        logger.info("MEMORY UTILIZATION SUMMARY")
        logger.info(f"{'='*80}")
        total_rss_mb = sum(s[1] for s in mem_stats)
        logger.info(f"Total average RSS across all {label.lower()}: {total_rss_mb:.1f} MB")

        logger.info(f"\n{'='*80}")
        logger.info(f"TOP {top} {label} BY AVERAGE MEMORY (RSS)")
        logger.info(f"{'='*80}")
        logger.info(f"{id_label:<10} {'Avg RSS (MB)':<14} {'Max RSS (MB)':<14} {'Avg %MEM':<10} {'Command'}")
        logger.info("-"*80)
        for tid, avg_rss, max_rss, avg_mem_pct, command in mem_stats[:top]:
            logger.info(f"{tid:<10} {avg_rss:<14.1f} {max_rss:<14.1f} {avg_mem_pct:<10.2f} {command}")

        # All ROS2-attributed PIDs by memory (process-level), mirroring the
        # CPU "ALL ROS2 PIDS" table above -- never capped at top-N.
        ros2_mem_stats = []
        for pid, records in data['pids'].items():
            if not records:
                continue
            cpus = [r['cpu'] for r in records]
            cores = sorted(set(r['core'] for r in records))
            avg_cpu = sum(cpus) / len(cpus)
            max_cpu = max(cpus)
            command = records[0]['command']
            core_affinity = '[' + ','.join(map(str, cores)) + ']'
            if not _is_ros2((pid, avg_cpu, max_cpu, core_affinity, command, pid)):
                continue
            rss_mb_vals = [r.get('rss', 0) / 1024.0 for r in records]
            mem_pct_vals = [r.get('mem_pct', 0) for r in records]
            avg_rss = sum(rss_mb_vals) / len(rss_mb_vals)
            max_rss = max(rss_mb_vals)
            avg_mem_pct = sum(mem_pct_vals) / len(mem_pct_vals)
            ros2_mem_stats.append((pid, avg_rss, max_rss, avg_mem_pct, command))
        ros2_mem_stats.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"\n{'='*80}")
        logger.info(f"ALL ROS2 PIDS ({len(ros2_mem_stats)}) BY AVERAGE MEMORY (RSS)")
        logger.info(f"{'='*80}")
        logger.info(f"{'PID':<10} {'Avg RSS (MB)':<14} {'Max RSS (MB)':<14} {'Avg %MEM':<10} {'Command'}")
        logger.info("-"*80)
        for pid, avg_rss, max_rss, avg_mem_pct, command in ros2_mem_stats:
            logger.info(f"{pid:<10} {avg_rss:<14.1f} {max_rss:<14.1f} {avg_mem_pct:<10.2f} {command}")

    logger.info("\n")


def parse_gpu_log(gpu_log_file: str):
    """Parse JSON-lines GPU usage log.  Returns list of dicts."""
    records = []
    try:
        with open(gpu_log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        pass
    return records


def plot_gpu(records: list, output_file=None, show=False):
    """
    Plot GPU busy %, engine-class breakdown, frequency/RC6, temperature,
    power and per-PID usage over time.
    Delegates to visualize_gpu.plot_gpu_full() so all panels stay in sync.
    Falls back to an inline implementation if the module is unavailable.
    """
    if not records:
        logger.info("  No GPU records to plot.")
        return

    # Filter out event markers
    records = [r for r in records if 'busy_pct' in r]
    if not records:
        logger.info("  No GPU data records to plot.")
        return

    # ── Prefer the dedicated visualize_gpu module ────────────────────────────
    try:
        import importlib.util  # noqa: E402
        import os as _os  # noqa: E402
        _script_dir = _os.path.dirname(_os.path.abspath(__file__))
        _spec = importlib.util.spec_from_file_location(
            'visualize_gpu',
            _os.path.join(_script_dir, 'visualize_gpu.py'))
        _vg = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_vg)
        _vg.plot_gpu_full(records, output_file=output_file, show=show)
        return
    except Exception:
        pass  # fall through to inline implementation

    # ── Inline fallback (no visualize_gpu.py available) ─────────────────────
    _ENG_RE = {
        'Render/3D': re.compile(r'render|3d',                      re.I),
        'Blitter':   re.compile(r'blitter|blt',                    re.I),
        'Video':     re.compile(r'^video$',                        re.I),
        'VE':        re.compile(r'videoenhance|video_enhance|ve\b', re.I),
    }
    _ENG_COLORS = {
        'Render/3D': '#e07b39', 'Blitter': '#4c9de0',
        'Video': '#6abf6a',     'VE': '#b565c9',
    }

    def _canonical(rec):
        out = {k: 0.0 for k in _ENG_RE}
        for key, val in (rec.get('engines') or {}).items():
            busy = float(val.get('busy', 0)) if isinstance(val, dict) else float(val or 0)
            for cls, pat in _ENG_RE.items():
                if pat.search(key):
                    out[cls] += busy
                    break
        return out

    timestamps  = [datetime.fromisoformat(r['ts']) for r in records]
    busy        = [r.get('busy_pct', 0.0) for r in records]
    has_temp    = any(r.get('temp_c') is not None for r in records)
    has_power   = any(r.get('power_gpu_w', 0) for r in records)
    has_engines = any(r.get('engines') for r in records)
    has_clients = any(r.get('clients') for r in records)

    nrows = 2 + has_temp + has_power + has_engines + has_clients
    fig, axes = plt.subplots(nrows, 1, figsize=(14, 4 * nrows), sharex=True)
    if nrows == 1:
        axes = [axes]
    ax_iter = iter(axes)

    fig.suptitle('Intel GPU Utilization', fontsize=14, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.94, hspace=0.38)

    # Panel 1 – busy %
    ax1 = next(ax_iter)
    ax1.fill_between(timestamps, busy, alpha=0.25, color='steelblue')
    ax1.plot(timestamps, busy, color='steelblue', linewidth=1.2, label='GPU busy %')
    ax1.set_ylabel('GPU Busy (%)', fontsize=10)
    ax1.set_ylim(0, 105)
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    # Panel 2 – frequency
    ax2 = next(ax_iter)
    act_freq = [r.get('act_freq_mhz', 0) for r in records]
    cur_freq = [r.get('cur_freq_mhz', 0) for r in records]
    ax2.plot(timestamps, act_freq, color='darkorange', linewidth=1.2, label='Actual freq')
    if any(cur_freq):
        ax2.plot(timestamps, cur_freq, color='gold', linewidth=1.0, linestyle='--',
                 label='Current freq')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.set_ylabel('Frequency (MHz)', fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    # Panel 3 – temperature
    if has_temp:
        ax3 = next(ax_iter)
        pairs = [(t, r['temp_c']) for t, r in zip(timestamps, records)
                 if r.get('temp_c') is not None]
        ts_t, vals_t = zip(*pairs)
        ax3.fill_between(ts_t, vals_t, alpha=0.2, color='tomato')
        ax3.plot(ts_t, vals_t, color='tomato', linewidth=1.2, label='GPU Temp (°C)')
        if max(vals_t) > 70:
            ax3.axhline(90, color='red', linewidth=0.8, linestyle='--',
                        alpha=0.5, label='90 °C threshold')
        ax3.set_ylabel('Temp (°C)', fontsize=10)
        ax3.legend(loc='upper right', fontsize=8)
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    # Panel 4 – power
    if has_power:
        ax4 = next(ax_iter)
        gpu_w = [r.get('power_gpu_w', 0.0) for r in records]
        pkg_w = [r.get('power_pkg_w', 0.0) for r in records]
        ax4.fill_between(timestamps, gpu_w, alpha=0.2, color='crimson')
        ax4.plot(timestamps, gpu_w, color='crimson', linewidth=1.2, label='GPU (W)')
        if any(p > 0 for p in pkg_w):
            ax4.plot(timestamps, pkg_w, color='salmon', linewidth=0.9,
                     linestyle='--', label='Package (W)')
        ax4.set_ylabel('Power (W)', fontsize=10)
        ax4.legend(loc='upper right', fontsize=8)
        ax4.grid(True, alpha=0.3)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    # Panel 5 – per-engine-class (canonical classes)
    if has_engines:
        ax5 = next(ax_iter)
        y_stack = np.zeros(len(records))
        for cls, col in _ENG_COLORS.items():
            vals = np.array([_canonical(r)[cls] for r in records])
            if any(v > 0.05 for v in vals):
                ax5.fill_between(timestamps, y_stack, y_stack + vals,
                                 alpha=0.55, color=col, label=cls)
                y_stack += vals
        ax5.set_ylabel('Engine Busy (%)', fontsize=10)
        ax5.set_ylim(0, 105)
        ax5.legend(loc='upper right', fontsize=8, ncol=2)
        ax5.grid(True, alpha=0.3)
        ax5.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    # Panel 6 – per-PID GPU % (top 8 by peak)
    if has_clients:
        from collections import defaultdict as _dd
        ax6 = next(ax_iter)
        pid_pts = _dd(list)
        pid_names = {}
        for rec, ts in zip(records, timestamps):
            for c in (rec.get('clients') or []):
                pid_pts[c['pid']].append((ts, c['total']))
                pid_names[c['pid']] = c.get('name', '?')
        peak = {p: max(v for _, v in pts) for p, pts in pid_pts.items()}
        top = sorted(peak, key=peak.__getitem__, reverse=True)[:8]
        _colors = plt.cm.tab10.colors
        for i, pid in enumerate(top):
            pts = sorted(pid_pts[pid])
            ax6.plot([p[0] for p in pts], [p[1] for p in pts],
                     linewidth=1.0, color=_colors[i % 10],
                     label=f'PID {pid} ({pid_names[pid]})', alpha=0.85)
        ax6.set_ylabel('GPU per-PID (%)', fontsize=10)
        ax6.legend(loc='upper right', fontsize=7, ncol=2)
        ax6.grid(True, alpha=0.3)
        ax6.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=30, ha='right')
    axes[-1].set_xlabel('Time', fontsize=10)
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"  Saved: {output_file}")
        if not show:
            plt.close()
    if show:
        plt.show()
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='Visualize ROS2 resource monitoring data from resource_usage.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all plots
  %(prog)s ros2_log.log

  # Generate specific plots
  %(prog)s ros2_log.log --cores --heatmap

  # Save plots to files
  %(prog)s ros2_log.log --output-dir ./plots/

  # Show top 20 threads
  %(prog)s ros2_log.log --top 20
        """
    )

    parser.add_argument('log_file', type=str,
                        help='Path to resource_usage.json')
    parser.add_argument('--cores', action='store_true',
                        help='Plot CPU utilization per core')
    parser.add_argument('--pids', action='store_true',
                        help='Plot CPU utilization per PID/thread')
    parser.add_argument('--heatmap', action='store_true',
                        help='Generate core utilization heatmap')
    parser.add_argument('--core-nodes', action='store_true',
                        help='Plot per-core CPU stacked by ROS2 node (top busiest cores), '
                             'if ros2_node_map is present')
    parser.add_argument('--mapping', action='store_true',
                        help='Show thread-to-core mapping')
    parser.add_argument('--disk-io', action='store_true',
                        help='Plot per-process disk I/O (read/write), if collected via --io/-d')
    parser.add_argument('--ctx-switches', action='store_true',
                        help='Plot per-process involuntary/voluntary context switches, '
                             'if collected via --ctx-switches/-x')
    parser.add_argument('--top', type=int, default=10,
                        help='Number of top threads to display (default: 10)')
    parser.add_argument('--by-tid', action='store_true',
                        help='Break down the top-N table by individual thread (TID) '
                             'instead of the default per-process (PID) view')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory to save plots (if not specified, displays interactively)')
    parser.add_argument('--show', action='store_true',
                        help='Display plots interactively (in addition to saving if --output-dir is set)')
    parser.add_argument('--summary', action='store_true',
                        help='Print summary statistics only')
    parser.add_argument('--gpu-log', type=str, default=None,
                        help='Path to gpu_usage.log (JSON-lines written by monitor_resources --gpu)')

    args = parser.parse_args()

    # If no specific plots selected, show all
    if not any([args.cores, args.pids, args.heatmap, args.mapping, args.summary]):
        args.cores = True
        args.pids = True
        args.heatmap = True
        args.mapping = True
        args.disk_io = True
        args.ctx_switches = True
        args.core_nodes = True

    logger.info(f"Parsing log file: {args.log_file}")
    data, _ = parse_resource_log(args.log_file)

    if not data['threads'] and not data['pids']:
        logger.warning("No data found in log file. Make sure it is a valid resource_usage.json document.")
        return

    # Report what we found
    if data['threads']:
        logger.info(f"Found {len(data['threads'])} threads across {len(data['timestamps'])} time samples")
    elif data['pids']:
        logger.info(f"Found {len(data['pids'])} processes across {len(data['timestamps'])} time samples")

    # Aggregate core utilization
    core_data = aggregate_core_utilization(data)

    # Print summary
    print_summary(data, core_data, by_tid=args.by_tid, top=args.top)
    print_node_summary(data, top=args.top)

    if data.get('num_cpus'):
        logger.info(f"  System CPU count detected from log: {data['num_cpus']} logical cores")

    if args.summary:
        return

    # Determine output file paths
    import os
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        core_out = os.path.join(args.output_dir, 'core_utilization.png')
        pid_out = os.path.join(args.output_dir, 'pid_utilization.png')
        heatmap_out = os.path.join(args.output_dir, 'core_heatmap.png')
        mapping_out = os.path.join(args.output_dir, 'thread_core_mapping.png')
    else:
        core_out = pid_out = heatmap_out = mapping_out = None

    # Generate plots
    if args.cores:
        logger.info("\nGenerating core utilization plot...")
        plot_core_utilization(core_data, core_out)

    if args.pids:
        logger.info(f"\nGenerating top {args.top} thread utilization plot...")
        plot_pid_utilization(data, top_n=args.top, output_file=pid_out)

    if args.heatmap:
        logger.info("\nGenerating core utilization heatmap...")
        plot_core_heatmap(core_data, data, heatmap_out)

    if args.mapping:
        logger.info("\nGenerating thread-to-core mapping...")
        plot_pid_to_core_mapping(data, mapping_out)

    if args.disk_io:
        logger.info(f"\nGenerating top {args.top} disk I/O plot...")
        disk_io_out = os.path.join(args.output_dir, 'disk_io.png') if args.output_dir else None
        plot_disk_io(data, top_n=args.top, output_file=disk_io_out)

    if args.ctx_switches:
        logger.info(f"\nGenerating top {args.top} context-switch plot...")
        ctx_out = os.path.join(args.output_dir, 'ctx_switches.png') if args.output_dir else None
        plot_ctx_switches(data, top_n=args.top, output_file=ctx_out)

    if args.core_nodes:
        logger.info("\nGenerating per-core CPU-by-node stacking plot...")
        core_nodes_out = os.path.join(args.output_dir, 'core_node_stacking.png') if args.output_dir else None
        plot_core_node_stacking(data, top_n=args.top, output_file=core_nodes_out)

    if args.gpu_log:
        import os
        gpu_out = os.path.join(args.output_dir, 'gpu_utilization.png') if args.output_dir else None
        logger.info("\nGenerating GPU utilization plot...")
        gpu_records = parse_gpu_log(args.gpu_log)
        if gpu_records:
            logger.info(f"  Found {len(gpu_records)} GPU samples")
            plot_gpu(gpu_records, gpu_out, show=(args.show or not args.output_dir))
        else:
            logger.warning("  No GPU data found.")

    # Display plots interactively if requested or if no output directory
    if args.show or not args.output_dir:
        logger.info("\nDisplaying plots interactively. Close windows to exit.")
        plt.show()

    logger.info("\nVisualization complete!")


if __name__ == '__main__':
    main()
