#!/usr/bin/env python3
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Publish uninitialized sensor_msgs.msg.Image messages
to the 'camera/aligned_depth_to_color/image_raw' topic
In case of an empty CameraInfo message, FastMapping should not crash and
an exception is to be caught by FastMapping.
"""

import sys
import subprocess
import rclpy

from sensor_msgs.msg import CameraInfo


def show_help():
    """Display help message and exit when FastMapping node is not running."""
    print("ERROR: FastMapping node must be running before starting this test...")
    print("ros2 run fast_mapping fast_mapping node")
    sys.exit(1)


def fast_mapping_is_alive():
    """Check if FastMapping node is running and display test result."""
    try:
        ros2_nodes = subprocess.check_output(["ros2", "node", "list"])
        if b"/fast_mapping_node" in ros2_nodes:
            print("Test passed")
        else:
            print("Test failed")

    except subprocess.CalledProcessError:
        show_help()


if __name__ == "__main__":

    rclpy.init(args=sys.argv)

    # Create node and publisher
    node = rclpy.create_node("image_camera_info_publisher")
    camera_publisher = node.create_publisher(
        CameraInfo,
        "camera/aligned_depth_to_color/camera_info",
        10,
    )
    cameraInfo = CameraInfo()

    node.get_logger().info("Sending an empty CameraInfo message")

    # Publish message of type 'CameraInfo' to the topic
    camera_publisher.publish(cameraInfo)

    # Check if FastMapping has crashed
    fast_mapping_is_alive()
