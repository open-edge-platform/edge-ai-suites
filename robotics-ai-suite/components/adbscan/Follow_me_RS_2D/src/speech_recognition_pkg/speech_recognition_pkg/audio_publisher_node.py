#!/usr/bin/env python3
# pylint: disable=duplicate-code
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

"""Publish simulated audio filenames based on guide-robot odometry."""

import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String


class AudioPublisher(Node):  # pylint: disable=too-many-instance-attributes
    """Emit audio filename commands triggered by the guide-robot position."""
    def __init__(self):
        """Initialize subscriptions, publishers, and parameters."""
        super().__init__('audio_publisher_node')
        # declare parameters
        self.declare_parameter('odom_topic', '/guide_robot/odom')
        self.declare_parameter('publish_frequency', 10)

        self.odom_topic_name_ = self.get_parameter('odom_topic').value
        self.publish_period_ = 1.0 / self.get_parameter('publish_frequency').value

        self.odom_subscriber_ = self.create_subscription(
            Odometry, self.odom_topic_name_, self.odom_topic_callback, 10
        )
        self.audio_publisher_ = self.create_publisher(String, 'audio_filename', 10)
        self.timer_ = self.create_timer(self.publish_period_, self.publish)
        self.pos_ = [0.0, 0.0, 0.0]
        self.rpy_ = (0.0, 0.0, 0.0)
        self.start_audio_published = False
        self.stop_audio_published = False
        self.get_logger().info('audio_publisher_node has been started')

    def odom_topic_callback(self, odom_msg):
        """Store pose from odometry messages."""
        self.rpy_ = self.euler_from_quaternion(
            odom_msg.pose.pose.orientation.x,
            odom_msg.pose.pose.orientation.y,
            odom_msg.pose.pose.orientation.z,
            odom_msg.pose.pose.orientation.w,
        )
        self.pos_ = [
            odom_msg.pose.pose.position.x,
            odom_msg.pose.pose.position.y,
            odom_msg.pose.pose.position.z,
        ]

    def publish(self):
        """Choose and publish the audio filename based on guide position."""
        audio_filename_msg = String()

        # Guide now moves in +X direction with S-curve trajectory.
        # "start" fires once when guide is near its starting position (~0.8, 0).
        # "stop" fires once when guide has nearly finished its trajectory.
        # Both are one-shot: after publishing the command once, we go back to
        # empty so the ADBSCAN node isn't flooded with persistent stop/start.
        if self.pos_[0] > 0.5 and self.pos_[0] < 1.5 and not self.start_audio_published:
            audio_filename_msg.data = 'start-1.wav'
            self.start_audio_published = True
        elif self.pos_[0] > 3.5 and not self.stop_audio_published:
            audio_filename_msg.data = 'stop-1.wav'
            self.stop_audio_published = True
        else:
            audio_filename_msg.data = ''
        self.audio_publisher_.publish(audio_filename_msg)
        self.get_logger().info(f'publishing audio file: {audio_filename_msg.data}')

    def euler_from_quaternion(self, x, y, z, w):
        """
        Convert a quaternion into euler angles (roll, pitch, yaw)
        roll is rotation around x in radians (counterclockwise)
        pitch is rotation around y in radians (counterclockwise)
        yaw is rotation around z in radians (counterclockwise)
        """
        t0 = +2.0 * (w * x + y * z)
        t1 = +1.0 - 2.0 * (x * x + y * y)
        roll_x = math.atan2(t0, t1)

        t2 = +2.0 * (w * y - z * x)
        t2 = +1.0 if t2 > +1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        pitch_y = math.asin(t2)

        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        yaw_z = math.atan2(t3, t4)

        return (roll_x, pitch_y, yaw_z)  # in radians


def main(args=None):
    """Entry point for the audio publisher node."""
    rclpy.init(args=args)
    node = AudioPublisher()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
