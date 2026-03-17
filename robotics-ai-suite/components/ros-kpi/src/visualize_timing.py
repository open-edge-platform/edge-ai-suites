#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Visualize ROS2 timing data from ros2_graph_monitor.py logs.
Creates interactive plots showing message timestamps, frequencies, and processing delays.
"""

import argparse
import csv
import sys
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib.patches import Rectangle


def parse_timing_log(log_file):
    """
    Parse timing log CSV file from ros2_graph_monitor.py.
    
    Returns:
        dict: Parsed timing data organized by topic
    """
    data = {
        'topics': defaultdict(lambda: {
            'timestamps': [],
            'wall_times': [],
            'message_counts': [],
            'delta_times': [],
            'frequencies': [],
            'processing_delays': [],
            'is_input': None,
            'is_output': None,
            'msg_type': None
        }),
        'start_time': None,
        'end_time': None
    }
    
    try:
        with open(log_file, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                topic_name = row['topic_name']
                timestamp = float(row['timestamp'])
                
                topic_data = data['topics'][topic_name]
                
                # Update start/end times
                if data['start_time'] is None or timestamp < data['start_time']:
                    data['start_time'] = timestamp
                if data['end_time'] is None or timestamp > data['end_time']:
                    data['end_time'] = timestamp
                
                # Store data
                topic_data['timestamps'].append(timestamp)
                topic_data['wall_times'].append(datetime.strptime(row['wall_time'], '%Y-%m-%d %H:%M:%S.%f'))
                topic_data['message_counts'].append(int(row['message_count']))
                
                # Handle optional fields (can be empty string, None, or 'None')
                if row['delta_time_ms'] and row['delta_time_ms'].strip() and row['delta_time_ms'] != 'None':
                    try:
                        topic_data['delta_times'].append(float(row['delta_time_ms']))
                    except ValueError:
                        topic_data['delta_times'].append(None)
                else:
                    topic_data['delta_times'].append(None)
                
                if row['frequency_hz'] and row['frequency_hz'].strip() and row['frequency_hz'] != 'None':
                    try:
                        topic_data['frequencies'].append(float(row['frequency_hz']))
                    except ValueError:
                        topic_data['frequencies'].append(None)
                else:
                    topic_data['frequencies'].append(None)
                
                if row['processing_delay_ms'] and row['processing_delay_ms'].strip() and row['processing_delay_ms'] != 'None':
                    try:
                        topic_data['processing_delays'].append(float(row['processing_delay_ms']))
                    except ValueError:
                        topic_data['processing_delays'].append(None)
                else:
                    topic_data['processing_delays'].append(None)
                
                # Store metadata (only need to do this once per topic)
                if topic_data['msg_type'] is None:
                    topic_data['msg_type'] = row['msg_type']
                    topic_data['is_input'] = row['is_input'] == 'True'
                    topic_data['is_output'] = row['is_output'] == 'True'
        
    except Exception as e:
        print(f"Error parsing log file: {e}", file=sys.stderr)
        sys.exit(1)
    
    return data


def plot_message_timestamps(data, output_file=None):
    """
    Plot message arrival timestamps for all topics.
    """
    topics = data['topics']
    
    if not topics:
        print("No topic data found in log file")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(topics)))
    
    for idx, (topic_name, topic_data) in enumerate(sorted(topics.items())):
        if not topic_data['timestamps']:
            continue
        
        # Convert to relative time (seconds from start)
        start_time = data['start_time']
        relative_times = [t - start_time for t in topic_data['timestamps']]
        message_indices = list(range(len(relative_times)))
        
        # Create label with I/O indicator
        io_indicator = ""
        if topic_data['is_input']:
            io_indicator = " [IN]"
        elif topic_data['is_output']:
            io_indicator = " [OUT]"
        
        label = f"{topic_name}{io_indicator}"
        
        ax.scatter(relative_times, message_indices, label=label, alpha=0.6, s=20, color=colors[idx])
    
    ax.set_xlabel('Time (seconds from start)', fontsize=12)
    ax.set_ylabel('Message Index', fontsize=12)
    ax.set_title('ROS2 Message Arrival Timestamps\n(Click legend to toggle series)', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    # Make legend interactive - map legend items to scatter plots
    scatter_map = {}
    for legend_item, scatter_plot in zip(legend.get_texts(), ax.collections):
        scatter_map[legend_item] = scatter_plot
        legend_item.set_picker(True)
    
    def on_pick(event):
        if isinstance(event.artist, plt.Text):
            legend_item = event.artist
            if legend_item in scatter_map:
                scatter_plot = scatter_map[legend_item]
                visible = not scatter_plot.get_visible()
                scatter_plot.set_visible(visible)
                legend_item.set_alpha(1.0 if visible else 0.2)
                fig.canvas.draw_idle()
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")



def plot_topic_frequencies(data, output_file=None):
    """
    Plot topic message frequencies over time.
    """
    topics = data['topics']
    
    if not topics:
        print("No topic data found in log file")
        return
    
    # Check if any topic has frequency data
    has_frequency_data = any(
        any(f is not None for f in topic_data['frequencies'])
        for topic_data in topics.values()
    )
    
    if not has_frequency_data:
        print("No frequency data found in log file (need at least 2 messages per topic to calculate frequency)")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(topics)))
    
    plot_count = 0
    for idx, (topic_name, topic_data) in enumerate(sorted(topics.items())):
        if not topic_data['timestamps']:
            continue
        
        # Filter out None values
        valid_data = [(t - data['start_time'], f) for t, f in zip(topic_data['timestamps'], topic_data['frequencies']) if f is not None]
        
        if not valid_data:
            continue
        
        plot_count += 1
        
        times, freqs = zip(*valid_data)
        
        # Create label with I/O indicator
        io_indicator = ""
        if topic_data['is_input']:
            io_indicator = " [IN]"
        elif topic_data['is_output']:
            io_indicator = " [OUT]"
        
        label = f"{topic_name}{io_indicator}"
        
        ax.plot(times, freqs, label=label, alpha=0.7, linewidth=2, color=colors[idx], marker='o', markersize=3)
    
    if plot_count == 0:
        plt.close(fig)
        print("No frequency data to plot")
        return
    
    ax.set_xlabel('Time (seconds from start)', fontsize=12)
    ax.set_ylabel('Frequency (Hz)', fontsize=12)
    ax.set_title('ROS2 Topic Message Frequencies Over Time\n(Click legend to toggle lines)', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    # Make legend interactive
    line_map = {}
    for legend_item, line in zip(legend.get_texts(), ax.get_lines()):
        line_map[legend_item] = line
        legend_item.set_picker(True)
    
    def on_pick(event):
        if isinstance(event.artist, plt.Text):
            legend_item = event.artist
            if legend_item in line_map:
                line = line_map[legend_item]
                visible = not line.get_visible()
                line.set_visible(visible)
                legend_item.set_alpha(1.0 if visible else 0.2)
                fig.canvas.draw_idle()
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")


def plot_processing_delays(data, output_file=None):
    """
    Plot processing delays over time (only for output topics).
    """
    topics = data['topics']
    
    # Filter for topics with processing delays
    output_topics = {name: tdata for name, tdata in topics.items() 
                     if tdata['is_output'] and any(d is not None for d in tdata['processing_delays'])}
    
    if not output_topics:
        print("No processing delay data found in log file")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(output_topics)))
    
    for idx, (topic_name, topic_data) in enumerate(sorted(output_topics.items())):
        # Filter out None values
        valid_data = [(t - data['start_time'], d) for t, d in zip(topic_data['timestamps'], topic_data['processing_delays']) if d is not None]
        
        if not valid_data:
            continue
        
        times, delays = zip(*valid_data)
        
        ax.plot(times, delays, label=topic_name, alpha=0.7, linewidth=2, color=colors[idx], marker='o', markersize=3)
    
    ax.set_xlabel('Time (seconds from start)', fontsize=12)
    ax.set_ylabel('Processing Delay (ms)', fontsize=12)
    ax.set_title('ROS2 Processing Delays Over Time\n(Input → Output latency, click legend to toggle lines)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    # Make legend interactive
    line_map = {}
    for legend_item, line in zip(legend.get_texts(), ax.get_lines()):
        line_map[legend_item] = line
        legend_item.set_picker(True)
    
    def on_pick(event):
        if isinstance(event.artist, plt.Text):
            legend_item = event.artist
            if legend_item in line_map:
                line = line_map[legend_item]
                visible = not line.get_visible()
                line.set_visible(visible)
                legend_item.set_alpha(1.0 if visible else 0.2)
                fig.canvas.draw_idle()
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")


def plot_inter_arrival_times(data, output_file=None):
    """
    Plot message inter-arrival times (delta times) over time.
    """
    topics = data['topics']
    
    if not topics:
        print("No topic data found in log file")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(topics)))
    
    for idx, (topic_name, topic_data) in enumerate(sorted(topics.items())):
        # Filter out None values
        valid_data = [(t - data['start_time'], d) for t, d in zip(topic_data['timestamps'], topic_data['delta_times']) if d is not None]
        
        if not valid_data:
            continue
        
        times, deltas = zip(*valid_data)
        
        # Create label with I/O indicator
        io_indicator = ""
        if topic_data['is_input']:
            io_indicator = " [IN]"
        elif topic_data['is_output']:
            io_indicator = " [OUT]"
        
        label = f"{topic_name}{io_indicator}"
        
        ax.plot(times, deltas, label=label, alpha=0.7, linewidth=2, color=colors[idx], marker='o', markersize=3)
    
    ax.set_xlabel('Time (seconds from start)', fontsize=12)
    ax.set_ylabel('Inter-Arrival Time (ms)', fontsize=12)
    ax.set_title('ROS2 Message Inter-Arrival Times\n(Time between consecutive messages, click legend to toggle lines)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    # Make legend interactive
    line_map = {}
    for legend_item, line in zip(legend.get_texts(), ax.get_lines()):
        line_map[legend_item] = line
        legend_item.set_picker(True)
    
    def on_pick(event):
        if isinstance(event.artist, plt.Text):
            legend_item = event.artist
            if legend_item in line_map:
                line = line_map[legend_item]
                visible = not line.get_visible()
                line.set_visible(visible)
                legend_item.set_alpha(1.0 if visible else 0.2)
                fig.canvas.draw_idle()
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")


def plot_io_correlation(data, output_file=None):
    """
    Plot input vs output message timing correlation.
    """
    topics = data['topics']
    
    input_topics = {name: tdata for name, tdata in topics.items() if tdata['is_input']}
    output_topics = {name: tdata for name, tdata in topics.items() if tdata['is_output']}
    
    if not input_topics or not output_topics:
        print("Need both input and output topics for correlation plot")
        return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot input topics in one color scheme, outputs in another
    input_colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(input_topics)))
    output_colors = plt.cm.Reds(np.linspace(0.4, 0.9, len(output_topics)))
    
    for idx, (topic_name, topic_data) in enumerate(sorted(input_topics.items())):
        times = [t - data['start_time'] for t in topic_data['timestamps']]
        y_values = [0] * len(times)  # All input messages at y=0
        ax.scatter(times, y_values, label=f"{topic_name} [IN]", alpha=0.6, s=30, color=input_colors[idx], marker='v')
    
    for idx, (topic_name, topic_data) in enumerate(sorted(output_topics.items())):
        times = [t - data['start_time'] for t in topic_data['timestamps']]
        y_values = [1] * len(times)  # All output messages at y=1
        ax.scatter(times, y_values, label=f"{topic_name} [OUT]", alpha=0.6, s=30, color=output_colors[idx], marker='^')
    
    ax.set_xlabel('Time (seconds from start)', fontsize=12)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Input Messages', 'Output Messages'])
    ax.set_title('ROS2 Input/Output Message Timing Correlation\n(Visualize temporal relationship between inputs and outputs)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    legend = ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    # Make legend interactive - map legend items to scatter plots
    scatter_map = {}
    for legend_item, scatter_plot in zip(legend.get_texts(), ax.collections):
        scatter_map[legend_item] = scatter_plot
        legend_item.set_picker(True)
    
    def on_pick(event):
        if isinstance(event.artist, plt.Text):
            legend_item = event.artist
            if legend_item in scatter_map:
                scatter_plot = scatter_map[legend_item]
                visible = not scatter_plot.get_visible()
                scatter_plot.set_visible(visible)
                legend_item.set_alpha(1.0 if visible else 0.2)
                fig.canvas.draw_idle()
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")


def print_summary(data):
    """
    Print summary statistics.
    """
    topics = data['topics']
    
    print("\n" + "="*80)
    print("TIMING DATA SUMMARY")
    print("="*80)
    
    total_messages = sum(tdata['message_counts'][-1] if tdata['message_counts'] else 0 
                         for tdata in topics.values())
    
    duration = data['end_time'] - data['start_time'] if data['start_time'] and data['end_time'] else 0
    
    print(f"\nTotal topics monitored: {len(topics)}")
    print(f"Total messages logged: {total_messages}")
    print(f"Monitoring duration: {duration:.2f} seconds")
    
    if data['start_time']:
        print(f"Start time: {datetime.fromtimestamp(data['start_time']).strftime('%Y-%m-%d %H:%M:%S.%f')}")
    if data['end_time']:
        print(f"End time: {datetime.fromtimestamp(data['end_time']).strftime('%Y-%m-%d %H:%M:%S.%f')}")
    
    # Per-topic statistics
    print(f"\n{'='*80}")
    print("TOPIC STATISTICS")
    print(f"{'='*80}")
    print(f"{'Topic':<40} {'Type':<6} {'Msgs':<8} {'Avg Freq':<12} {'Avg Delay':<12}")
    print("-"*80)
    
    for topic_name, topic_data in sorted(topics.items()):
        io_type = "IN" if topic_data['is_input'] else ("OUT" if topic_data['is_output'] else "-")
        msg_count = topic_data['message_counts'][-1] if topic_data['message_counts'] else 0
        
        # Calculate average frequency
        valid_freqs = [f for f in topic_data['frequencies'] if f is not None]
        avg_freq = sum(valid_freqs) / len(valid_freqs) if valid_freqs else 0
        
        # Calculate average processing delay
        valid_delays = [d for d in topic_data['processing_delays'] if d is not None]
        avg_delay = sum(valid_delays) / len(valid_delays) if valid_delays else None
        
        freq_str = f"{avg_freq:.2f} Hz" if avg_freq > 0 else "-"
        delay_str = f"{avg_delay:.2f} ms" if avg_delay is not None else "-"
        
        # Truncate long topic names
        display_name = topic_name if len(topic_name) <= 38 else topic_name[:35] + "..."
        
        print(f"{display_name:<40} {io_type:<6} {msg_count:<8} {freq_str:<12} {delay_str:<12}")
    
    print("\n")


def categorize_topic(topic_name: str, msg_type: str) -> str:
    """
    Categorize a topic into one of four categories.
    
    Args:
        topic_name: The name of the topic (e.g., '/scan', '/cmd_vel')
        msg_type: The message type (e.g., 'sensor_msgs/msg/LaserScan')
        
    Returns:
        One of: 'Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other'
    """
    topic_lower = topic_name.lower()
    type_lower = msg_type.lower() if msg_type else ''
    
    # Sensor category - raw sensor data
    sensor_patterns = [
        '/scan', '/laser', '/lidar', '/camera', '/image', '/imu', '/gps', '/gnss',
        '/odom', '/odometry', '/depth', '/pointcloud', '/point_cloud', '/ultrasonic',
        '/sonar', '/range', '/battery', '/joint_states', '/tf', '/clock'
    ]
    sensor_types = ['sensor_msgs', 'tf2_msgs']
    
    # Perception category - processed sensor data, maps, costmaps
    perception_patterns = [
        '/map', '/costmap', '/obstacles', '/detections', '/tracked', '/classification',
        '/semantic', '/occupancy', '/global_costmap', '/local_costmap', '/voxel',
        '/footprint', '/markers', '/visualization'
    ]
    perception_types = ['nav_msgs/msg/occupancygrid', 'nav_msgs/msg/odometry', 'visualization_msgs']
    
    # Motion Planning category - paths, goals, planning
    planning_patterns = [
        '/plan', '/path', '/global_plan', '/local_plan', '/trajectory', '/goal',
        '/waypoint', '/route', '/planner', '/planning', '/navigate'
    ]
    planning_types = ['nav_msgs/msg/path', 'nav2_msgs', 'action']
    
    # Controls category - velocity commands, control outputs
    control_patterns = [
        '/cmd_vel', '/cmd', '/control', '/velocity', '/speed', '/steering',
        '/throttle', '/brake', '/motor', '/actuator', '/joint_command'
    ]
    control_types = ['geometry_msgs/msg/twist', 'ackermann_msgs', 'control_msgs']
    
    # Check each category
    if any(pattern in topic_lower for pattern in sensor_patterns) or \
       any(sensor_type in type_lower for sensor_type in sensor_types):
        return 'Sensor'
    
    if any(pattern in topic_lower for pattern in perception_patterns) or \
       any(perc_type in type_lower for perc_type in perception_types):
        return 'Perception'
    
    if any(pattern in topic_lower for pattern in planning_patterns) or \
       any(plan_type in type_lower for plan_type in planning_types):
        return 'Motion Planning'
    
    if any(pattern in topic_lower for pattern in control_patterns) or \
       any(ctrl_type in type_lower for ctrl_type in control_types):
        return 'Controls'
    
    return 'Other'


def plot_category_statistics(data, output_file=None):
    """
    Plot statistics grouped by topic category (Sensor, Perception, Motion Planning, Controls).
    Shows message counts, average frequencies, and processing delays per category.
    """
    topics = data['topics']
    
    if not topics:
        print("No topic data found in log file")
        return
    
    # Categorize topics and collect statistics
    category_stats = {
        'Sensor': {'topics': [], 'msgs': 0, 'freqs': [], 'delays': []},
        'Perception': {'topics': [], 'msgs': 0, 'freqs': [], 'delays': []},
        'Motion Planning': {'topics': [], 'msgs': 0, 'freqs': [], 'delays': []},
        'Controls': {'topics': [], 'msgs': 0, 'freqs': [], 'delays': []},
        'Other': {'topics': [], 'msgs': 0, 'freqs': [], 'delays': []}
    }
    
    for topic_name, topic_data in topics.items():
        category = categorize_topic(topic_name, topic_data['msg_type'])
        
        category_stats[category]['topics'].append(topic_name)
        
        # Message count
        if topic_data['message_counts']:
            category_stats[category]['msgs'] += topic_data['message_counts'][-1]
        
        # Frequencies
        valid_freqs = [f for f in topic_data['frequencies'] if f is not None]
        if valid_freqs:
            category_stats[category]['freqs'].extend(valid_freqs)
        
        # Processing delays
        valid_delays = [d for d in topic_data['processing_delays'] if d is not None]
        if valid_delays:
            category_stats[category]['delays'].extend(valid_delays)
    
    # Filter out empty categories
    category_stats = {k: v for k, v in category_stats.items() if v['topics']}
    
    if not category_stats:
        print("No categorized topics found")
        return
    
    # Create subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    categories = list(category_stats.keys())
    colors = {'Sensor': '#FF6B6B', 'Perception': '#4ECDC4', 
              'Motion Planning': '#45B7D1', 'Controls': '#FFA07A', 'Other': '#95A99C'}
    category_colors = [colors.get(cat, '#95A99C') for cat in categories]
    
    # 1. Number of topics per category (bar chart)
    topic_counts = [len(category_stats[cat]['topics']) for cat in categories]
    bars1 = ax1.bar(range(len(categories)), topic_counts, color=category_colors, alpha=0.7, edgecolor='black')
    ax1.set_xlabel('Category', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Number of Topics', fontsize=12, fontweight='bold')
    ax1.set_title('Topics per Category', fontsize=14, fontweight='bold')
    ax1.set_xticks(range(len(categories)))
    ax1.set_xticklabels(categories, rotation=15, ha='right')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, count in zip(bars1, topic_counts):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count)}',
                ha='center', va='bottom', fontweight='bold')
    
    # 2. Total messages per category (bar chart)
    msg_counts = [category_stats[cat]['msgs'] for cat in categories]
    bars2 = ax2.bar(range(len(categories)), msg_counts, color=category_colors, alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Category', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Total Messages', fontsize=12, fontweight='bold')
    ax2.set_title('Message Count per Category', fontsize=14, fontweight='bold')
    ax2.set_xticks(range(len(categories)))
    ax2.set_xticklabels(categories, rotation=15, ha='right')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, count in zip(bars2, msg_counts):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count)}',
                ha='center', va='bottom', fontweight='bold')
    
    # 3. Average frequency per category (box plot)
    freq_data = [category_stats[cat]['freqs'] for cat in categories if category_stats[cat]['freqs']]
    freq_labels = [cat for cat in categories if category_stats[cat]['freqs']]
    
    if freq_data:
        bp1 = ax3.boxplot(freq_data, labels=freq_labels, patch_artist=True, showmeans=True)
        for patch, cat in zip(bp1['boxes'], [cat for cat in categories if category_stats[cat]['freqs']]):
            patch.set_facecolor(colors.get(cat, '#95A99C'))
            patch.set_alpha(0.7)
        ax3.set_ylabel('Frequency (Hz)', fontsize=12, fontweight='bold')
        ax3.set_title('Frequency Distribution by Category', fontsize=14, fontweight='bold')
        ax3.set_xticklabels(freq_labels, rotation=15, ha='right')
        ax3.grid(True, alpha=0.3, axis='y')
    else:
        ax3.text(0.5, 0.5, 'No frequency data available', 
                ha='center', va='center', transform=ax3.transAxes, fontsize=12)
        ax3.set_title('Frequency Distribution by Category', fontsize=14, fontweight='bold')
    
    # 4. Processing delays per category (box plot)
    delay_data = [category_stats[cat]['delays'] for cat in categories if category_stats[cat]['delays']]
    delay_labels = [cat for cat in categories if category_stats[cat]['delays']]
    
    if delay_data:
        bp2 = ax4.boxplot(delay_data, labels=delay_labels, patch_artist=True, showmeans=True)
        for patch, cat in zip(bp2['boxes'], [cat for cat in categories if category_stats[cat]['delays']]):
            patch.set_facecolor(colors.get(cat, '#95A99C'))
            patch.set_alpha(0.7)
        ax4.set_ylabel('Processing Delay (ms)', fontsize=12, fontweight='bold')
        ax4.set_title('Processing Delay Distribution by Category', fontsize=14, fontweight='bold')
        ax4.set_xticklabels(delay_labels, rotation=15, ha='right')
        ax4.grid(True, alpha=0.3, axis='y')
    else:
        ax4.text(0.5, 0.5, 'No processing delay data available', 
                ha='center', va='center', transform=ax4.transAxes, fontsize=12)
        ax4.set_title('Processing Delay Distribution by Category', fontsize=14, fontweight='bold')
    
    plt.suptitle('ROS2 Topic Category Statistics', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")


def plot_topic_activity_heatmap(data, output_file=None):
    """
    Plot a heatmap showing topic activity (message frequency) over time.
    Each row represents a topic, and color intensity shows message frequency.
    """
    topics = data['topics']
    
    if not topics:
        print("No topic data found in log file")
        return
    
    # Filter topics with frequency data
    topics_with_data = {name: tdata for name, tdata in topics.items() 
                       if tdata['frequencies'] and any(f is not None for f in tdata['frequencies'])}
    
    if not topics_with_data:
        print("No frequency data available for heatmap")
        return
    
    # Sort topics by average frequency (most active first)
    topic_avg_freq = []
    for name, tdata in topics_with_data.items():
        valid_freqs = [f for f in tdata['frequencies'] if f is not None and f > 0]
        avg_freq = sum(valid_freqs) / len(valid_freqs) if valid_freqs else 0
        topic_avg_freq.append((name, avg_freq))
    
    topic_avg_freq.sort(key=lambda x: x[1], reverse=True)
    sorted_topics = [name for name, _ in topic_avg_freq]
    
    # Prepare time bins (use start_time to create regular intervals)
    start_time = data['start_time']
    end_time = data['end_time']
    duration = end_time - start_time
    
    # Create time bins (e.g., 100 bins across the duration)
    num_bins = min(100, int(duration) + 1)
    time_bins = np.linspace(start_time, end_time, num_bins + 1)
    bin_centers = (time_bins[:-1] + time_bins[1:]) / 2
    
    # Create heatmap matrix
    heatmap_data = np.zeros((len(sorted_topics), num_bins))
    
    for topic_idx, topic_name in enumerate(sorted_topics):
        topic_data = topics_with_data[topic_name]
        
        # Bin the frequency data
        for timestamp, freq in zip(topic_data['timestamps'], topic_data['frequencies']):
            if freq is not None and freq > 0:
                # Find which bin this timestamp belongs to
                bin_idx = np.searchsorted(time_bins[1:], timestamp)
                if 0 <= bin_idx < num_bins:
                    heatmap_data[topic_idx, bin_idx] = max(heatmap_data[topic_idx, bin_idx], freq)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, max(8, len(sorted_topics) * 0.3)))
    
    # Plot heatmap
    im = ax.imshow(heatmap_data, aspect='auto', cmap='YlOrRd', interpolation='nearest')
    
    # Set axis labels
    ax.set_xlabel('Time (seconds from start)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Topic', fontsize=12, fontweight='bold')
    ax.set_title('ROS2 Topic Activity Heatmap\n(Message Frequency Over Time)', 
                 fontsize=14, fontweight='bold')
    
    # Set y-axis ticks (topic names)
    ax.set_yticks(range(len(sorted_topics)))
    
    # Truncate long topic names for display
    display_names = []
    for name in sorted_topics:
        topic_data = topics_with_data[name]
        io_indicator = ""
        if topic_data['is_input']:
            io_indicator = " [IN]"
        elif topic_data['is_output']:
            io_indicator = " [OUT]"
        
        display_name = name + io_indicator
        if len(display_name) > 35:
            display_name = display_name[:32] + "..."
        display_names.append(display_name)
    
    ax.set_yticklabels(display_names, fontsize=8)
    
    # Set x-axis ticks (time)
    num_time_ticks = 10
    tick_indices = np.linspace(0, num_bins - 1, num_time_ticks, dtype=int)
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([f"{(bin_centers[i] - start_time):.1f}" for i in tick_indices])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Frequency (Hz)')
    cbar.ax.set_ylabel('Frequency (Hz)', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")


def plot_topic_delay_heatmap(data, output_file=None):
    """
    Plot a heatmap showing processing delays across topics over time.
    Each row represents a topic, and color intensity shows processing delay.
    """
    topics = data['topics']
    
    if not topics:
        print("No topic data found in log file")
        return
    
    # Filter topics with delay data
    topics_with_data = {name: tdata for name, tdata in topics.items() 
                       if tdata['processing_delays'] and any(d is not None for d in tdata['processing_delays'])}
    
    if not topics_with_data:
        print("No processing delay data available for heatmap")
        return
    
    # Sort topics by average delay (highest delay first)
    topic_avg_delay = []
    for name, tdata in topics_with_data.items():
        valid_delays = [d for d in tdata['processing_delays'] if d is not None and d > 0]
        avg_delay = sum(valid_delays) / len(valid_delays) if valid_delays else 0
        topic_avg_delay.append((name, avg_delay))
    
    topic_avg_delay.sort(key=lambda x: x[1], reverse=True)
    sorted_topics = [name for name, _ in topic_avg_delay]
    
    # Prepare time bins
    start_time = data['start_time']
    end_time = data['end_time']
    duration = end_time - start_time
    
    # Create time bins (e.g., 100 bins across the duration)
    num_bins = min(100, int(duration) + 1)
    time_bins = np.linspace(start_time, end_time, num_bins + 1)
    bin_centers = (time_bins[:-1] + time_bins[1:]) / 2
    
    # Create heatmap matrix
    heatmap_data = np.zeros((len(sorted_topics), num_bins))
    
    for topic_idx, topic_name in enumerate(sorted_topics):
        topic_data = topics_with_data[topic_name]
        
        # Bin the delay data
        for timestamp, delay in zip(topic_data['timestamps'], topic_data['processing_delays']):
            if delay is not None and delay > 0:
                # Find which bin this timestamp belongs to
                bin_idx = np.searchsorted(time_bins[1:], timestamp)
                if 0 <= bin_idx < num_bins:
                    heatmap_data[topic_idx, bin_idx] = max(heatmap_data[topic_idx, bin_idx], delay)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, max(8, len(sorted_topics) * 0.3)))
    
    # Plot heatmap
    im = ax.imshow(heatmap_data, aspect='auto', cmap='RdYlGn_r', interpolation='nearest')
    
    # Set axis labels
    ax.set_xlabel('Time (seconds from start)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Topic', fontsize=12, fontweight='bold')
    ax.set_title('ROS2 Topic Processing Delay Heatmap\n(Processing Delays Over Time)', 
                 fontsize=14, fontweight='bold')
    
    # Set y-axis ticks (topic names)
    ax.set_yticks(range(len(sorted_topics)))
    
    # Truncate long topic names for display
    display_names = []
    for name in sorted_topics:
        topic_data = topics_with_data[name]
        io_indicator = ""
        if topic_data['is_input']:
            io_indicator = " [IN]"
        elif topic_data['is_output']:
            io_indicator = " [OUT]"
        
        display_name = name + io_indicator
        if len(display_name) > 35:
            display_name = display_name[:32] + "..."
        display_names.append(display_name)
    
    ax.set_yticklabels(display_names, fontsize=8)
    
    # Set x-axis ticks (time)
    num_time_ticks = 10
    tick_indices = np.linspace(0, num_bins - 1, num_time_ticks, dtype=int)
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([f"{(bin_centers[i] - start_time):.1f}" for i in tick_indices])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Processing Delay (ms)')
    cbar.ax.set_ylabel('Processing Delay (ms)', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {output_file}")



def main():
    parser = argparse.ArgumentParser(
        description='Visualize ROS2 timing data from ros2_graph_monitor.py logs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all plots
  %(prog)s timing_log.csv
  
  # Generate specific plots
  %(prog)s timing_log.csv --timestamps --frequencies
  
  # Save plots to files
  %(prog)s timing_log.csv --output-dir ./plots/
  
  # Print summary only
  %(prog)s timing_log.csv --summary
        """
    )
    
    parser.add_argument('log_file', type=str,
                        help='Path to timing CSV log file from ros2_graph_monitor.py')
    parser.add_argument('--timestamps', action='store_true',
                        help='Plot message arrival timestamps')
    parser.add_argument('--frequencies', action='store_true',
                        help='Plot topic message frequencies over time')
    parser.add_argument('--delays', action='store_true',
                        help='Plot processing delays over time')
    parser.add_argument('--inter-arrival', action='store_true',
                        help='Plot message inter-arrival times')
    parser.add_argument('--io-correlation', action='store_true',
                        help='Plot input/output message timing correlation')
    parser.add_argument('--categories', action='store_true',
                        help='Plot topic statistics grouped by category (Sensor/Perception/Planning/Controls)')
    parser.add_argument('--activity-heatmap', action='store_true',
                        help='Plot topic activity heatmap showing frequency over time')
    parser.add_argument('--delay-heatmap', action='store_true',
                        help='Plot topic delay heatmap showing processing delays over time')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory to save plots (if not specified, displays interactively)')
    parser.add_argument('--show', action='store_true',
                        help='Display plots interactively (in addition to saving if --output-dir is set)')
    parser.add_argument('--summary', action='store_true',
                        help='Print summary statistics only')
    
    args = parser.parse_args()
    
    # Parse log file
    print(f"Parsing timing log: {args.log_file}")
    data = parse_timing_log(args.log_file)
    
    if not data['topics']:
        print("No data found in log file")
        sys.exit(1)
    
    # Print summary
    print_summary(data)
    
    # If --summary only, exit
    if args.summary:
        return
    
    # Determine which plots to generate
    generate_all = not any([
        args.timestamps,
        args.frequencies,
        args.delays,
        args.inter_arrival,
        args.io_correlation,
        args.categories,
        args.activity_heatmap,
        args.delay_heatmap
    ])
    
    # Prepare output directory
    output_dir = args.output_dir
    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nSaving plots to: {output_dir}")
    
    # Generate plots
    if generate_all or args.timestamps:
        print("\nGenerating message timestamps plot...")
        output_file = f"{output_dir}/message_timestamps.png" if output_dir else None
        plot_message_timestamps(data, output_file)
    
    if generate_all or args.frequencies:
        print("\nGenerating topic frequencies plot...")
        output_file = f"{output_dir}/topic_frequencies.png" if output_dir else None
        plot_topic_frequencies(data, output_file)
    
    if generate_all or args.delays:
        print("\nGenerating processing delays plot...")
        output_file = f"{output_dir}/processing_delays.png" if output_dir else None
        plot_processing_delays(data, output_file)
    
    if generate_all or args.inter_arrival:
        print("\nGenerating inter-arrival times plot...")
        output_file = f"{output_dir}/inter_arrival_times.png" if output_dir else None
        plot_inter_arrival_times(data, output_file)
    
    if generate_all or args.io_correlation:
        print("\nGenerating I/O correlation plot...")
        output_file = f"{output_dir}/io_correlation.png" if output_dir else None
        plot_io_correlation(data, output_file)
    
    if generate_all or args.categories:
        print("\nGenerating category statistics plot...")
        output_file = f"{output_dir}/category_statistics.png" if output_dir else None
        plot_category_statistics(data, output_file)
    
    if generate_all or args.activity_heatmap:
        print("\nGenerating topic activity heatmap...")
        output_file = f"{output_dir}/topic_activity_heatmap.png" if output_dir else None
        plot_topic_activity_heatmap(data, output_file)
    
    if generate_all or args.delay_heatmap:
        print("\nGenerating topic delay heatmap...")
        output_file = f"{output_dir}/topic_delay_heatmap.png" if output_dir else None
        plot_topic_delay_heatmap(data, output_file)
    
    # Display plots interactively if requested or if no output directory
    if args.show or not output_dir:
        print("\nDisplaying plots interactively. Close windows to exit.")
        plt.show()
    
    if output_dir:
        print("\nAll plots saved successfully!")


if __name__ == '__main__':
    main()
