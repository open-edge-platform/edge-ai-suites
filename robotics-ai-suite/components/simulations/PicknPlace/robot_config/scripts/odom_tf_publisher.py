#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

"""
Publishes TF transform from odometry messages.
This is needed because Gazebo Harmonic's DiffDrive plugin doesn't publish TF directly to ROS.
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster


class OdomTFPublisher(Node):
    def __init__(self):
        super().__init__('odom_tf_publisher')

        # Declare parameters
        self.declare_parameter('odom_topic', '/amr1/odom')
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('frame_prefix', '')

        # Get parameters
        odom_topic = self.get_parameter('odom_topic').get_parameter_value().string_value
        self.publish_tf = self.get_parameter('publish_tf').get_parameter_value().bool_value
        configured_prefix = self.get_parameter('frame_prefix').get_parameter_value().string_value

        # Derive namespace prefix from odom topic if not explicitly configured
        # Example: /amr1/odom -> amr1
        derived_prefix = ''
        topic_parts = [part for part in odom_topic.split('/') if part]
        if len(topic_parts) >= 2 and topic_parts[-1] == 'odom':
            derived_prefix = topic_parts[-2]

        self.frame_prefix = configured_prefix.strip('/') if configured_prefix else derived_prefix

        # Create TF broadcaster
        if self.publish_tf:
            self.tf_broadcaster = TransformBroadcaster(self)

        # Subscribe to odometry
        self.odom_sub = self.create_subscription(
            Odometry,
            odom_topic,
            self.odom_callback,
            10
        )

        self.get_logger().info(
            f'Subscribed to {odom_topic}, publishing TF: {self.publish_tf},'
            f' frame_prefix: {self.frame_prefix or "<none>"}'
        )

    def _normalize_frame(self, frame_id: str):
        """Normalize TF frame names and apply namespace prefix when needed."""
        if not frame_id:
            return frame_id

        normalized = frame_id.lstrip('/')
        if not self.frame_prefix:
            return normalized

        if normalized.startswith(self.frame_prefix + '/'):
            return normalized

        # Keep global frames unmodified
        if normalized in ('map', 'world'):
            return normalized

        return f'{self.frame_prefix}/{normalized}'

    def odom_callback(self, msg: Odometry):
        """Convert odometry message to TF transform."""
        if not self.publish_tf:
            return

        # Create transform message
        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = self._normalize_frame(msg.header.frame_id)
        t.child_frame_id = self._normalize_frame(msg.child_frame_id)

        # Copy pose
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        t.transform.rotation = msg.pose.pose.orientation

        # Broadcast transform
        self.tf_broadcaster.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = OdomTFPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        node.get_logger().error(f'Exception in odom_tf_publisher: {e}')
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass  # Ignore double shutdown errors


if __name__ == '__main__':
    main()
