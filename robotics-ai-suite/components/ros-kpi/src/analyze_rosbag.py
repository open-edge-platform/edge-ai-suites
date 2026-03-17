#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
import sqlite3
import psutil
from datetime import datetime
from collections import defaultdict
import sys

db_path = "/home/intel/rosbag2_2025_12_19-10_33_21/rosbag2_2025_12_19-10_33_21_0.db3"

# Get CPU information
cpu_freq = psutil.cpu_freq()
cpu_model = "Unknown"
try:
    with open('/proc/cpuinfo', 'r') as f:
        for line in f:
            if 'model name' in line:
                cpu_model = line.split(':')[1].strip()
                break
except:
    pass

print("=" * 80)
print("HOST SYSTEM INFORMATION")
print("=" * 80)
print(f"CPU Model: {cpu_model}")
print(f"CPU Max Speed: {cpu_freq.max:.1f} MHz")
print(f"CPU Cycles per ms: {cpu_freq.max * 1000:.0f} cycles")
print()

def format_duration_with_cycles(duration_s, cpu_mhz):
    """Format duration showing seconds, milliseconds, and CPU cycles"""
    duration_ms = duration_s * 1000
    cycles = duration_s * cpu_mhz * 1e6
    return f"{duration_s:.2f}s ({duration_ms:.2f}ms, ~{cycles/1e6:.1f}M cycles)"

def format_gap_with_cycles(gap_ms, cpu_mhz):
    """Format time gap with CPU cycles"""
    cycles = gap_ms * cpu_mhz * 1000
    return f"{gap_ms:.2f}ms (~{cycles/1e6:.1f}M cycles)"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get topics
cursor.execute("SELECT id, name, type FROM topics")
topics = {row[0]: {'name': row[1], 'type': row[2]} for row in cursor.fetchall()}

print("=" * 80)
print("ROSBAG ANALYSIS - All Topics with CPU Timing")
print("=" * 80)

# Categorize topics as input or output
input_topics = []
output_topics = []
transform_topics = []

for topic_id, topic_info in topics.items():
    name = topic_info['name']
    if '/map' in name or '/costmap' in name or '/path' in name or '/goal' in name:
        output_topics.append(topic_id)
    elif '/tf' in name:
        transform_topics.append(topic_id)
    else:
        input_topics.append(topic_id)

for topic_id, topic_info in topics.items():
    print(f"\nTopic ID: {topic_id}")
    print(f"Topic Name: {topic_info['name']}")
    print(f"Message Type: {topic_info['type']}")
    
    # Get message statistics
    cursor.execute("""
        SELECT 
            COUNT(*) as count,
            MIN(timestamp) as first_ts,
            MAX(timestamp) as last_ts
        FROM messages 
        WHERE topic_id = ?
    """, (topic_id,))
    
    result = cursor.fetchone()
    count, first_ts, last_ts = result
    
    if count > 0:
        duration_ns = last_ts - first_ts
        duration_s = duration_ns / 1e9
        frequency = count / duration_s if duration_s > 0 else 0
        
        print(f"Message Count: {count}")
        print(f"First Message: {first_ts} ({datetime.fromtimestamp(first_ts/1e9).strftime('%Y-%m-%d %H:%M:%S.%f')})")
        print(f"Last Message:  {last_ts} ({datetime.fromtimestamp(last_ts/1e9).strftime('%Y-%m-%d %H:%M:%S.%f')})")
        print(f"Duration: {format_duration_with_cycles(duration_s, cpu_freq.max)}")
        print(f"Average Frequency: {frequency:.2f} Hz")
        
        # Get time gaps between messages
        cursor.execute("""
            SELECT timestamp
            FROM messages 
            WHERE topic_id = ?
            ORDER BY timestamp
            LIMIT 100
        """, (topic_id,))
        
        timestamps = [row[0] for row in cursor.fetchall()]
        if len(timestamps) > 1:
            gaps = [(timestamps[i+1] - timestamps[i])/1e6 for i in range(len(timestamps)-1)]
            avg_gap = sum(gaps) / len(gaps)
            min_gap = min(gaps)
            max_gap = max(gaps)
            
            print(f"  Time gaps (first 99 messages):")
            print(f"    Average: {format_gap_with_cycles(avg_gap, cpu_freq.max)}")
            print(f"    Min: {format_gap_with_cycles(min_gap, cpu_freq.max)}")
            print(f"    Max: {format_gap_with_cycles(max_gap, cpu_freq.max)}")

