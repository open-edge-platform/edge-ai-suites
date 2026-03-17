#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
ROS2 Latency Tester - Roundtrip latency measurement similar to performance_test.

This tool measures roundtrip latency by publishing messages with embedded timestamps
and calculating the time delta when the message returns. It provides statistics
similar to the Intel ECI performance_test tool.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy
import time
import statistics
import argparse
from dataclasses import dataclass, field
from typing import List, Optional
import csv
from datetime import datetime


@dataclass
class LatencyStatistics:
    """Statistics container matching performance_test output."""
    samples: int = 0
    latency_min_ms: float = float('inf')
    latency_max_ms: float = 0.0
    latency_mean_ms: float = 0.0
    latency_variance_ms: float = 0.0
    latency_values: List[float] = field(default_factory=list)
    
    def update(self, latency_ms: float):
        """Update statistics with a new latency sample."""
        self.samples += 1
        self.latency_values.append(latency_ms)
        
        # Update min/max
        if latency_ms < self.latency_min_ms:
            self.latency_min_ms = latency_ms
        if latency_ms > self.latency_max_ms:
            self.latency_max_ms = latency_ms
        
        # Recalculate mean and variance
        self.latency_mean_ms = statistics.mean(self.latency_values)
        if len(self.latency_values) > 1:
            self.latency_variance_ms = statistics.variance(self.latency_values)
    
    def get_summary(self) -> dict:
        """Get summary statistics."""
        if self.samples == 0:
            return {}
        
        return {
            'samples': self.samples,
            'min_ms': self.latency_min_ms,
            'max_ms': self.latency_max_ms,
            'mean_ms': self.latency_mean_ms,
            'variance_ms': self.latency_variance_ms,
            'std_dev_ms': statistics.stdev(self.latency_values) if len(self.latency_values) > 1 else 0.0,
            'percentile_99_ms': statistics.quantiles(self.latency_values, n=100)[98] if len(self.latency_values) > 1 else self.latency_mean_ms,
            'percentile_999_ms': statistics.quantiles(self.latency_values, n=1000)[998] if len(self.latency_values) > 10 else self.latency_mean_ms,
        }
    
    def failures(self, budget_ms: float) -> int:
        """Count how many samples exceeded the latency budget."""
        return sum(1 for lat in self.latency_values if lat > budget_ms)


