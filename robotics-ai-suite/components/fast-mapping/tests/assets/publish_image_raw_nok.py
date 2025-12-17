#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Test module for publishing uninitialized sensor_msgs.msg.Image messages.

Publishes empty depth images to test FastMapping's error handling.
"""

import sys
import rclpy

from sensor_msgs.msg import CameraInfo
from sensor_msgs.msg import Image
from publish_camera_info import fast_mapping_is_alive


def show_help():
    """Display help message and exit when FastMapping node is not running."""
    print("ERROR: FastMapping node must be running before starting this test...")
    print("ros2 run fast_mapping fast_mapping node")
    sys.exit(1)


def send_depth_info(ros_node):
    """Send a depth info message to unblock FastMapping."""
    ros_node.get_logger().info("Send a depth info msg to unblock FastMapping")

    camera_publisher = ros_node.create_publisher(
        CameraInfo,
        "camera/aligned_depth_to_color/camera_info", 10)
    camera_info = CameraInfo()
    camera_publisher.publish(camera_info)


if __name__ == "__main__":

    rclpy.init(args=sys.argv)

    # Create node and publisher
    node = rclpy.create_node("image_raw_nok_publisher")

    # send a depth info message to unlock FastMapping
    send_depth_info(node)

    # Create a publisher for image raw
    image_publisher = node.create_publisher(Image, "camera/aligned_depth_to_color/image_raw", 10)
    image_raw = Image()

    node.get_logger().info("Sending an empty depth image message")

    # Publish message of type 'Image' to the topic
    image_publisher.publish(image_raw)

    fast_mapping_is_alive()
