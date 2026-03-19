#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Visualize ROS2 resource monitoring data from pidstat logs.
Creates interactive plots showing CPU utilization per core and per PID/thread over time.
"""

import re
import json
import argparse
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np


def parse_pidstat_log(log_file):
    """
    Parse pidstat log file and extract CPU usage data.
    
    Returns:
        dict: Parsed data with timestamps, PIDs, CPU cores, and utilization
    """
    data = {
        'timestamps': [],
        'pids': defaultdict(list),  # pid -> list of (timestamp, cpu%, core)
        'cores': defaultdict(list),  # core -> list of (timestamp, total_cpu%)
        'threads': defaultdict(list),  # tid -> list of (timestamp, cpu%, core, command)
        'tgid_commands': {},  # tgid -> command mapping
        'num_cpus': 0,  # total logical CPUs on the monitored system
    }
    
    current_timestamp = None
    monitoring_sessions = []
    current_session = None
    current_tgid_command = {}  # Track TGID commands within each timestamp
    
    # ANSI color code pattern for stripping
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    
    with open(log_file, 'r') as f:
        for line in f:
            # Strip ANSI color codes from line
            line = ansi_escape.sub('', line)
            
            # Detect total CPU count from pidstat header, e.g. "(20 CPU)"
            if not data['num_cpus']:
                cpu_count_match = re.search(r'\((\d+) CPU\)', line)
                if cpu_count_match:
                    data['num_cpus'] = int(cpu_count_match.group(1))

            # Check for session start
            if 'Monitoring started at' in line:
                match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    current_session = {
                        'start': match.group(1),
                        'data_points': []
                    }
                    monitoring_sessions.append(current_session)
            
            # Check for timestamp line (pidstat output)
            time_match = re.match(r'^(\d{2}:\d{2}:\d{2} [AP]M)\s+\d+', line)
            if time_match:
                current_timestamp = time_match.group(1)
                if current_timestamp not in data['timestamps']:
                    data['timestamps'].append(current_timestamp)
                # Reset TGID command tracking for new timestamp
                current_tgid_command = {}
            
            # Parse data lines
            if current_timestamp and re.match(r'^\d{2}:\d{2}:\d{2} [AP]M', line):
                parts = line.split()
                if len(parts) >= 12:
                    time_str = parts[0] + ' ' + parts[1]
                    uid = parts[2]
                    
                    # Detect format based on column count and structure
                    # Thread mode: Time UID TGID TID %usr %system %guest %wait %CPU CPU minflt/s majflt/s VSZ RSS %MEM Command
                    #              parts[3] is TGID, parts[4] is TID (could be '-' or thread ID)
                    # PID mode:    Time UID PID %usr %system %guest %wait %CPU CPU minflt/s majflt/s VSZ RSS %MEM Command
                    #              parts[3] is PID, parts[4] is %usr (a float percentage)
                    
                    # Simple detection: In thread mode, parts[4] == '-' or is a number (thread ID)
                    # In PID mode, parts[4] is a float percentage like "0.00" or "1.25"
                    # We check if it looks like a TID (dash or integer) vs a percentage
                    has_threads = (parts[4] == '-' or 
                                   (parts[4].isdigit() and len(parts) >= 16))
                    
                    if has_threads:
                        # Thread mode format
                        # Time UID TGID TID %usr %system %guest %wait %CPU CPU minflt/s majflt/s VSZ RSS %MEM Command
                        tgid = parts[3]
                        tid = parts[4]
                        cpu_pct = float(parts[9])  # %CPU column
                        try:
                            cpu_core = int(parts[10])   # CPU core column
                        except (ValueError, IndexError):
                            cpu_core = 0  # Default if not available
                        
                        # Parse memory stats
                        try:
                            minflt = float(parts[11])  # minor page faults/s
                            majflt = float(parts[12])  # major page faults/s
                            vsz = int(parts[13])       # virtual memory KB
                            rss = int(parts[14])       # resident set size KB
                            mem_pct = float(parts[15]) # memory %
                        except (ValueError, IndexError):
                            minflt = majflt = vsz = rss = mem_pct = 0
                        
                        command = ' '.join(parts[16:]) if len(parts) > 16 else ''
                        
                        # If this is a TGID line (TID is '-'), store the command
                        if tid == '-':
                            current_tgid_command[tgid] = command
                            data['tgid_commands'][tgid] = command
                            
                            # Store PID data
                            data['pids'][tgid].append({
                                'time': time_str,
                                'cpu': cpu_pct,
                                'core': cpu_core,
                                'command': command,
                                'minflt': minflt,
                                'majflt': majflt,
                                'vsz': vsz,
                                'rss': rss,
                                'mem_pct': mem_pct
                            })
                        else:
                            # This is a thread line, use parent TGID command if available
                            full_command = current_tgid_command.get(tgid, command)
                            if tgid in data['tgid_commands']:
                                full_command = data['tgid_commands'][tgid]
                            
                            # Enhance thread command with TGID info
                            if full_command != command and not command.startswith('|__'):
                                enhanced_command = f"{full_command} {command}"
                            elif full_command != command:
                                enhanced_command = f"{full_command} (thread)"
                            else:
                                enhanced_command = command
                            
                            # Store thread data
                            data['threads'][tid].append({
                                'time': time_str,
                                'cpu': cpu_pct,
                                'core': cpu_core,
                                'command': enhanced_command,
                                'tgid': tgid,
                                'minflt': minflt,
                                'majflt': majflt,
                                'vsz': vsz,
                                'rss': rss,
                                'mem_pct': mem_pct
                            })
                    else:
                        # PID-only mode format
                        pid = parts[3]
                        cpu_pct = float(parts[8])  # %CPU column (position 8 in PID mode)
                        try:
                            cpu_core = int(parts[9])   # CPU core column (position 9 in PID mode)
                        except (ValueError, IndexError):
                            cpu_core = 0  # Default if not available
                        
                        # Parse memory stats
                        try:
                            minflt = float(parts[10])
                            majflt = float(parts[11])
                            vsz = int(parts[12])
                            rss = int(parts[13])
                            mem_pct = float(parts[14])
                        except (ValueError, IndexError):
                            minflt = majflt = vsz = rss = mem_pct = 0
                        
                        command = ' '.join(parts[15:]) if len(parts) > 15 else parts[-1]
                        
                        # Store PID data
                        data['pids'][pid].append({
                            'time': time_str,
                            'cpu': cpu_pct,
                            'core': cpu_core,
                            'command': command,
                            'minflt': minflt,
                            'majflt': majflt,
                            'vsz': vsz,
                            'rss': rss,
                            'mem_pct': mem_pct
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
    for tid, records in data['threads'].items():
        for record in records:
            time_str = record['time']
            core = record['core']
            cpu_pct = record['cpu']
            core_usage[time_str][core] += cpu_pct
    
    # Aggregate PID data by core and timestamp (if threads not available)
    if not data['threads'] and data['pids']:
        for pid, records in data['pids'].items():
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
        print(f"Core utilization plot saved to {output_file}")



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
        print("No data to plot")
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
        print(f"{'PID' if not data['threads'] else 'Thread'} utilization plot saved to {output_file}")



def plot_core_heatmap(core_data, data, output_file=None):
    """
    Create a heatmap showing CPU utilization across cores over time.
    Works with both thread mode and PID-only mode.
    """
    # Get all unique cores and times
    all_cores = sorted(set(core_data.keys()))
    all_times = sorted(set(t for records in core_data.values() for t, _ in records))
    
    if not all_times or not all_cores:
        print("No data to plot heatmap")
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
        f'ROS2 CPU Core Utilization Heatmap\n'
        f'(Hover to preview | Click for detailed stats | Color scale: 100% = 1 full core)'
    )
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('CPU Utilization (%)', rotation=270, labelpad=20)
    
    # Add hover annotation for interactivity
    annot = ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
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
                        short_cmd = item['command'][:30] + "..." if len(item['command']) > 30 else item['command']
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
                detail_text = f"═══════════════════════════════════════════════════\n"
                detail_text += f"  CORE {core_val} PERFORMANCE @ {time_val}\n"
                detail_text += f"═══════════════════════════════════════════════════\n\n"
                detail_text += f"CPU Utilization: {cpu_val:.2f}%\n\n"
                
                if items_sorted:
                    # Calculate aggregate memory
                    total_rss = sum(item['rss'] for item in items_sorted) / 1024  # MB
                    total_vsz = sum(item['vsz'] for item in items_sorted) / 1024  # MB
                    total_mem_pct = sum(item['mem_pct'] for item in items_sorted)
                    total_minflt = sum(item['minflt'] for item in items_sorted)
                    total_majflt = sum(item['majflt'] for item in items_sorted)
                    
                    detail_text += f"Memory Statistics:\n"
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
        print(f"Core heatmap saved to {output_file}")



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
        print(f"No significant {'thread' if data['threads'] else 'process'} data to plot")
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
    annot = ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
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
        print(f"{'Thread' if data['threads'] else 'Process'}-to-core mapping plot saved to {output_file}")



def print_summary(data, core_data):
    """
    Print summary statistics.
    """
    num_cpus = data.get('num_cpus', 0)
    cpu_note = (
        f"Note: CPU% uses pidstat scale where 100% = 1 full core. "
        f"System has {num_cpus} logical cores (theoretical max: {num_cpus * 100}%)."
        if num_cpus else
        "Note: CPU% uses pidstat scale where 100% = 1 full core (values >100% = multi-core usage)."
    )

    print("\n" + "="*80)
    print("RESOURCE UTILIZATION SUMMARY")
    print("="*80)
    print(f"\n{cpu_note}")

    # Number of unique threads/PIDs
    print(f"\nTotal unique threads monitored: {len(data['threads'])}")
    print(f"Total unique PIDs monitored: {len(data['pids'])}")
    print(f"Total time samples: {len(data['timestamps'])}")

    # Core statistics
    print(f"\n{'='*80}")
    print("CPU CORE STATISTICS")
    print(f"{'='*80}")
    print(f"{'Core':<8} {'Avg CPU %':<12} {'Max CPU %':<12} {'Avg Cores':<12} {'Samples':<10}")
    print("-"*80)

    for core in sorted(core_data.keys()):
        records = core_data[core]
        cpus = [r[1] for r in records]
        avg_cpu = sum(cpus) / len(cpus) if cpus else 0
        max_cpu = max(cpus) if cpus else 0
        avg_cores = avg_cpu / 100.0
        print(f"{core:<8} {avg_cpu:<12.2f} {max_cpu:<12.2f} {avg_cores:<12.2f} {len(records):<10}")

    # Top threads/processes by average CPU
    source_data = data['threads'] if data['threads'] else data['pids']
    label = "THREADS" if data['threads'] else "PROCESSES"
    id_label = "TID" if data['threads'] else "PID"

    print(f"\n{'='*80}")
    print(f"TOP 10 {label} BY AVERAGE CPU UTILIZATION")
    print(f"{'='*80}")
    print(f"{id_label:<10} {'Avg CPU %':<12} {'Avg Cores':<12} {'Max CPU %':<12} {'Core Affinity':<17} {'Command'}")
    print("-"*80)

    thread_stats = []
    for tid, records in source_data.items():
        if records:
            cpus = [r['cpu'] for r in records]
            cores = sorted(set(r['core'] for r in records))
            avg_cpu = sum(cpus) / len(cpus)
            max_cpu = max(cpus)
            command = records[0]['command']
            core_affinity = '[' + ','.join(map(str, cores)) + ']'
            thread_stats.append((tid, avg_cpu, max_cpu, core_affinity, command))

    thread_stats.sort(key=lambda x: x[1], reverse=True)

    for tid, avg_cpu, max_cpu, core_affinity, command in thread_stats[:10]:
        avg_cores = avg_cpu / 100.0
        print(f"{tid:<10} {avg_cpu:<12.2f} {avg_cores:<12.2f} {max_cpu:<12.2f} {core_affinity:<17} {command}")

    print("\n")


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
        print("  No GPU records to plot.")
        return

    # Filter out event markers
    records = [r for r in records if 'busy_pct' in r]
    if not records:
        print("  No GPU data records to plot.")
        return

    # ── Prefer the dedicated visualize_gpu module ────────────────────────────
    try:
        import importlib.util, os as _os
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

    source      = records[0].get('source', 'sysfs')
    timestamps  = [datetime.fromisoformat(r['ts']) for r in records]
    busy        = [r.get('busy_pct', 0.0) for r in records]
    has_temp    = any(r.get('temp_c') is not None for r in records)
    has_power   = source == 'intel_gpu_top' and any(r.get('power_gpu_w', 0) for r in records)
    has_engines = source == 'intel_gpu_top' and any(r.get('engines') for r in records)
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
    if source == 'sysfs':
        throttle_ts = [t for t, r in zip(timestamps, records) if r.get('throttled')]
        if throttle_ts:
            ax1.vlines(throttle_ts, 0, 100, colors='red', alpha=0.4,
                       linewidth=0.8, label='Throttle active')
    ax1.set_ylabel('GPU Busy (%)', fontsize=10)
    ax1.set_ylim(0, 105)
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    # Panel 2 – frequency & RC6
    ax2 = next(ax_iter)
    act_freq = [r.get('act_freq_mhz', 0) for r in records]
    if source == 'intel_gpu_top':
        req_freq = [r.get('req_freq_mhz', 0) for r in records]
        rc6_pct  = [r.get('rc6_pct', 0.0) for r in records]
        ax2.plot(timestamps, act_freq, color='darkorange', linewidth=1.2, label='Actual freq')
        ax2.plot(timestamps, req_freq, color='gold', linewidth=1.0, linestyle='--',
                 label='Requested freq')
        ax2_rc6 = ax2.twinx()
        ax2_rc6.plot(timestamps, rc6_pct, color='grey', linewidth=0.8,
                     linestyle=':', label='RC6 %', alpha=0.7)
        ax2_rc6.set_ylabel('RC6 (%)', fontsize=9, color='grey')
        ax2_rc6.tick_params(axis='y', labelcolor='grey')
        l1, lb1 = ax2.get_legend_handles_labels()
        l2, lb2 = ax2_rc6.get_legend_handles_labels()
        ax2.legend(l1 + l2, lb1 + lb2, loc='upper right', fontsize=8)
    else:
        cur_freq = [r.get('cur_freq_mhz', 0) for r in records]
        ax2.plot(timestamps, act_freq, color='darkorange', linewidth=1.2, label='Actual freq')
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
        print(f"  Saved: {output_file}")
        if not show:
            plt.close()
    if show:
        plt.show()
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='Visualize ROS2 resource monitoring data from pidstat logs',
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
                        help='Path to pidstat log file')
    parser.add_argument('--cores', action='store_true',
                        help='Plot CPU utilization per core')
    parser.add_argument('--pids', action='store_true',
                        help='Plot CPU utilization per PID/thread')
    parser.add_argument('--heatmap', action='store_true',
                        help='Generate core utilization heatmap')
    parser.add_argument('--mapping', action='store_true',
                        help='Show thread-to-core mapping')
    parser.add_argument('--top', type=int, default=10,
                        help='Number of top threads to display (default: 10)')
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
    
    print(f"Parsing log file: {args.log_file}")
    data, sessions = parse_pidstat_log(args.log_file)
    
    if not data['threads'] and not data['pids']:
        print("No data found in log file. Make sure the log contains pidstat output.")
        return
    
    # Report what we found
    if data['threads']:
        print(f"Found {len(data['threads'])} threads across {len(data['timestamps'])} time samples")
    elif data['pids']:
        print(f"Found {len(data['pids'])} processes across {len(data['timestamps'])} time samples")
    
    # Aggregate core utilization
    core_data = aggregate_core_utilization(data)
    
    # Print summary
    print_summary(data, core_data)

    if data.get('num_cpus'):
        print(f"  System CPU count detected from log: {data['num_cpus']} logical cores")
    
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
        print("\nGenerating core utilization plot...")
        plot_core_utilization(core_data, core_out)
    
    if args.pids:
        print(f"\nGenerating top {args.top} thread utilization plot...")
        plot_pid_utilization(data, top_n=args.top, output_file=pid_out)
    
    if args.heatmap:
        print("\nGenerating core utilization heatmap...")
        plot_core_heatmap(core_data, data, heatmap_out)
    
    if args.mapping:
        print("\nGenerating thread-to-core mapping...")
        plot_pid_to_core_mapping(data, mapping_out)

    if args.gpu_log:
        import os
        gpu_out = os.path.join(args.output_dir, 'gpu_utilization.png') if args.output_dir else None
        print("\nGenerating GPU utilization plot...")
        gpu_records = parse_gpu_log(args.gpu_log)
        if gpu_records:
            print(f"  Found {len(gpu_records)} GPU samples")
            plot_gpu(gpu_records, gpu_out, show=(args.show or not args.output_dir))
        else:
            print("  No GPU data found.")

    # Display plots interactively if requested or if no output directory
    if args.show or not args.output_dir:
        print("\nDisplaying plots interactively. Close windows to exit.")
        plt.show()

    print("\nVisualization complete!")


if __name__ == '__main__':
    main()