class LatencyTesterNode(Node):
    """
    Node for roundtrip latency testing.
    
    Modes:
    - Main: Publishes messages on 'test_topic' and receives them on 'test_topic_reply'
    - Relay: Receives messages on 'test_topic' and echoes them to 'test_topic_reply'
    """
    
    def __init__(self, 
                 mode: str = 'Main',
                 rate: int = 1000,
                 msg_size: int = 1024,
                 max_runtime: int = 60,
                 reliability: str = 'BEST_EFFORT',
                 durability: str = 'VOLATILE',
                 history_depth: int = 16,
                 log_file: Optional[str] = None,
                 print_console: bool = True):
        super().__init__('latency_tester')
        
        self.mode = mode
        self.rate = rate
        self.msg_size = msg_size
        self.max_runtime = max_runtime
        self.print_console = print_console
        self.start_time = time.time()
        
        # Statistics
        self.stats = LatencyStatistics()
        self.sent_count = 0
        self.received_count = 0
        self.lost_count = 0
        
        # Pending messages {timestamp: msg_data}
        self.pending_messages = {}
        
        # CSV logging
        self.csv_file = None
        self.csv_writer = None
        if log_file:
            self._init_csv_logging(log_file)
        
        # Setup QoS
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT if reliability == 'BEST_EFFORT' else QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE if durability == 'VOLATILE' else QoSDurabilityPolicy.TRANSIENT_LOCAL,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=history_depth
        )
        
        # Import String message type for simple testing
        from std_msgs.msg import String
        
        if mode == 'Main':
            # Main mode: publish and subscribe
            self.publisher = self.create_publisher(String, 'test_topic', qos)
            self.subscription = self.create_subscription(
                String,
                'test_topic_reply',
                self.reply_callback,
                qos
            )
            
            # Create timer for publishing
            timer_period = 1.0 / rate  # seconds
            self.timer = self.create_timer(timer_period, self.publish_message)
            
            # Create timer for periodic stats display
            self.stats_timer = self.create_timer(1.0, self.print_stats)
            
            self.get_logger().info(f'Latency Tester (Main mode) started - Rate: {rate} Hz, Runtime: {max_runtime}s')
            
        elif mode == 'Relay':
            # Relay mode: just echo messages
            self.publisher = self.create_publisher(String, 'test_topic_reply', qos)
            self.subscription = self.create_subscription(
                String,
                'test_topic',
                self.relay_callback,
                qos
            )
            self.get_logger().info('Latency Tester (Relay mode) started')
        
        else:
            self.get_logger().error(f'Unknown mode: {mode}. Use "Main" or "Relay"')
            raise ValueError(f'Unknown mode: {mode}')
    
    def _init_csv_logging(self, log_file: str):
        """Initialize CSV logging."""
        try:
            self.csv_file = open(log_file, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            
            # Write metadata header
            self.csv_writer.writerow(['# Latency Test Results'])
            self.csv_writer.writerow(['# Mode:', self.mode])
            self.csv_writer.writerow(['# Rate (Hz):', self.rate])
            self.csv_writer.writerow(['# Message Size:', self.msg_size])
            self.csv_writer.writerow(['# Max Runtime (s):', self.max_runtime])
            self.csv_writer.writerow([])
            
            # Write data header
            self.csv_writer.writerow([
                'timestamp',
                'wall_time',
                'latency_ms',
                'sent',
                'received',
                'lost',
                'loss_pct'
            ])
            self.csv_file.flush()
            self.get_logger().info(f'Logging to: {log_file}')
        except Exception as e:
            self.get_logger().error(f'Failed to initialize CSV: {e}')
            self.csv_writer = None
    
    def publish_message(self):
        """Publish a message with embedded timestamp (Main mode)."""
        # Check if max runtime exceeded
        if time.time() - self.start_time >= self.max_runtime:
            self.get_logger().info('Max runtime reached, stopping...')
            self.print_final_summary()
            raise SystemExit
        
        from std_msgs.msg import String
        
        # Create message with timestamp
        timestamp = time.time()
        # Embed timestamp and padding data
        padding = 'X' * max(0, self.msg_size - 50)  # Approximate size
        msg = String()
        msg.data = f'{timestamp}:{padding}'
        
        # Publish
        self.publisher.publish(msg)
        self.sent_count += 1
        
        # Track pending message
        self.pending_messages[timestamp] = msg.data
        
        # Clean up old pending messages (>5 seconds old)
        cutoff = timestamp - 5.0
        self.pending_messages = {k: v for k, v in self.pending_messages.items() if k > cutoff}
    
    def reply_callback(self, msg):
        """Handle received reply message (Main mode)."""
        receive_time = time.time()
        
        try:
            # Extract timestamp from message
            parts = msg.data.split(':', 1)
            if len(parts) < 1:
                return
            
            send_time = float(parts[0])
            
            # Calculate latency
            latency_s = receive_time - send_time
            latency_ms = latency_s * 1000.0
            
            # Update statistics
            self.stats.update(latency_ms)
            self.received_count += 1
            
            # Remove from pending
            if send_time in self.pending_messages:
                del self.pending_messages[send_time]
            
            # Calculate loss
            self.lost_count = self.sent_count - self.received_count
            loss_pct = (self.lost_count / self.sent_count * 100) if self.sent_count > 0 else 0
            
            # Log to CSV
            if self.csv_writer:
                self.csv_writer.writerow([
                    receive_time,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                    latency_ms,
                    self.sent_count,
                    self.received_count,
                    self.lost_count,
                    loss_pct
                ])
                self.csv_file.flush()
                
        except (ValueError, IndexError) as e:
            self.get_logger().warn(f'Failed to parse message: {e}')
    
    def relay_callback(self, msg):
        """Echo received message back (Relay mode)."""
        # Simply republish the message
        self.publisher.publish(msg)
    
    def print_stats(self):
        """Print periodic statistics (Main mode)."""
        if not self.print_console or self.mode != 'Main':
            return
        
        runtime = time.time() - self.start_time
        summary = self.stats.get_summary()
        
        if summary:
            print(f"\n{'='*70}")
            print(f"Runtime: {runtime:.1f}s | Sent: {self.sent_count} | Received: {self.received_count} | Lost: {self.lost_count}")
            print(f"{'='*70}")
            print(f"Latency (ms):")
            print(f"  Min:      {summary['min_ms']:.4f}")
            print(f"  Max:      {summary['max_ms']:.4f}")
            print(f"  Mean:     {summary['mean_ms']:.4f}")
            print(f"  Std Dev:  {summary['std_dev_ms']:.4f}")
            print(f"  99th %%:   {summary['percentile_99_ms']:.4f}")
            print(f"  Samples:  {summary['samples']}")
            
            # Check against 1ms budget (for 1000 Hz)
            if self.rate == 1000:
                failures = self.stats.failures(1.0)
                print(f"\nFailures (>1ms): {failures} / {summary['samples']} ({failures/summary['samples']*100:.2f}%)")
    
    def print_final_summary(self):
        """Print final summary statistics."""
        print(f"\n{'='*70}")
        print("FINAL RESULTS")
        print(f"{'='*70}")
        
        runtime = time.time() - self.start_time
        loss_pct = (self.lost_count / self.sent_count * 100) if self.sent_count > 0 else 0
        
        print(f"\nTest Configuration:")
        print(f"  Mode:        {self.mode}")
        print(f"  Rate:        {self.rate} Hz")
        print(f"  Runtime:     {runtime:.2f} s")
        print(f"  Message Size: {self.msg_size} bytes")
        
        print(f"\nMessage Statistics:")
        print(f"  Sent:        {self.sent_count}")
        print(f"  Received:    {self.received_count}")
        print(f"  Lost:        {self.lost_count} ({loss_pct:.2f}%)")
        
        summary = self.stats.get_summary()
        if summary:
            print(f"\nLatency Statistics (ms):")
            print(f"  Samples:     {summary['samples']}")
            print(f"  Min:         {summary['min_ms']:.4f}")
            print(f"  Max:         {summary['max_ms']:.4f}")
            print(f"  Mean:        {summary['mean_ms']:.4f}")
            print(f"  Std Dev:     {summary['std_dev_ms']:.4f}")
            print(f"  Variance:    {summary['variance_ms']:.6f}")
            print(f"  99th %%:      {summary['percentile_99_ms']:.4f}")
            print(f"  99.9th %%:    {summary['percentile_999_ms']:.4f}")
            
            # Calculate failures for common rates
            cycle_time_ms = 1000.0 / self.rate
            failures = self.stats.failures(cycle_time_ms)
            
            print(f"\n{'='*70}")
            print(f"INDUSTRIAL EVALUATION ({self.rate} Hz → {cycle_time_ms:.3f}ms budget)")
            print(f"{'='*70}")
            print(f"  Failures (>{cycle_time_ms:.3f}ms): {failures} / {summary['samples']} ({failures/summary['samples']*100:.1f}%)")
            print(f"  Worst case: {summary['max_ms']:.4f} ms")
            
            if summary['max_ms'] < cycle_time_ms:
                print(f"\n   EXCELLENT - Even worst case within {cycle_time_ms:.3f}ms budget")
            elif failures == 0:
                print(f"\n   PASSED - All mean latencies within budget")
            else:
                print(f"\n    NEEDS TUNING - {failures} samples exceeded budget")
            
            # Jitter assessment
            jitter_pct = (summary['std_dev_ms'] / summary['mean_ms']) * 100
            print(f"\n  Jitter (CoV): {jitter_pct:.1f}%")
            if jitter_pct < 10:
                print(f"     Low jitter - Consistent performance")
            elif jitter_pct < 25:
                print(f"      Moderate jitter")
            else:
                print(f"     High jitter - Needs investigation")
        
        print(f"{'='*70}\n")
        
        if self.csv_file:
            self.csv_file.close()
    
    def __del__(self):
        """Cleanup."""
        if hasattr(self, 'csv_file') and self.csv_file:
            self.csv_file.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='ROS2 Roundtrip Latency Tester (similar to performance_test)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Terminal 1 - Main node (measures latency)
  ros2 run ros2-kpi latency-tester --mode Main --rate 1000 --max-runtime 60
  
  # Terminal 2 - Relay node (echoes messages back)
  ros2 run ros2-kpi latency-tester --mode Relay
  
  # With CSV logging
  ros2 run ros2-kpi latency-tester --mode Main --rate 1000 --logfile results.csv
  
  # High-frequency test
  ros2 run ros2-kpi latency-tester --mode Main --rate 2000 --max-runtime 30
        """
    )
    
    parser.add_argument('--mode', type=str, default='Main', choices=['Main', 'Relay'],
                        help='Test mode: Main (publishes and measures) or Relay (echoes back)')
    parser.add_argument('--rate', type=int, default=1000,
                        help='Publishing rate in Hz (default: 1000)')
    parser.add_argument('--msg-size', type=int, default=1024,
                        help='Message payload size in bytes (default: 1024)')
    parser.add_argument('--max-runtime', type=int, default=60,
                        help='Maximum test runtime in seconds (default: 60)')
    parser.add_argument('--reliability', type=str, default='BEST_EFFORT',
                        choices=['BEST_EFFORT', 'RELIABLE'],
                        help='QoS reliability (default: BEST_EFFORT)')
    parser.add_argument('--durability', type=str, default='VOLATILE',
                        choices=['VOLATILE', 'TRANSIENT_LOCAL'],
                        help='QoS durability (default: VOLATILE)')
    parser.add_argument('--history-depth', type=int, default=16,
                        help='QoS history depth (default: 16)')
    parser.add_argument('--logfile', type=str, default=None,
                        help='CSV log file path')
    parser.add_argument('--print-console', action='store_true', default=True,
                        help='Print statistics to console')
    
    args = parser.parse_args()
    
    rclpy.init()
    
    try:
        node = LatencyTesterNode(
            mode=args.mode,
            rate=args.rate,
            msg_size=args.msg_size,
            max_runtime=args.max_runtime,
            reliability=args.reliability,
            durability=args.durability,
            history_depth=args.history_depth,
            log_file=args.logfile,
            print_console=args.print_console
        )
        
        rclpy.spin(node)
        
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
