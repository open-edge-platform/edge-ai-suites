#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Revision $Id$

"""Publish uninitialized sensor_msgs.msg.Image messages
to the 'camera/aligned_depth_to_color/image_raw' topic.
In case of an empty depth image, FastMapping should not crash and
an OpenCv exception is to be caught by FastMapping.
"""

import os
import signal
import subprocess
import sys

import rclpy
from sensor_msgs.msg import CameraInfo
from sensor_msgs.msg import Image


def exit_with_tip():
    """Prints helpfull message if FastMapping node is not running."""
    print("ERROR: FastMapping node must be running before starting this test...")
    print("Run: ros2 run fast_mapping fast_mapping node")
    sys.exit(1)


# pylint: disable=duplicate-code,inconsistent-return-statements
def get_pid(process_name="fast_mapping_node"):
    """Get the PID of the FastMapping node process or exit if it not running"""
    try:
        pid = subprocess.check_output(["pidof", process_name])
        return int(pid)
    except subprocess.CalledProcessError:
        exit_with_tip()


def pid_is_alive(pid):
    """Checks if process with given PID is alive"""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def send_depth_info(ros_node):
    """Creates publisher and sends a depth message"""
    ros_node.get_logger().info("Send a depth info msg to unblock FastMapping")

    publisher = ros_node.create_publisher(CameraInfo,
                                          "camera/aligned_depth_to_color/camera_info", 10)
    camera_info = CameraInfo()
    publisher.publish(camera_info)


if __name__ == "__main__":
    rclpy.init(args=sys.argv)

    # Create node and publisher
    node = rclpy.create_node("image_raw_nok_publisher")

    # send a depth info message to unlock FastMapping
    send_depth_info(node)

    # Create a publisher for image raw
    pub = node.create_publisher(Image, "camera/aligned_depth_to_color/image_raw", 10)
    imageRaw = Image()

    node.get_logger().info("Sending an empty depth image message")

    # Publish message of type 'Image' to the topic
    pub.publish(imageRaw)

    # Check if FastMapping has crashed
    FM_PID = get_pid()

    # pylint: disable=duplicate-code
    SUCCESS = pid_is_alive(FM_PID)
    if SUCCESS:
        print("Test passed")
        os.kill(FM_PID, signal.SIGKILL)
    else:
        print("Test failed")
