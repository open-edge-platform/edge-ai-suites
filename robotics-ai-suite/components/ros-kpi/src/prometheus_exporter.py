#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
ROS2 KPI Prometheus Exporter

Exposes ROS2 monitoring metrics in Prometheus format for Grafana visualization.
Reads from the same data sources as the monitoring scripts and exposes metrics
on an HTTP endpoint for Prometheus to scrape.
"""

import argparse
import csv
import time
import sys
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, Optional
import threading

try:
    from prometheus_client import Gauge, Counter, Histogram, Info, make_wsgi_app
    from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY
except ImportError:
    print("Error: prometheus_client not installed")
    print("Install with: uv sync")
    sys.exit(1)


def _start_http_server_reuse(port: int, addr: str = ''):
    """
    Like prometheus_client.start_http_server but sets SO_REUSEADDR so the
    process can rebind immediately after a previous instance exits.
    """
    import socket
    from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
    import logging

    class _SilentHandler(WSGIRequestHandler):
        def log_message(self, fmt, *args):   # suppress request logs
            pass

    class _ReuseServer(WSGIServer):
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()

    app = make_wsgi_app()
    httpd = make_server(addr, port, app, _ReuseServer, handler_class=_SilentHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


class ROS2MetricsCollector:
    """Collects ROS2 KPI metrics from monitoring data and exposes them for Prometheus."""

    def __init__(self, session_dir: Optional[Path] = None):
        """
        Initialize the metrics collector.

        Args:
            session_dir: Path to monitoring session directory containing CSV/log files
        """
        self.session_dir = session_dir
        self.graph_log = None
        self.resource_log = None

        if session_dir:
            self.graph_log = session_dir / "graph_timing.csv"
            self.resource_log = session_dir / "resource_usage.log"

        # Initialize Prometheus metrics
        self._init_metrics()

    def _init_metrics(self):
        """Initialize Prometheus metric objects."""
        # Topic metrics
        self.topic_message_count = Gauge(
            'ros2_topic_message_count',
            'Total messages received on topic',
            ['topic', 'msg_type', 'io_direction']
        )

        self.topic_frequency = Gauge(
            'ros2_topic_frequency_hz',
            'Message frequency in Hz',
            ['topic', 'msg_type', 'io_direction']
        )

        self.topic_delta_time = Gauge(
            'ros2_topic_delta_time_ms',
            'Time between messages in milliseconds',
            ['topic', 'msg_type', 'io_direction']
        )

        self.processing_delay = Gauge(
            'ros2_processing_delay_ms',
            'Input to output processing delay in milliseconds',
            ['topic', 'msg_type']
        )

        # Node metrics
        self.node_avg_latency = Gauge(
            'ros2_node_avg_latency_ms',
            'Average processing latency per node',
            ['node']
        )

        self.node_avg_frequency = Gauge(
            'ros2_node_avg_frequency_hz',
            'Average message frequency per node',
            ['node']
        )

        # Per-node topic metrics (populated from graph_topology.json + CSV KPIs)
        # direction = 'publishes' | 'subscribes'
        self.node_topic_frequency = Gauge(
            'ros2_node_topic_frequency_hz',
            'Message frequency for a topic associated with a node',
            ['node', 'topic', 'direction']
        )

        self.node_topic_latency = Gauge(
            'ros2_node_topic_latency_ms',
            'Mean latency for a topic associated with a node',
            ['node', 'topic', 'direction']
        )

        self.node_topic_msg_count = Gauge(
            'ros2_node_topic_msg_count',
            'Message count for a topic associated with a node',
            ['node', 'topic', 'direction']
        )

        self.node_proc_delay = Gauge(
            'ros2_node_proc_delay_ms',
            'Processing delay (input→output) for a node',
            ['node']
        )

        # Resource metrics
        self.cpu_usage = Gauge(
            'ros2_process_cpu_percent',
            'CPU usage percentage',
            ['process', 'pid', 'thread']
        )

        self.memory_usage = Gauge(
            'ros2_process_memory_mb',
            'Memory usage in megabytes',
            ['process', 'pid']
        )

        self.io_read = Gauge(
            'ros2_process_io_read_kb_per_sec',
            'I/O read rate in KB/s',
            ['process', 'pid']
        )

        self.io_write = Gauge(
            'ros2_process_io_write_kb_per_sec',
            'I/O write rate in KB/s',
            ['process', 'pid']
        )

        # System info
        self.exporter_info = Info('ros2_kpi_exporter', 'ROS2 KPI Exporter Information')
        self.exporter_info.info({
            'version': '1.0',
            'session_dir': str(self.session_dir) if self.session_dir else 'live'
        })

    # ------------------------------------------------------------------
    def update_from_topology_json(self):
        """
        Read graph_topology.json and graph_timing.csv together to populate
        ros2_node_topic_* metrics that carry node→topic relationships and
        per-topic KPIs (frequency, latency, msg count).
        """
        import json as _json

        topo_path = None
        if self.session_dir:
            topo_path = self.session_dir / 'graph_topology.json'
        if not topo_path or not topo_path.exists():
            return

        try:
            with open(topo_path) as f:
                topo = _json.load(f)
        except Exception as e:
            print(f"Error reading topology JSON: {e}")
            return

        nodes  = topo.get('nodes',  {})
        topics = topo.get('topics', {})

        # Build topic KPI lookup from the topology itself (already has freq/latency)
        # then enrich with CSV if needed
        topic_kpi: dict = {}
        for tname, td in topics.items():
            topic_kpi[tname] = {
                'freq':      td.get('avg_freq_hz'),
                'latency':   td.get('latency_mean_ms') or td.get('avg_delta_ms'),
                'msg_count': td.get('msg_count', 0) or 0,
            }

        # Supplement with CSV if KPIs are missing (topology without live data)
        if self.graph_log and self.graph_log.exists():
            try:
                last: dict = {}
                with open(self.graph_log) as f:
                    for row in csv.DictReader(f):
                        last[row['topic_name']] = row
                for tname, row in last.items():
                    if tname not in topic_kpi:
                        topic_kpi[tname] = {}
                    kpi = topic_kpi[tname]
                    def _f(v):
                        try: return float(v) if v and v.strip() else None
                        except: return None
                    if kpi.get('freq')    is None: kpi['freq']    = _f(row.get('frequency_hz'))
                    if kpi.get('latency') is None: kpi['latency'] = _f(row.get('latency_mean_ms'))
                    if not kpi.get('msg_count'):   kpi['msg_count'] = int(_f(row.get('message_count')) or 0)
            except Exception as e:
                print(f"Warning: could not enrich from CSV: {e}")

        # Emit per-node metrics
        for nname, nd in nodes.items():
            short = nname.lstrip('/')

            # Processing delay
            pd_mean = nd.get('proc_delay_mean_ms')
            if pd_mean is not None:
                self.node_proc_delay.labels(node=short).set(pd_mean)

            node_freqs = []
            node_latencies = []

            for direction, topic_list in [('publishes', nd.get('publishes', [])),
                                          ('subscribes', nd.get('subscribes', []))]:
                for tname in topic_list:
                    kpi = topic_kpi.get(tname, {})
                    freq    = kpi.get('freq')
                    latency = kpi.get('latency')
                    mc      = kpi.get('msg_count', 0)

                    # Always emit frequency so the 'node' label is registered in
                    # Prometheus even before messages start flowing (fixes the
                    # Grafana $node variable being empty at startup / in remote mode).
                    self.node_topic_frequency.labels(
                        node=short, topic=tname, direction=direction
                    ).set(freq if freq is not None else 0.0)
                    if latency is not None:
                        self.node_topic_latency.labels(
                            node=short, topic=tname, direction=direction
                        ).set(latency)
                    self.node_topic_msg_count.labels(
                        node=short, topic=tname, direction=direction
                    ).set(mc)

                    if freq is not None:
                        node_freqs.append(freq)
                    if latency is not None:
                        node_latencies.append(latency)

            # Aggregate per-node averages (used by the node overview Grafana panels)
            if node_freqs:
                self.node_avg_frequency.labels(node=short).set(
                    sum(node_freqs) / len(node_freqs)
                )
            if node_latencies:
                self.node_avg_latency.labels(node=short).set(
                    sum(node_latencies) / len(node_latencies)
                )

    # ------------------------------------------------------------------
    def update_from_graph_csv(self):
        """Read graph timing CSV and update metrics."""
        if not self.graph_log or not self.graph_log.exists():
            return

        try:
            # Read the last N entries from CSV (keep a sliding window)
            with open(self.graph_log, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                if not rows:
                    return

                # Process recent data (last 100 entries or all if fewer)
                recent_rows = rows[-100:]

                # Group by topic and update metrics
                topic_data = defaultdict(list)
                for row in recent_rows:
                    topic = row['topic_name']
                    topic_data[topic].append(row)

                # Update metrics for each topic
                for topic, topic_rows in topic_data.items():
                    # Get most recent row for this topic
                    latest = topic_rows[-1]

                    msg_type = latest.get('msg_type', 'unknown')
                    is_input = latest.get('is_input', 'False') == 'True'
                    is_output = latest.get('is_output', 'False') == 'True'

                    io_direction = 'input' if is_input else ('output' if is_output else 'unknown')

                    # Update metrics
                    if latest.get('message_count'):
                        self.topic_message_count.labels(
                            topic=topic,
                            msg_type=msg_type,
                            io_direction=io_direction
                        ).set(float(latest['message_count']))

                    if latest.get('frequency_hz'):
                        self.topic_frequency.labels(
                            topic=topic,
                            msg_type=msg_type,
                            io_direction=io_direction
                        ).set(float(latest['frequency_hz']))

                    if latest.get('delta_time_ms') and latest['delta_time_ms']:
                        self.topic_delta_time.labels(
                            topic=topic,
                            msg_type=msg_type,
                            io_direction=io_direction
                        ).set(float(latest['delta_time_ms']))

                    if latest.get('processing_delay_ms') and latest['processing_delay_ms']:
                        self.processing_delay.labels(
                            topic=topic,
                            msg_type=msg_type
                        ).set(float(latest['processing_delay_ms']))

        except Exception as e:
            print(f"Error reading graph CSV: {e}")

    def update_from_resource_log(self):
        """Read resource usage log and update metrics."""
        if not self.resource_log or not self.resource_log.exists():
            return

        import re
        try:
            with open(self.resource_log, 'r') as f:
                lines = f.readlines()

            # Collect last value per PID so we emit the most recent sample
            latest: dict = {}   # pid -> {cpu, rss_mb, command}

            for line in lines:
                line = line.rstrip()
                if not re.match(r'^\d{2}:\d{2}:\d{2} [AP]M', line):
                    continue
                parts = line.split()
                if len(parts) < 12:
                    continue

                # Detect thread mode vs PID mode (same heuristic as visualize_resources.py)
                # Thread mode: parts[4] is '-' or a plain integer (TID)
                # PID mode:    parts[4] is a float percentage like '0.60'
                has_threads = (parts[4] == '-' or
                               (parts[4].isdigit() and len(parts) >= 16))

                try:
                    if has_threads:
                        # Thread mode: Time UID TGID TID %usr %sys %guest %wait %CPU CPU ... VSZ RSS %MEM Command
                        tgid    = parts[3]
                        tid     = parts[4]
                        if tid != '-':          # only process-level (TGID) lines
                            continue
                        cpu_pct = float(parts[9])
                        rss_kb  = int(parts[14])
                        command = ' '.join(parts[16:]) if len(parts) > 16 else parts[-1]
                        pid_key = tgid
                    else:
                        # PID mode: Time UID PID %usr %sys %guest %wait %CPU CPU ... VSZ RSS %MEM Command
                        pid_key = parts[3]
                        cpu_pct = float(parts[8])
                        rss_kb  = int(parts[13])
                        command = ' '.join(parts[15:]) if len(parts) > 15 else parts[-1]

                    latest[pid_key] = {
                        'cpu':     cpu_pct,
                        'rss_mb':  rss_kb / 1024.0,
                        'command': command.strip(),
                    }
                except (ValueError, IndexError):
                    continue

            # Emit metrics for the most recent sample of each PID
            for pid, info in latest.items():
                proc = info['command'] or f'pid_{pid}'
                self.cpu_usage.labels(
                    process=proc, pid=pid, thread='-'
                ).set(info['cpu'])
                self.memory_usage.labels(
                    process=proc, pid=pid
                ).set(info['rss_mb'])

        except Exception as e:
            print(f"Error reading resource log: {e}")

    def start_live_monitoring(self, interval: int = 5):
        """
        Start live monitoring mode - continuously update metrics from data files.

        Args:
            interval: Update interval in seconds
        """
        print(f"Starting live metric collection (update interval: {interval}s)")

        while True:
            try:
                self.update_from_graph_csv()
                self.update_from_resource_log()
                self.update_from_topology_json()
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nStopping metric collection...")
                break
            except Exception as e:
                print(f"Error in live monitoring: {e}")
                time.sleep(interval)


class LiveMetricsExporter:
    """
    Direct live metrics exporter that integrates with monitor_stack.
    This version receives metrics directly rather than reading from files.
    """

    def __init__(self):
        """Initialize live metrics exporter."""
        self._init_metrics()
        self.lock = threading.Lock()

    def _init_metrics(self):
        """Initialize Prometheus metric objects."""
        # Topic metrics
        self.topic_frequency = Gauge(
            'ros2_live_topic_frequency_hz',
            'Live message frequency in Hz',
            ['topic', 'node']
        )

        self.topic_rate = Gauge(
            'ros2_live_topic_rate',
            'Live message rate',
            ['topic', 'node']
        )

        self.processing_delay = Gauge(
            'ros2_live_processing_delay_ms',
            'Live processing delay in milliseconds',
            ['node', 'input_topic', 'output_topic']
        )

        # Resource metrics
        self.cpu_percent = Gauge(
            'ros2_live_cpu_percent',
            'Live CPU usage percentage',
            ['process', 'pid', 'thread']
        )

        self.memory_mb = Gauge(
            'ros2_live_memory_mb',
            'Live memory usage in MB',
            ['process', 'pid']
        )

    def update_topic_metrics(self, topic: str, node: str, frequency: float, rate: float):
        """Update topic metrics."""
        with self.lock:
            self.topic_frequency.labels(topic=topic, node=node).set(frequency)
            self.topic_rate.labels(topic=topic, node=node).set(rate)

    def update_processing_delay(self, node: str, input_topic: str, output_topic: str, delay_ms: float):
        """Update processing delay metric."""
        with self.lock:
            self.processing_delay.labels(
                node=node,
                input_topic=input_topic,
                output_topic=output_topic
            ).set(delay_ms)

    def update_cpu_metric(self, process: str, pid: str, thread: str, cpu_percent: float):
        """Update CPU usage metric."""
        with self.lock:
            self.cpu_percent.labels(process=process, pid=pid, thread=thread).set(cpu_percent)

    def update_memory_metric(self, process: str, pid: str, memory_mb: float):
        """Update memory usage metric."""
        with self.lock:
            self.memory_mb.labels(process=process, pid=pid).set(memory_mb)


def main():
    """Main entry point for the Prometheus exporter."""
    parser = argparse.ArgumentParser(
        description='ROS2 KPI Prometheus Exporter - Export ROS2 metrics for Grafana'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=9092,
        help='Port to expose metrics on (default: 9092)'
    )
    parser.add_argument(
        '--session-dir',
        type=str,
        help='Path to monitoring session directory (for file-based mode)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Update interval in seconds (default: 5)'
    )
    parser.add_argument(
        '--sessions-dir',
        type=str,
        default='monitoring_sessions',
        help='Root directory containing session folders (live mode, default: monitoring_sessions)'
    )
    parser.add_argument(
        '--mode',
        choices=['file', 'live'],
        default='file',
        help='Exporter mode: file (read from --session-dir) or live (auto-watch latest session)'
    )

    args = parser.parse_args()

    # Free the port if a previous exporter is still bound to it
    import subprocess as _sp
    try:
        _sp.run(['fuser', '-k', f'{args.port}/tcp'],
                capture_output=True, timeout=3)
        time.sleep(0.4)   # give the OS a moment to release the socket
    except Exception:
        pass

    # Start HTTP server for Prometheus scraping (SO_REUSEADDR enabled)
    print(f"Starting Prometheus exporter on port {args.port}")
    try:
        _start_http_server_reuse(args.port)
    except OSError as e:
        print(f"Error: cannot bind port {args.port}: {e}")
        print(f"Try: fuser -k {args.port}/tcp   then retry.")
        sys.exit(1)

    if args.mode == 'file':
        # File-based mode: read from monitoring session files
        if not args.session_dir:
            print("Error: --session-dir required for file mode")
            sys.exit(1)

        session_path = Path(args.session_dir)
        if not session_path.exists():
            print(f"Error: Session directory not found: {session_path}")
            sys.exit(1)

        collector = ROS2MetricsCollector(session_path)

        print(f"Monitoring session: {session_path}")
        print(f"Metrics available at http://localhost:{args.port}/metrics")
        print("Press Ctrl+C to stop\n")

        collector.start_live_monitoring(interval=args.interval)
    else:
        # Live mode: auto-watch the latest monitoring session dir.
        # Switches automatically when a newer session is created.
        sessions_base = Path(args.sessions_dir)

        print(f"Live mode: watching {sessions_base}/ for the latest session")
        print(f"Metrics available at http://localhost:{args.port}/metrics")
        print("Press Ctrl+C to stop\n")

        def _latest_session(base: Path):
            """Return the newest session directory (by name, which is a timestamp)."""
            if not base.exists():
                return None
            dirs = sorted(
                [d for d in base.iterdir() if d.is_dir() and d.name[:8].isdigit()],
                key=lambda d: d.name
            )
            return dirs[-1] if dirs else None

        collector = None
        current_session = None

        try:
            while True:
                latest = _latest_session(sessions_base)
                if latest != current_session:
                    current_session = latest
                    if current_session:
                        collector = ROS2MetricsCollector(current_session)
                        print(f"[live] Tracking session: {current_session.name}")
                    else:
                        collector = None
                        print(f"[live] No sessions yet — waiting in {sessions_base}/...")

                if collector:
                    try:
                        collector.update_from_graph_csv()
                        collector.update_from_resource_log()
                        collector.update_from_topology_json()
                    except Exception as e:
                        print(f"[live] update error: {e}")

                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopping exporter...")


if __name__ == '__main__':
    main()