print("\n" + "=" * 80)
print("INPUT/OUTPUT MESSAGE FLOW WITH LATENCY ANALYSIS")
print("=" * 80)

# Find input and output topics
cursor.execute("""
    SELECT DISTINCT t.id, t.name, t.type
    FROM topics t
    JOIN messages m ON t.id = m.topic_id
    ORDER BY t.name
""")

all_topics_list = cursor.fetchall()

# Separate topics
sensor_topics = [t for t in all_topics_list if 'scan' in t[1] or 'odom' in t[1] or 'camera' in t[1] or 'image' in t[1]]
map_output = [t for t in all_topics_list if '/map' == t[1]]
other_outputs = [t for t in all_topics_list if 'costmap' in t[1] or 'path' in t[1]]

print("\nINPUT TOPICS (Sensors):")
for tid, name, mtype in sensor_topics:
    cursor.execute("SELECT COUNT(*) FROM messages WHERE topic_id = ?", (tid,))
    count = cursor.fetchone()[0]
    print(f"  - {name} ({mtype}) - {count} messages")

print("\nOUTPUT TOPICS:")
for tid, name, mtype in map_output + other_outputs:
    cursor.execute("SELECT COUNT(*) FROM messages WHERE topic_id = ?", (tid,))
    count = cursor.fetchone()[0]
    print(f"  - {name} ({mtype}) - {count} messages")

print("\n" + "=" * 80)
print("LATENCY ANALYSIS: Input to Output Delays")
print("=" * 80)

