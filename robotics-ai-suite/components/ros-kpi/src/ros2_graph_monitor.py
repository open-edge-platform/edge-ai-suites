#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
ROS2 Graph Monitor - Traverse and display ROS2 graph with message timing information.

This script discovers and monitors ROS2 nodes, topics, and their connections,
displaying message frequencies, delta timestamps, and other useful metrics.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
import sys
import os
import time
import argparse
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import re
import threading
import csv
import json
import statistics as stats_module


def _latency_stats(samples) -> dict:
    """Compute latency statistics from a rolling deque of ms samples."""
    if not samples:
        return {}
    n = len(samples)
    mean = stats_module.mean(samples)
    return {
        'samples':    n,
        'min_ms':     min(samples),
        'max_ms':     max(samples),
        'mean_ms':    mean,
        'std_dev_ms': stats_module.stdev(samples) if n > 1 else 0.0,
    }


def categorize_topic(topic_name: str, msg_type: str) -> str:
    """
    Categorize a topic into one of four categories: Sensor, Perception, Motion Planning, or Controls.
    
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


class ROS2GraphMonitor(Node):
    """Monitor ROS2 graph and message statistics."""

    def __init__(self, target_node: Optional[str] = None, show_realtime_delays: bool = True,
                 log_file: Optional[str] = None, topology_file: Optional[str] = None,
                 remote_ip: Optional[str] = None, remote_user: str = 'ubuntu'):
        super().__init__('ros2_graph_monitor')

        # Target node to monitor (None = monitor all)
        self.target_node = target_node
        self.show_realtime_delays = show_realtime_delays
        self.remote_ip = remote_ip
        self.remote_user = remote_user
        self.log_file = log_file
        self.topology_file = topology_file
        self.csv_writer = None
        self.csv_file = None

        # Initialize CSV logging if requested
        if self.log_file:
            self._init_csv_logging()

        # Storage for graph information
        self.topic_stats = defaultdict(lambda: {
            'last_timestamp': None,
            'message_count': 0,
            'delta_samples': deque(maxlen=50),
            'latency_samples': deque(maxlen=1000),
            'publishers': [],
            'subscribers': [],
            'msg_type': None,
            'is_input': False,   # True if target node subscribes to this
            'is_output': False,  # True if target node publishes to this
        })

        # Per-node processing delay tracking (input → output across all nodes)
        self.node_input_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self.node_processing_delays: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        self.node_info = {}
        self.subscribers = {}
        self.lock = threading.Lock()

        # Configure QoS profile for topic discovery
        self.qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=10
        )

        if self.target_node:
            self.get_logger().info(f'ROS2 Graph Monitor initialized - Monitoring node: {self.target_node}')
        else:
            self.get_logger().info('ROS2 Graph Monitor initialized - Monitoring all nodes')

    def discover_graph(self):
        """Discover all nodes, topics, and their connections in the ROS2 graph."""
        # Get all node names
        node_names_and_namespaces = self.get_node_names_and_namespaces()

        # Filter for target node if specified
        if self.target_node:
            node_names_and_namespaces = [
                (name, ns) for name, ns in node_names_and_namespaces
                if f"{ns}/{name}".replace('//', '/') == self.target_node or name == self.target_node
            ]

            if not node_names_and_namespaces:
                self.get_logger().warn(f'Target node "{self.target_node}" not found in graph!')

        with self.lock:
            self.node_info.clear()

            for node_name, namespace in node_names_and_namespaces:
                full_node_name = f"{namespace}/{node_name}".replace('//', '/')

                # Get publishers and subscribers for each node
                topic_names_and_types = self.get_topic_names_and_types()

                publishers = []
                subscribers = []

                for topic_name, topic_types in topic_names_and_types:
                    # Get publishers for this topic
                    pub_info = self.get_publishers_info_by_topic(topic_name)
                    for pub in pub_info:
                        pub_node_name = f"{pub.node_namespace}/{pub.node_name}".replace('//', '/')
                        if pub_node_name == full_node_name:
                            publishers.append((topic_name, topic_types[0] if topic_types else 'unknown'))

                            # Store topic metadata
                            if topic_name not in self.topic_stats:
                                self.topic_stats[topic_name]['msg_type'] = topic_types[0] if topic_types else 'unknown'
                            if full_node_name not in self.topic_stats[topic_name]['publishers']:
                                self.topic_stats[topic_name]['publishers'].append(full_node_name)

                            # Mark as output if this is the target node
                            if self.target_node and full_node_name == self.target_node:
                                self.topic_stats[topic_name]['is_output'] = True

                    # Get subscribers for this topic
                    sub_info = self.get_subscriptions_info_by_topic(topic_name)
                    for sub in sub_info:
                        sub_node_name = f"{sub.node_namespace}/{sub.node_name}".replace('//', '/')
                        if sub_node_name == full_node_name:
                            subscribers.append((topic_name, topic_types[0] if topic_types else 'unknown'))

                            # Store topic metadata
                            if sub_node_name not in self.topic_stats[topic_name]['subscribers']:
                                self.topic_stats[topic_name]['subscribers'].append(sub_node_name)

                            # Mark as input if this is the target node
                            if self.target_node and sub_node_name == self.target_node:
                                self.topic_stats[topic_name]['is_input'] = True

                self.node_info[full_node_name] = {
                    'name': node_name,
                    'namespace': namespace,
                    'publishers': publishers,
                    'subscribers': subscribers
                }

        # If monitoring specific node, only track relevant topics
        if self.target_node:
            self._filter_topics_for_node()

        # ── SSH fallback ────────────────────────────────────────────────────
        # If DDS peer discovery found no user-space nodes but we're monitoring
        # remotely, try SSH to query the graph directly.  This bypasses DDS
        # domain mismatches, multicast filtering, and firewall UDP issues.
        if self.remote_ip:
            _skip = ('ros2_graph_monitor', '_ros2cli_daemon', '_ros2cli_')
            user_nodes = [n for n in self.node_info if not any(s in n for s in _skip)]
            if not user_nodes:
                ssh_nodes = self._discover_via_ssh()
                if ssh_nodes:
                    self.get_logger().info(
                        f'SSH fallback: discovered {len(ssh_nodes)} nodes on {self.remote_ip}')
                    with self.lock:
                        self.node_info.update(ssh_nodes)
                    if self.target_node:
                        self._filter_topics_for_node()

        return self.node_info

    def _discover_via_ssh(self) -> dict:
        """
        Fallback graph discovery via SSH when DDS peer discovery fails.

        Runs ``ros2 node list`` and ``ros2 node info`` on the remote machine
        and synthesises a node_info dict identical to what discover_graph()
        produces.  Also populates self.topic_stats with publisher/subscriber
        lists so the topology JSON is complete.

        Works even when DDS traffic is blocked by firewalls or when the
        ROS_DOMAIN_ID mismatch cannot be resolved at runtime.
        """
        import subprocess as _sp
        node_info: dict = {}
        ssh_base = [
            'ssh', '-T',
            '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=5',
            '-o', 'StrictHostKeyChecking=no',
            f'{self.remote_user}@{self.remote_ip}',
        ]
        ros_env = (
            # Read domain ID without sourcing .bashrc (interactive guard bypasses exports)
            'D=$(grep -hE "^export ROS_DOMAIN_ID=" ~/.bashrc ~/.bash_profile ~/.profile '
            '/etc/environment 2>/dev/null | tail -1 | cut -d= -f2); '
            'export ROS_DOMAIN_ID=${D:-0}; '
            'source /opt/ros/$(ls /opt/ros/ 2>/dev/null | head -1)/setup.bash '
            '2>/dev/null; '
        )

        def _ssh(cmd: str, timeout: int = 15) -> str:
            try:
                r = _sp.run(ssh_base + [ros_env + cmd],
                            capture_output=True, text=True,
                            timeout=timeout, stdin=_sp.DEVNULL)
                return r.stdout
            except Exception:
                return ''

        # ── node list ────────────────────────────────────────────────────────
        nodes_raw = _ssh('ros2 node list 2>/dev/null')
        nodes = [n.strip() for n in nodes_raw.splitlines()
                 if n.strip() and '/_' not in n]
        if not nodes:
            return node_info

        # ── topic list with types ─────────────────────────────────────────────
        topic_raw = _ssh('ros2 topic list -t 2>/dev/null')
        topic_types: Dict[str, str] = {}
        for line in topic_raw.splitlines():
            m = re.match(r'(/\S+)\s+\[([^\]]+)\]', line.strip())
            if m:
                topic_types[m.group(1)] = m.group(2)

        # ── per-node info ─────────────────────────────────────────────────────
        for node in nodes[:40]:  # cap to avoid long SSH chains
            info_raw = _ssh(f'ros2 node info {node} 2>/dev/null')
            publishers: List[Tuple[str, str]]  = []
            subscribers: List[Tuple[str, str]] = []
            section = None
            for line in info_raw.splitlines():
                ls = line.strip()
                if ls == 'Publishers:':
                    section = 'pub'
                elif ls == 'Subscribers:':
                    section = 'sub'
                elif ls.startswith(('Service ', 'Action ', 'Clients')):
                    section = None
                elif section and ls.startswith('/') and ':' in ls:
                    parts = ls.split(':', 1)
                    topic    = parts[0].strip()
                    msg_type = parts[1].strip() if len(parts) > 1 else \
                               topic_types.get(topic, 'unknown')
                    if not msg_type:
                        msg_type = topic_types.get(topic, 'unknown')
                    if section == 'pub':
                        publishers.append((topic, msg_type))
                    else:
                        subscribers.append((topic, msg_type))

            node_info[node] = {
                'name':        node.lstrip('/'),
                'namespace':   '/',
                'publishers':  publishers,
                'subscribers': subscribers,
            }

            # Seed topic_stats so subscriptions and topology JSON are populated
            with self.lock:
                for topic, msg_type in publishers:
                    self.topic_stats[topic]['msg_type'] = msg_type
                    if node not in self.topic_stats[topic]['publishers']:
                        self.topic_stats[topic]['publishers'].append(node)
                for topic, msg_type in subscribers:
                    self.topic_stats[topic]['msg_type'] = msg_type
                    if node not in self.topic_stats[topic]['subscribers']:
                        self.topic_stats[topic]['subscribers'].append(node)

        return node_info

    def _filter_topics_for_node(self):
        """Filter topic_stats to only include topics relevant to target node."""
        if not self.target_node or not self.node_info:
            return

        relevant_topics = set()
        for node_name, info in self.node_info.items():
            for topic, _ in info['publishers']:
                relevant_topics.add(topic)
            for topic, _ in info['subscribers']:
                relevant_topics.add(topic)

        # Remove topics not relevant to target node
        topics_to_remove = [t for t in self.topic_stats.keys() if t not in relevant_topics]
        for topic in topics_to_remove:
            del self.topic_stats[topic]

    def _init_csv_logging(self):
        """Initialize CSV logging."""
        try:
            self.csv_file = open(self.log_file, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)

            # Write header
            self.csv_writer.writerow([
                'timestamp',
                'wall_time',
                'topic_name',
                'msg_type',
                'is_input',
                'is_output',
                'message_count',
                'delta_time_ms',
                'frequency_hz',
                'processing_delay_ms',
                'latency_min_ms',
                'latency_max_ms',
                'latency_mean_ms',
                'latency_std_dev_ms'
            ])
            self.csv_file.flush()
            self.get_logger().info(f'Logging to CSV file: {self.log_file}')
        except Exception as e:
            self.get_logger().error(f'Failed to initialize CSV logging: {e}')
            self.csv_writer = None
            self.csv_file = None

    def _log_message(self, topic_name: str, current_time: float, delta: Optional[float], processing_delay: Optional[float]):
        """Log a message event to CSV file."""
        if not self.csv_writer:
            return

        try:
            stats = self.topic_stats[topic_name]
            frequency = 1.0 / delta if delta and delta > 0 else None
            
            # Get latency statistics
            lat_stats = _latency_stats(stats['latency_samples'])

            self.csv_writer.writerow([
                current_time,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                topic_name,
                stats['msg_type'],
                stats['is_input'],
                stats['is_output'],
                stats['message_count'],
                delta * 1000 if delta else None,
                frequency,
                processing_delay * 1000 if processing_delay else None,
                lat_stats.get('min_ms'),
                lat_stats.get('max_ms'),
                lat_stats.get('mean_ms'),
                lat_stats.get('std_dev_ms')
            ])
            self.csv_file.flush()
        except Exception as e:
            self.get_logger().error(f'Failed to log message: {e}')

    def close_log(self):
        """Close the CSV log file."""
        if self.csv_file:
            self.csv_file.close()
            self.get_logger().info('CSV log file closed')

    def write_topology_json(self):
        """Export the current node-topic topology to a JSON file for visualize_graph.py.

        The JSON captures every discovered node and topic with their publisher/subscriber
        node-name lists plus the latest KPI metrics.  This gives visualize_graph.py the
        full Node -> Topic -> Node edge set needed for a proper rqt_graph-style view.
        """
        if not self.topology_file:
            return
        try:
            with self.lock:
                topology: Dict[str, Any] = {
                    'generated': datetime.now().isoformat(),
                    'target_node': self.target_node,
                    'nodes': {},
                    'topics': {},
                }

                # ── Node entries ────────────────────────────────────────────
                for node_name, info in self.node_info.items():
                    nd = _latency_stats(self.node_processing_delays[node_name])
                    topology['nodes'][node_name] = {
                        'publishes':  [t for t, _ in info.get('publishers',  [])],
                        'subscribes': [t for t, _ in info.get('subscribers', [])],
                        'proc_delay_mean_ms':    nd.get('mean_ms'),
                        'proc_delay_std_dev_ms': nd.get('std_dev_ms'),
                        'proc_delay_samples':    nd.get('samples', 0),
                    }

                # ── Topic entries with metrics ───────────────────────────────
                for topic_name, data in self.topic_stats.items():
                    avg_delta = (sum(data['delta_samples']) / len(data['delta_samples'])
                                 if data['delta_samples'] else None)
                    freq = (1.0 / avg_delta) if avg_delta else None
                    lat_stats = _latency_stats(data['latency_samples'])

                    topology['topics'][topic_name] = {
                        'msg_type':       data['msg_type'],
                        'publishers':     list(data['publishers']),
                        'subscribers':    list(data['subscribers']),
                        'msg_count':      data['message_count'],
                        'avg_freq_hz':    freq,
                        'avg_delta_ms':   avg_delta * 1000 if avg_delta else None,
                        'is_input':       data['is_input'],
                        'is_output':      data['is_output'],
                        'latency_min_ms':    lat_stats.get('min_ms'),
                        'latency_max_ms':    lat_stats.get('max_ms'),
                        'latency_mean_ms':   lat_stats.get('mean_ms'),
                        'latency_std_dev_ms': lat_stats.get('std_dev_ms'),
                    }

            with open(self.topology_file, 'w') as fh:
                json.dump(topology, fh, indent=2, default=str)
        except Exception as exc:
            self.get_logger().error(f'Failed to write topology JSON: {exc}')

    def subscribe_to_topic(self, topic_name: str, msg_type_str: str):
        """Dynamically subscribe to a topic to monitor messages."""
        if topic_name in self.subscribers:
            return  # Already subscribed

        try:
            # Import the message type dynamically
            msg_type = self._get_msg_type(msg_type_str)
            if msg_type is None:
                # Only log warning for non-action feedback messages
                # Action feedback messages require special handling and aren't standard msg types
                if not msg_type_str.endswith('_FeedbackMessage') and 'action/' not in msg_type_str:
                    self.get_logger().warn(f"Could not load message type: {msg_type_str}")
                return

            # Create callback for this topic
            def callback(msg):
                current_time = time.time()

                # Try to extract message ID from header (if available)
                msg_id = None
                try:
                    if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
                        # Use ROS2 timestamp as message ID
                        msg_id = (msg.header.stamp.sec, msg.header.stamp.nanosec)
                except Exception:
                    pass  # No header or stamp field available

                with self.lock:
                    stats = self.topic_stats[topic_name]

                    # Calculate delta time
                    delta = None
                    if stats['last_timestamp'] is not None:
                        delta = current_time - stats['last_timestamp']
                        stats['delta_samples'].append(delta)

                    stats['last_timestamp'] = current_time
                    stats['message_count'] += 1

                    # Log to CSV if enabled
                    processing_delay = None

                    # Per-node processing delay – runs for every node, no --node flag needed.
                    # Step 1: compute output delay for each publisher of this topic BEFORE
                    #         recording new input timestamps (avoids self-loop skew).
                    for pub_node in stats['publishers']:
                        if self.node_input_times[pub_node]:
                            delay = current_time - max(self.node_input_times[pub_node])
                            if 0.0 < delay < 10.0:   # sanity: ignore gaps > 10 s
                                delay_ms = delay * 1000
                                self.node_processing_delays[pub_node].append(delay_ms)
                                stats['latency_samples'].append(delay_ms)
                                processing_delay = delay
                                if self.show_realtime_delays:
                                    ts = datetime.now().strftime('%H:%M:%S.%f')
                                    lat = _latency_stats(self.node_processing_delays[pub_node])
                                    print(f"[{ts}] {pub_node} → {topic_name}: "
                                          f"proc delay = {delay_ms:.3f} ms "
                                          f"(mean={lat.get('mean_ms', 0):.3f} ms)")

                    # Step 2: record this message as an input event for all subscriber nodes.
                    for sub_node in stats['subscribers']:
                        self.node_input_times[sub_node].append(current_time)

                    # Log message to CSV
                    self._log_message(topic_name, current_time, delta, processing_delay)

            # Create subscription
            subscription = self.create_subscription(
                msg_type,
                topic_name,
                callback,
                self.qos_profile
            )

            self.subscribers[topic_name] = subscription
            self.get_logger().info(f"Subscribed to topic: {topic_name}")

        except Exception as e:
            self.get_logger().error(f"Failed to subscribe to {topic_name}: {str(e)}")

    def _get_msg_type(self, msg_type_str: str):
        """Import and return the message type class from a string."""
        try:
            parts = msg_type_str.split('/')
            if len(parts) != 3:
                return None

            package, subfolder, msg_name = parts

            # Try to import the message type
            if subfolder == 'msg':
                module = __import__(f'{package}.msg', fromlist=[msg_name])
            elif subfolder == 'srv':
                module = __import__(f'{package}.srv', fromlist=[msg_name])
            elif subfolder == 'action':
                # Action messages require special handling
                # Action feedback messages are generated types, not directly importable
                if msg_name.endswith('_FeedbackMessage'):
                    return None  # Skip action feedback messages
                module = __import__(f'{package}.action', fromlist=[msg_name])
            else:
                return None

            return getattr(module, msg_name)
        except (ImportError, AttributeError) as e:
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics for all monitored topics."""
        with self.lock:
            stats = {}
            for topic_name, data in self.topic_stats.items():
                avg_delta = None
                frequency = None

                if data['delta_samples']:
                    avg_delta = sum(data['delta_samples']) / len(data['delta_samples'])
                    frequency = 1.0 / avg_delta if avg_delta > 0 else 0

                # Get latency statistics
                lat_stats = _latency_stats(data['latency_samples'])

                stats[topic_name] = {
                    'msg_type': data['msg_type'],
                    'message_count': data['message_count'],
                    'avg_delta_ms': avg_delta * 1000 if avg_delta else None,
                    'frequency_hz': frequency,
                    'publishers': data['publishers'],
                    'subscribers': data['subscribers'],
                    'last_seen': data['last_timestamp'],
                    'is_input': data['is_input'],
                    'is_output': data['is_output'],
                    'latency_min_ms': lat_stats.get('min_ms'),
                    'latency_max_ms': lat_stats.get('max_ms'),
                    'latency_mean_ms': lat_stats.get('mean_ms'),
                    'latency_std_dev_ms': lat_stats.get('std_dev_ms'),
                    'latency_samples':    lat_stats.get('samples', 0),
                }

            # Per-node processing delay statistics
            node_proc_delays = {
                node: _latency_stats(delays)
                for node, delays in self.node_processing_delays.items()
                if delays
            }

            return {
                'topics': stats,
                'node_proc_delays': node_proc_delays,
            }

    def get_node_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Calculate average latency and frequency for each node based on their published topics."""
        with self.lock:
            node_stats = {}

            # Iterate through all nodes
            for node_name, info in self.node_info.items():
                # Collect statistics from all topics published by this node
                pub_frequencies = []
                pub_latencies = []
                pub_message_counts = []

                # Collect statistics from all topics subscribed by this node
                sub_frequencies = []
                sub_latencies = []
                sub_message_counts = []

                # Check published topics
                for topic, _ in info['publishers']:
                    if topic in self.topic_stats:
                        data = self.topic_stats[topic]
                        if data['delta_samples']:
                            avg_delta = sum(data['delta_samples']) / len(data['delta_samples'])
                            frequency = 1.0 / avg_delta if avg_delta > 0 else 0
                            pub_latencies.append(avg_delta * 1000)  # Convert to ms
                            pub_frequencies.append(frequency)
                        pub_message_counts.append(data['message_count'])

                # Check subscribed topics
                for topic, _ in info['subscribers']:
                    if topic in self.topic_stats:
                        data = self.topic_stats[topic]
                        if data['delta_samples']:
                            avg_delta = sum(data['delta_samples']) / len(data['delta_samples'])
                            frequency = 1.0 / avg_delta if avg_delta > 0 else 0
                            sub_latencies.append(avg_delta * 1000)  # Convert to ms
                            sub_frequencies.append(frequency)
                        sub_message_counts.append(data['message_count'])

                # Calculate averages for this node
                node_stats[node_name] = {
                    'published_topics': len(info['publishers']),
                    'subscribed_topics': len(info['subscribers']),
                    'avg_pub_frequency_hz': sum(pub_frequencies) / len(pub_frequencies) if pub_frequencies else None,
                    'avg_pub_latency_ms': sum(pub_latencies) / len(pub_latencies) if pub_latencies else None,
                    'total_pub_messages': sum(pub_message_counts) if pub_message_counts else 0,
                    'avg_sub_frequency_hz': sum(sub_frequencies) / len(sub_frequencies) if sub_frequencies else None,
                    'avg_sub_latency_ms': sum(sub_latencies) / len(sub_latencies) if sub_latencies else None,
                    'total_sub_messages': sum(sub_message_counts) if sub_message_counts else 0,
                }

            return node_stats


def categorize_node(node_name: str, node_info: Dict) -> str:
    """
    Categorize a node based on its name and topics it publishes/subscribes to.
    
    Args:
        node_name: The name of the node
        node_info: Dictionary containing 'publishers' and 'subscribers' lists
        
    Returns:
        One of: 'Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other'
    """
    node_lower = node_name.lower()
    
    # Get all topics this node interacts with
    all_topics = []
    if 'publishers' in node_info:
        all_topics.extend([topic for topic, _ in node_info['publishers']])
    if 'subscribers' in node_info:
        all_topics.extend([topic for topic, _ in node_info['subscribers']])
    
    # Node name patterns for each category
    sensor_node_patterns = ['camera', 'lidar', 'laser', 'imu', 'gps', 'gnss', 'scan', 
                           'sensor', 'depth', 'range', 'ultrasonic', 'sonar']
    perception_node_patterns = ['map', 'costmap', 'slam', 'rtabmap', 'detection', 
                               'tracking', 'semantic', 'localization', 'amcl']
    planning_node_patterns = ['planner', 'planning', 'path', 'route', 'navigate', 
                             'behavior', 'bt_navigator', 'waypoint']
    control_node_patterns = ['controller', 'control', 'cmd', 'velocity', 'motor', 
                            'actuator', 'drive', 'steering']
    
    # Check node name first
    if any(pattern in node_lower for pattern in sensor_node_patterns):
        return 'Sensor'
    if any(pattern in node_lower for pattern in perception_node_patterns):
        return 'Perception'
    if any(pattern in node_lower for pattern in planning_node_patterns):
        return 'Motion Planning'
    if any(pattern in node_lower for pattern in control_node_patterns):
        return 'Controls'
    
    # Check topics if node name doesn't match
    category_votes = {'Sensor': 0, 'Perception': 0, 'Motion Planning': 0, 'Controls': 0}
    for topic in all_topics:
        topic_category = categorize_topic(topic, '')
        if topic_category in category_votes:
            category_votes[topic_category] += 1
    
    # Return category with most votes, or 'Other' if no clear winner
    max_votes = max(category_votes.values())
    if max_votes > 0:
        for category, votes in category_votes.items():
            if votes == max_votes:
                return category
    
    return 'Other'


def print_node_statistics(node_stats: Dict[str, Dict[str, Any]], node_info: Dict):
    """Print average latency and frequency for each node."""
    print(f"\n{'NODE STATISTICS (Average Latency & Frequency)':-^80}")
    print(f"Total Nodes: {len(node_stats)}\n")

    print(f"{'Node Name':<32} {'Category':<16} {'Pub Freq':<10} {'Pub Lat':<10} {'Sub Freq':<10} {'Sub Lat':<10}")
    print(f"{'':32} {'':16} {'(Hz)':<10} {'(ms)':<10} {'(Hz)':<10} {'(ms)':<10}")
    print("-" * 88)

    for node_name, stats in sorted(node_stats.items()):
        # Truncate node name if too long
        node_display = node_name if len(node_name) <= 30 else node_name[:27] + "..."
        
        # Get node category
        category = categorize_node(node_name, node_info.get(node_name, {}))
        category_icons = {
            'Sensor': '📡 Sensor',
            'Perception': '🧠 Perception',
            'Motion Planning': '🗺️ Planning',
            'Controls': '🎮 Controls',
            'Other': '📋 Other'
        }
        category_display = category_icons.get(category, category)
        if len(category_display) > 14:
            category_display = category_display[:11] + "..."

        pub_freq = f"{stats['avg_pub_frequency_hz']:.2f}" if stats['avg_pub_frequency_hz'] else "N/A"
        pub_lat = f"{stats['avg_pub_latency_ms']:.2f}" if stats['avg_pub_latency_ms'] else "N/A"
        sub_freq = f"{stats['avg_sub_frequency_hz']:.2f}" if stats['avg_sub_frequency_hz'] else "N/A"
        sub_lat = f"{stats['avg_sub_latency_ms']:.2f}" if stats['avg_sub_latency_ms'] else "N/A"

        print(f"{node_display:<32} {category_display:<16} {pub_freq:<10} {pub_lat:<10} {sub_freq:<10} {sub_lat:<10}")

    print("\n")


def print_graph_info(node_info: Dict, stats_data: Dict, target_node: Optional[str] = None,
                     show_processing: bool = True, show_nodes: bool = True,
                     show_topics: bool = True, show_io_details: bool = True,
                     show_connections: bool = True, show_node_stats: bool = True):
    """Print formatted graph information."""
    # Extract topic stats (handle both old and new format)
    if 'topics' in stats_data:
        topic_stats = stats_data['topics']
    else:
        topic_stats = stats_data
    
    # Skip printing if there's no meaningful data (only monitor node exists)
    if not node_info and not topic_stats:
        return
    
    # Check if only the monitor node exists
    if len(node_info) <= 1 and all('ros2_graph_monitor' in name for name in node_info.keys()):
        return
    
    print("\n" + "="*80)
    if target_node:
        print(f"ROS2 NODE MONITOR: {target_node} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"ROS2 GRAPH ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Print processing delay summary (per-node, all nodes)
    if show_processing and stats_data.get('node_proc_delays'):
        print(f"\n{'PROCESSING DELAY ANALYSIS (input → output per node)':-^80}")
        for nname, nd in sorted(stats_data['node_proc_delays'].items()):
            mean = nd.get('mean_ms')
            std  = nd.get('std_dev_ms')
            n    = nd.get('samples', 0)
            if mean is not None:
                std_str = f' ± {std:.3f}' if std is not None else ''
                print(f"  {nname:<45} {mean:.3f}{std_str} ms  (n={n})")
        print()

    # Print node statistics first (average latency and frequency per node)
    if show_node_stats and 'node_stats' in stats_data:
        print_node_statistics(stats_data['node_stats'], node_info)

    # Print nodes
    if show_nodes:
        print(f"\n{'NODE INFORMATION':-^80}")
        print(f"Total Nodes: {len(node_info)}\n")

        for node_name, info in sorted(node_info.items()):
            print(f"📦 {node_name}")

            if info['publishers']:
                print(f"  Publishers ({len(info['publishers'])})")
                for topic, msg_type in sorted(info['publishers']):
                    print(f"    → {topic} [{msg_type.split('/')[-1]}]")

            if info['subscribers']:
                print(f"  Subscribers ({len(info['subscribers'])})")
                for topic, msg_type in sorted(info['subscribers']):
                    print(f"    ← {topic} [{msg_type.split('/')[-1]}]")

            print()

    # Print topic statistics
    if show_topics:
        print(f"{'TOPIC STATISTICS':-^80}")
        print(f"Total Topics: {len(topic_stats)}\n")

        # Categorize topics
        categorized_topics = {
            'Sensor': [],
            'Perception': [],
            'Motion Planning': [],
            'Controls': [],
            'Other': []
        }
        
        for topic_name, stats in topic_stats.items():
            category = categorize_topic(topic_name, stats['msg_type'])
            categorized_topics[category].append((topic_name, stats))
        
        # Display topics by category
        for category in ['Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other']:
            topics = categorized_topics[category]
            if not topics:
                continue
                
            # Category header with icon
            category_icons = {
                'Sensor': '📡',
                'Perception': '🧠',
                'Motion Planning': '🗺️',
                'Controls': '🎮',
                'Other': '📋'
            }
            icon = category_icons.get(category, '📋')
            print(f"\n{icon} {category.upper()} ({len(topics)} topics)")
            
            if target_node:
                print(f"{'Topic':<38} {'I/O':<4} {'Msg Type':<20} {'Freq (Hz)':<12} {'Delta (ms)':<12}")
            else:
                print(f"{'Topic':<40} {'Msg Type':<25} {'Freq (Hz)':<12} {'Delta (ms)':<12} {'Count':<10}")
            print("-" * 80)

            for topic_name, stats in sorted(topics):
                msg_type_short = stats['msg_type'].split('/')[-1] if stats['msg_type'] else 'unknown'
                freq = f"{stats['frequency_hz']:.2f}" if stats['frequency_hz'] else "N/A"
                delta = f"{stats['avg_delta_ms']:.2f}" if stats['avg_delta_ms'] else "N/A"
                count = stats['message_count']

                if target_node:
                    # Show input/output indicator
                    io_indicator = ""
                    if stats.get('is_input') and stats.get('is_output'):
                        io_indicator = "I/O"
                    elif stats.get('is_input'):
                        io_indicator = "IN"
                    elif stats.get('is_output'):
                        io_indicator = "OUT"

                    # Truncate topic name if too long
                    topic_display = topic_name if len(topic_name) <= 36 else topic_name[:33] + "..."
                    msg_type_display = msg_type_short if len(msg_type_short) <= 18 else msg_type_short[:15] + "..."

                    print(f"{topic_display:<38} {io_indicator:<4} {msg_type_display:<20} {freq:<12} {delta:<12}")
                else:
                    # Truncate topic name if too long
                    topic_display = topic_name if len(topic_name) <= 38 else topic_name[:35] + "..."

                    print(f"{topic_display:<40} {msg_type_short:<25} {freq:<12} {delta:<12} {count:<10}")

        print()
    # Print detailed input/output timing for target node
    if show_io_details and target_node:
        print(f"{'INPUT/OUTPUT TIMING DETAILS':-^80}")

        input_topics = [(name, stats) for name, stats in sorted(topic_stats.items()) if stats.get('is_input')]
        output_topics = [(name, stats) for name, stats in sorted(topic_stats.items()) if stats.get('is_output')]

        if input_topics:
            # Categorize input topics
            input_categorized = defaultdict(list)
            for topic_name, stats in input_topics:
                category = categorize_topic(topic_name, stats['msg_type'])
                input_categorized[category].append((topic_name, stats))
            
            print("\n📥 INPUT TOPICS (Subscribed by target node):")
            for category in ['Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other']:
                if category not in input_categorized:
                    continue
                    
                category_icons = {
                    'Sensor': '📡',
                    'Perception': '🧠',
                    'Motion Planning': '🗺️',
                    'Controls': '🎮',
                    'Other': '📋'
                }
                icon = category_icons.get(category, '📋')
                print(f"\n  {icon} {category}:")
                
                for topic_name, stats in input_categorized[category]:
                    print(f"    {topic_name}")
                    print(f"       Type: {stats['msg_type']}")
                    if stats['frequency_hz']:
                        print(f"       Frequency: {stats['frequency_hz']:.2f} Hz")
                        print(f"       Avg Delta: {stats['avg_delta_ms']:.2f} ms")
                    print(f"       Messages: {stats['message_count']}")
                    if stats['publishers']:
                        print(f"       Published by: {', '.join(stats['publishers'])}")

        if output_topics:
            # Categorize output topics
            output_categorized = defaultdict(list)
            for topic_name, stats in output_topics:
                category = categorize_topic(topic_name, stats['msg_type'])
                output_categorized[category].append((topic_name, stats))
            
            print("\n📤 OUTPUT TOPICS (Published by target node):")
            for category in ['Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other']:
                if category not in output_categorized:
                    continue
                    
                category_icons = {
                    'Sensor': '📡',
                    'Perception': '🧠',
                    'Motion Planning': '🗺️',
                    'Controls': '🎮',
                    'Other': '📋'
                }
                icon = category_icons.get(category, '📋')
                print(f"\n  {icon} {category}:")
                
                for topic_name, stats in output_categorized[category]:
                    print(f"    {topic_name}")
                    print(f"       Type: {stats['msg_type']}")
                    if stats['frequency_hz']:
                        print(f"       Frequency: {stats['frequency_hz']:.2f} Hz")
                        print(f"       Avg Delta: {stats['avg_delta_ms']:.2f} ms")
                    print(f"       Messages: {stats['message_count']}")
                    if stats['subscribers']:
                        other_subs = [s for s in stats['subscribers'] if s != target_node]
                        if other_subs:
                            print(f"       Subscribed by: {', '.join(other_subs)}")

        node_delays = stats_data.get('node_proc_delays', {})
        if input_topics and output_topics and node_delays:
            avg_all = [nd['mean_ms'] for nd in node_delays.values() if nd.get('mean_ms') is not None]
            if avg_all:
                overall = sum(avg_all) / len(avg_all)
                print(f"\n⏱️  PROCESSING: {overall:.2f} ms avg delay across {len(avg_all)} nodes (input → output)")

        print()

    # Print connections
    if show_connections:
        print(f"{'TOPIC CONNECTIONS':-^80}")
        
        # Categorize topics with connections
        categorized_connections = {
            'Sensor': [],
            'Perception': [],
            'Motion Planning': [],
            'Controls': [],
            'Other': []
        }
        
        for topic_name, stats in topic_stats.items():
            if stats['publishers'] or stats['subscribers']:
                category = categorize_topic(topic_name, stats['msg_type'])
                categorized_connections[category].append((topic_name, stats))
        
        # Display connections by category
        for category in ['Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other']:
            topics = categorized_connections[category]
            if not topics:
                continue
            
            # Category header with icon
            category_icons = {
                'Sensor': '📡',
                'Perception': '🧠',
                'Motion Planning': '🗺️',
                'Controls': '🎮',
                'Other': '📋'
            }
            icon = category_icons.get(category, '📋')
            print(f"\n{icon} {category.upper()}")
            print("-" * 80)
            
            for topic_name, stats in sorted(topics):
                print(f"\n📡 {topic_name}")
                print(f"   Type: {stats['msg_type']}")

                if stats['publishers']:
                    print(f"   Publishers: {', '.join(stats['publishers'])}")

                if stats['subscribers']:
                    print(f"   Subscribers: {', '.join(stats['subscribers'])}")

                if stats['frequency_hz']:
                    print(f"   Frequency: {stats['frequency_hz']:.2f} Hz")
                    print(f"   Avg Delta: {stats['avg_delta_ms']:.2f} ms")
                    print(f"   Message Count: {stats['message_count']}")

        print("\n" + "="*80 + "\n")

def main():
    """Main function to run the ROS2 graph monitor."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Monitor ROS2 graph and display node/topic statistics with timing information.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor all nodes and topics
  %(prog)s

  # Monitor a specific node
  %(prog)s --node /rtabmap
  %(prog)s -n /wandering

  # Set custom update interval
  %(prog)s --node /controller_server --interval 2
        """
    )
    parser.add_argument(
        '-n', '--node',
        type=str,
        help='Specific node name to monitor (e.g., /rtabmap, /wandering). If not provided, monitors all nodes.'
    )
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=5.0,
        help='Update interval in seconds (default: 5.0)'
    )
    parser.add_argument(
        '--show-processing',
        action='store_true',
        help='Show processing delay analysis (for target node)'
    )
    parser.add_argument(
        '--show-node-stats',
        action='store_true',
        help='Show average latency and frequency per node'
    )
    parser.add_argument(
        '--show-nodes',
        action='store_true',
        help='Show node information section'
    )
    parser.add_argument(
        '--show-topics',
        action='store_true',
        help='Show topic statistics table'
    )
    parser.add_argument(
        '--show-io-details',
        action='store_true',
        help='Show detailed input/output timing (for target node)'
    )
    parser.add_argument(
        '--show-connections',
        action='store_true',
        help='Show topic connections section'
    )
    parser.add_argument(
        '--realtime-delays',
        action='store_true',
        default=True,
        help='Display real-time processing delay for each output message (enabled by default, use --no-realtime-delays to disable)'
    )
    parser.add_argument(
        '--no-realtime-delays',
        dest='realtime_delays',
        action='store_false',
        help='Disable real-time processing delay display'
    )
    parser.add_argument(
        '--log',
        type=str,
        default=None,
        help='Path to CSV log file for timing data (will be created/overwritten)'
    )
    parser.add_argument(
        '--topology',
        type=str,
        default=None,
        help='Path to JSON file for node-topic topology export (used by visualize_graph.py '
             'to produce a true rqt_graph-style directed-graph view). Updated every interval.'
    )
    parser.add_argument(
        '--remote-ip',
        type=str,
        default=None,
        help='IP address of the remote system running the ROS2 pipeline. '
             'Configures DDS peer discovery so this monitor can observe a '
             'ROS2 graph on another machine (requires matching ROS_DOMAIN_ID).'
    )
    parser.add_argument(
        '--remote-user',
        type=str,
        default='ubuntu',
        help='SSH username for the remote system (default: ubuntu). '
             'Used for SSH-based graph discovery fallback.'
    )
    parser.add_argument(
        '--no-countdown',
        action='store_true',
        default=False,
        help='Skip the 5-second startup countdown (used when launched '
             'programmatically by monitor_stack.py).'
    )

    args = parser.parse_args()

    # If no specific sections selected, show all
    show_all = not any([
        args.show_processing,
        args.show_node_stats,
        args.show_nodes,
        args.show_topics,
        args.show_io_details,
        args.show_connections
    ])

    if show_all:
        args.show_processing = True
        args.show_node_stats = True
        args.show_nodes = True
        args.show_topics = True
        args.show_io_details = True
        args.show_connections = True

    if args.node:
        print(f"Starting ROS2 Graph Monitor for node: {args.node}...")
    else:
        print("Starting ROS2 Graph Monitor for all nodes...")

    # Configure DDS peer discovery for remote system if requested
    if args.remote_ip:
        print(f"Configuring DDS discovery for remote host: {args.remote_ip}")
        # Auto-detect remote ROS_DOMAIN_ID and align locally when run standalone
        if not args.no_countdown:  # standalone mode (not spawned by monitor_stack)
            try:
                import subprocess as _sp2
                r = _sp2.run(
                    ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                     '-o', 'StrictHostKeyChecking=no',
                     f'{args.remote_user}@{args.remote_ip}', 'echo "${ROS_DOMAIN_ID:-0}"'],
                    capture_output=True, text=True, timeout=10, stdin=_sp2.DEVNULL)
                remote_domain = r.stdout.strip()
                local_domain  = os.environ.get('ROS_DOMAIN_ID', '0')
                if remote_domain.isdigit() and remote_domain != local_domain:
                    print(f"  ⚠  ROS_DOMAIN_ID mismatch: local={local_domain}, remote={remote_domain}")
                    print(f"     Setting ROS_DOMAIN_ID={remote_domain} to match remote.")
                    os.environ['ROS_DOMAIN_ID'] = remote_domain
                else:
                    print(f"  ✅ ROS_DOMAIN_ID={os.environ.get('ROS_DOMAIN_ID','0')} matches.")
            except Exception:
                pass
        os.environ['ROS_LOCALHOST_ONLY'] = '0'
        # CycloneDDS: disable multicast, force unicast to the specified peer
        cyclone_uri = (
            '<CycloneDDS><Domain>'
            '<General><AllowMulticast>false</AllowMulticast></General>'
            '<Discovery><Peers>'
            f'<Peer address="{args.remote_ip}"/>'
            '</Peers></Discovery>'
            '</Domain></CycloneDDS>'
        )
        os.environ['CYCLONEDDS_URI'] = cyclone_uri
        # FastDDS / rmw_fastrtps unicast peer (always override)
        os.environ['ROS_STATIC_PEERS'] = args.remote_ip
        print(f"  ROS_LOCALHOST_ONLY=0")
        print(f"  CYCLONEDDS_URI set with peer {args.remote_ip} (multicast disabled)")
        print(f"  ROS_STATIC_PEERS={args.remote_ip}")

    # Countdown to give user time to start ROS2 launch
    if args.no_countdown:
        print("Starting monitor!\n")
    else:
        print("\nStarting in...")
        for i in range(5, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        print("Starting monitor!\n")

    rclpy.init()

    try:
        monitor = ROS2GraphMonitor(target_node=args.node, show_realtime_delays=args.realtime_delays,
                                    log_file=args.log, topology_file=args.topology,
                                    remote_ip=args.remote_ip, remote_user=args.remote_user)

        # Initial discovery with retry for target node
        node_info = None
        if args.node:
            print(f"Waiting for node: {args.node}...")
            retry_count = 0
            while not node_info and rclpy.ok():
                node_info = monitor.discover_graph()

                if not node_info:
                    if retry_count == 0:
                        print(f"Node '{args.node}' not found. Retrying every second...")
                        print("Available nodes:")
                        all_nodes = monitor.get_node_names_and_namespaces()
                        # Filter out the monitor itself
                        other_nodes = [(name, ns) for name, ns in all_nodes if name != 'ros2_graph_monitor']

                        if not other_nodes:
                            print("  (No ROS2 processes found!)")
                            print("\nNo ROS2 processes are running.")
                            print("Start your ROS2 launch file first, then run this monitor.")
                            print("\nExiting...")
                            return

                        for name, ns in sorted(other_nodes):
                            full_name = f"{ns}/{name}".replace('//', '/')
                            print(f"  {full_name}")
                        print("\nWaiting for target node to appear...")
                    else:
                        print(f"Retry {retry_count}: Node '{args.node}' not found yet...", end='\r')

                        # Exit after 30 retries (30 seconds)
                        if retry_count >= 30:
                            print()  # New line
                            print(f"\nTimeout: Node '{args.node}' did not appear after 30 seconds.")
                            print("Exiting...")
                            return

                    retry_count += 1
                    time.sleep(1.0)
                else:
                    if retry_count > 0:
                        print()  # New line after retry messages
                    print(f"✓ Node '{args.node}' found!")
        else:
            print("Discovering ROS2 graph...")
            node_info = monitor.discover_graph()

            # Check if any nodes were found
            all_nodes = monitor.get_node_names_and_namespaces()
            # Filter out the monitor itself
            other_nodes = [n for n in all_nodes if n[0] != 'ros2_graph_monitor']

            if not other_nodes:
                print("\nNo ROS2 nodes found yet. Will continue monitoring...")
                print("The monitor will detect nodes as they start up.")

        # Subscribe to all discovered topics for monitoring
        print("Setting up topic subscriptions...")
        for topic_name, stats in monitor.topic_stats.items():
            if stats['msg_type']:
                monitor.subscribe_to_topic(topic_name, stats['msg_type'])

        # Write initial topology snapshot
        monitor.write_topology_json()

        print(f"Monitoring {len(monitor.subscribers)} topics. Collecting data...")
        print("Press Ctrl+C to stop and display results.\n")

        # Monitoring loop
        update_interval = args.interval
        last_update = time.time()

        try:
            while rclpy.ok():
                rclpy.spin_once(monitor, timeout_sec=0.1)

                # Periodically update display
                current_time = time.time()
                if current_time - last_update >= update_interval:
                    # Re-discover graph (in case new nodes/topics appeared)
                    monitor.discover_graph()
                    monitor.write_topology_json()

                    # Subscribe to any new topics
                    for topic_name, stats in monitor.topic_stats.items():
                        if stats['msg_type'] and topic_name not in monitor.subscribers:
                            monitor.subscribe_to_topic(topic_name, stats['msg_type'])

                    # Display statistics
                    stats_data = monitor.get_statistics()
                    # Add node statistics
                    stats_data['node_stats'] = monitor.get_node_statistics()
                    
                    # Check if we have any real data
                    all_nodes = monitor.get_node_names_and_namespaces()
                    other_nodes = [n for n in all_nodes if n[0] != 'ros2_graph_monitor']
                    
                    if other_nodes or len(stats_data.get('topics', {})) > 0:
                        print_graph_info(node_info, stats_data, args.node,
                                       show_processing=args.show_processing,
                                       show_node_stats=args.show_node_stats,
                                       show_nodes=args.show_nodes,
                                       show_topics=args.show_topics,
                                       show_io_details=args.show_io_details,
                                       show_connections=args.show_connections)
                    else:
                        # Just show a brief waiting message
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for ROS2 nodes...", end='\r')

                    last_update = current_time

        except KeyboardInterrupt:
            print("\n\nStopping monitor...")

        # Final statistics display
        print("\nFinal Statistics:")
        stats_data = monitor.get_statistics()
        # Add node statistics
        stats_data['node_stats'] = monitor.get_node_statistics()
        print_graph_info(node_info, stats_data, args.node,
                       show_processing=args.show_processing,
                       show_node_stats=args.show_node_stats,
                       show_nodes=args.show_nodes,
                       show_topics=args.show_topics,
                       show_io_details=args.show_io_details,
                       show_connections=args.show_connections)

    finally:
        monitor.close_log()
        monitor.destroy_node()
        rclpy.shutdown()
        print("ROS2 Graph Monitor stopped.")


if __name__ == '__main__':
    main()
