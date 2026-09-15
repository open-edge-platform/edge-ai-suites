#!/usr/bin/env python3
"""Subscribe to fast_lio's /Odometry and write it out in TUM format.

Plain hku-mars/FAST_LIO (unlike FAST-LIVO2) has no built-in TUM trajectory
export - it only publishes nav_msgs/Odometry. This is the small piece that
fills that gap so evaluate_rmse.sh has an estimated trajectory to compare
against ground truth.

Usage:
  record_odometry_tum.py --topic /Odometry --out est_tum.txt
"""
import argparse
import signal
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from nav_msgs.msg import Odometry


class OdometryRecorder(Node):
    def __init__(self, topic, out_path):
        super().__init__("record_odometry_tum")
        self.file = open(out_path, "w")
        self.count = 0
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=200,
        )
        self.sub = self.create_subscription(Odometry, topic, self.on_odom, qos)

    def on_odom(self, msg):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        self.file.write(f"{t:.9f} {p.x:.6f} {p.y:.6f} {p.z:.6f} "
                        f"{q.x:.9f} {q.y:.9f} {q.z:.9f} {q.w:.9f}\n")
        self.count += 1
        if self.count % 200 == 0:
            self.file.flush()

    def close(self):
        self.file.flush()
        self.file.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="/Odometry")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rclpy.init()
    node = OdometryRecorder(args.topic, args.out)

    def handle_signal(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info(f"Wrote {node.count} odometry poses to {args.out}")
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