# For each output message, find the most recent input messages
if map_output:
    map_topic_id = map_output[0][0]
    
    cursor.execute("""
        SELECT timestamp
        FROM messages
        WHERE topic_id = ?
        ORDER BY timestamp
        LIMIT 50
    """, (map_topic_id,))
    
    map_timestamps = [row[0] for row in cursor.fetchall()]
    
    print(f"\nAnalyzing latency for first 50 /map output messages")
    print(f"Map #    Map Time (s)  Input to Output Delays")
    print("-" * 100)
    
    for idx, map_ts in enumerate(map_timestamps):
        delays_info = []
        
        # Check each sensor topic for most recent message before this map output
        for sensor_tid, sensor_name, _ in sensor_topics:
            cursor.execute("""
                SELECT timestamp
                FROM messages
                WHERE topic_id = ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (sensor_tid, map_ts))
            
            result = cursor.fetchone()
            if result:
                input_ts = result[0]
                delay_ms = (map_ts - input_ts) / 1e6
                delay_cycles = delay_ms * cpu_freq.max * 1000
                
                # Short name for display
                short_name = sensor_name.split('/')[-1]
                delays_info.append(f"{short_name}:{delay_ms:.1f}ms")
        
        map_time_s = (map_ts - map_timestamps[0]) / 1e9
        delays_str = ", ".join(delays_info) if delays_info else "No inputs found"
        
        print(f"{idx+1:<8} {map_time_s:<12.3f}  {delays_str}")

print("\n" + "=" * 80)
print("DETAILED MESSAGE TIMELINE (First 100 messages)")
print("=" * 80)
print(f"\nSeq    Time (ms)       Delta (ms)   Type  Topic                                    Message Type")
print("-" * 110)

cursor.execute("""
    SELECT m.topic_id, m.timestamp, t.name, t.type
    FROM messages m
    JOIN topics t ON m.topic_id = t.id
    ORDER BY m.timestamp
    LIMIT 100
""")

rows = cursor.fetchall()
prev_ts = None

for seq, (topic_id, timestamp, topic_name, topic_type) in enumerate(rows, 1):
    time_ms = timestamp / 1e6
    delta_ms = (timestamp - prev_ts) / 1e6 if prev_ts else 0
    
    # Mark input vs output
    marker = "IN " if any(s in topic_name for s in ['scan', 'odom', 'camera', 'image']) else "OUT"
    
    print(f"{seq:<6} {time_ms:<15.2f} {delta_ms:<12.2f} {marker}   {topic_name:<40} {topic_type:<20}")
    prev_ts = timestamp

print("\n" + "=" * 80)
print("INPUT-OUTPUT CORRELATION MATRIX")
print("=" * 80)

if sensor_topics and map_output:
    print("\nFor each /map output, showing delay from most recent input messages:\n")
    
    # Get a sample of map messages
    cursor.execute("""
        SELECT timestamp
        FROM messages
        WHERE topic_id = ?
        ORDER BY timestamp
        LIMIT 20
    """, (map_output[0][0],))
    
    sample_map_ts = [row[0] for row in cursor.fetchall()]
    
    # Header
    header = f"Map #    Time(s)   "
    for _, name, _ in sensor_topics:
        short_name = name.split('/')[-1][:15]
        header += f" {short_name:<18}"
    print(header)
    print("-" * (18 + len(sensor_topics) * 20))
    
    for idx, map_ts in enumerate(sample_map_ts, 1):
        row_data = f"{idx:<8} {(map_ts - sample_map_ts[0])/1e9:<10.2f}"
        
        for sensor_tid, sensor_name, _ in sensor_topics:
            cursor.execute("""
                SELECT timestamp
                FROM messages
                WHERE topic_id = ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (sensor_tid, map_ts))
            
            result = cursor.fetchone()
            if result:
                delay_ms = (map_ts - result[0]) / 1e6
                row_data += f" {delay_ms:>8.1f}ms ({delay_ms*cpu_freq.max*1000/1e6:.0f}Mc)"
            else:
                row_data += f" {'N/A':>18}"
        
        print(row_data)

print("\n" + "=" * 80)
print("NODE ANALYSIS - Time Traversal")
print("=" * 80)

# Build topic to node mapping (approximate based on topic names)
def infer_node_from_topic(topic_name):
    """Infer likely node name from topic"""
    if '/map' in topic_name:
        return 'slam_toolbox' if 'slam' in topic_name else 'map_server'
    elif '/scan' in topic_name:
        return 'lidar_driver'
    elif '/odom' in topic_name:
        return 'odometry_publisher'
    elif '/camera' in topic_name or '/image' in topic_name:
        return 'camera_driver'
    elif '/costmap' in topic_name:
        return 'costmap_2d'
    elif '/tf' in topic_name:
        return 'robot_state_publisher'
    else:
        return 'unknown_node'

# Create node graph
node_topics = defaultdict(lambda: {'publishes': [], 'subscribes': []})

for topic_id, topic_info in topics.items():
    topic_name = topic_info['name']
    node = infer_node_from_topic(topic_name)
    
    # Assume nodes publish to topics with their name
    if node in topic_name or topic_name.startswith(f'/{node}'):
        node_topics[node]['publishes'].append(topic_name)
    else:
        node_topics[node]['subscribes'].append(topic_name)

print("\nInferred Node Graph:")
print("-" * 80)
for node, data in sorted(node_topics.items()):
    print(f"\nNode: {node}")
    if data['publishes']:
        print(f"  Publishes to: {', '.join(data['publishes'])}")
    if data['subscribes']:
        print(f"  Subscribes to: {', '.join(data['subscribes'])}")

# Interactive node traversal
print("\n" + "=" * 80)
print("INTERACTIVE NODE TIME TRAVERSAL")
print("=" * 80)
print("\nAvailable nodes:")
for i, node in enumerate(sorted(node_topics.keys()), 1):
    print(f"  {i}. {node}")

print("\nEnter node name to analyze (or press Enter to skip):")
target_node = input("> ").strip()

if target_node and target_node in node_topics:
    print(f"\n" + "=" * 80)
    print(f"TIME TRAVERSAL FOR NODE: {target_node}")
    print("=" * 80)
    
    # Get all topics associated with this node
    node_topic_names = node_topics[target_node]['publishes'] + node_topics[target_node]['subscribes']
    node_topic_ids = [tid for tid, tinfo in topics.items() if tinfo['name'] in node_topic_names]
    
    if not node_topic_ids:
        print(f"No topics found for node {target_node}")
    else:
        # Get all messages for this node's topics
        placeholders = ','.join('?' * len(node_topic_ids))
        cursor.execute(f"""
            SELECT m.timestamp, t.name, t.type, m.topic_id
            FROM messages m
            JOIN topics t ON m.topic_id = t.id
            WHERE m.topic_id IN ({placeholders})
            ORDER BY m.timestamp
            LIMIT 200
        """, node_topic_ids)
        
        node_messages = cursor.fetchall()
        
        if not node_messages:
            print(f"No messages found for node {target_node}")
        else:
            print(f"\nFound {len(node_messages)} messages (showing first 200)")
            print(f"\n{'Seq':<6} {'Time (s)':<12} {'Delta (ms)':<12} {'Direction':<10} {'Topic':<40}")
            print("-" * 90)
            
            start_time = node_messages[0][0]
            prev_time = None
            
            for seq, (timestamp, topic_name, topic_type, topic_id) in enumerate(node_messages, 1):
                time_s = (timestamp - start_time) / 1e9
                delta_ms = (timestamp - prev_time) / 1e6 if prev_time else 0
                
                # Determine if this is input or output for this node
                if topic_name in node_topics[target_node]['publishes']:
                    direction = "OUTPUT"
                else:
                    direction = "INPUT"
                
                print(f"{seq:<6} {time_s:<12.6f} {delta_ms:<12.2f} {direction:<10} {topic_name:<40}")
                prev_time = timestamp
            
            # Processing time analysis
            print(f"\n" + "=" * 80)
            print(f"PROCESSING TIME ANALYSIS FOR {target_node}")
            print("=" * 80)
            
            # Group messages into processing cycles (input -> output)
            print("\nInput-to-Output Processing Time:")
            print(f"{'Cycle':<8} {'Input Time (s)':<15} {'Output Time (s)':<15} {'Processing (ms)':<15} {'CPU Cycles (M)':<15}")
            print("-" * 80)
            
            input_msgs = [(ts, tn) for ts, tn, _, _ in node_messages if tn in node_topics[target_node]['subscribes']]
            output_msgs = [(ts, tn) for ts, tn, _, _ in node_messages if tn in node_topics[target_node]['publishes']]
            
            cycle = 0
            for out_ts, out_topic in output_msgs[:50]:  # Analyze first 50 output messages
                # Find most recent input before this output
                recent_inputs = [(in_ts, in_topic) for in_ts, in_topic in input_msgs if in_ts <= out_ts]
                if recent_inputs:
                    in_ts, in_topic = recent_inputs[-1]
                    processing_ms = (out_ts - in_ts) / 1e6
                    processing_cycles = processing_ms * cpu_freq.max * 1000 / 1e6
                    
                    in_time_s = (in_ts - start_time) / 1e9
                    out_time_s = (out_ts - start_time) / 1e9
                    
                    cycle += 1
                    print(f"{cycle:<8} {in_time_s:<15.6f} {out_time_s:<15.6f} {processing_ms:<15.2f} {processing_cycles:<15.1f}")
            
            if cycle == 0:
                print("No input-output pairs found for processing time analysis")

conn.close()

print("\n" + "=" * 80)
print("Analysis complete!")
print("=" * 80)

