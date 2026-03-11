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

"""Publish simulated trajectory and gesture images for follow-me demo (v2)."""

import math
import os

import cv2
import rclpy
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Image


class TrajAndImgPublisher(Node):  # pylint: disable=too-many-instance-attributes
    """Publish guide-robot velocity commands and camera images on a timer."""
    # Time-based S-curve trajectory: (end_time, linear_x, angular_z)
    # Guide starts at (0.8, 0) facing +X, continuously moving with gentle curves.
    TRAJ_SEGMENTS = [
        (6.0, 0.08,  0.00),    # straight
        (10.0, 0.08,  0.10),   # gentle curve left  (~23 deg)
        (16.0, 0.08,  0.00),   # straight
        (20.0, 0.08, -0.10),   # gentle curve right (~23 deg)
        (26.0, 0.08,  0.00),   # straight
        (30.0, 0.08,  0.10),   # gentle curve left
        (36.0, 0.08,  0.00),   # straight
        (40.0, 0.06, -0.08),   # slow gentle right
        (43.0, 0.04,  0.00),   # slow straight
        (45.0, 0.00,  0.00),   # stop
    ]

    def __init__(self):
        """Initialize the trajectory and image publisher node."""
        super().__init__('traj_and_img_publisher_node')
        # declare parameters
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('twist_topic', '/cmd_vel')
        self.declare_parameter('publish_frequency', 10)
        self.declare_parameter('Camera_topic', '/sim_camera')
        self.odom_topic_name_ = self.get_parameter('odom_topic').value
        self.twist_topic_name_ = self.get_parameter('twist_topic').value
        self.publish_period_ = 1.0 / self.get_parameter('publish_frequency').value
        self.camera_topic_name_ = self.get_parameter('Camera_topic').value

        self.image_dir_ = os.path.join(
            get_package_share_directory('gesture_recognition_pkg'), 'config', 'gesture_imgs'
        )

        self.odom_subscriber_ = self.create_subscription(
            Odometry, self.odom_topic_name_, self.odom_topic_callback, 10
        )
        self.trajectory_publisher_ = self.create_publisher(Twist, self.twist_topic_name_, 10)
        self.image_publisher_ = self.create_publisher(Image, self.camera_topic_name_, 10)
        self.timer_ = self.create_timer(self.publish_period_, self.publish)
        self.pos_ = [0.0, 0.0, 0.0]
        self.rpy_ = (0.0, 0.0, 0.0)
        self.start_time_ = None
        self.startup_delay_ = 10.0  # Wait for Gazebo to stabilize
        self.get_logger().info('trajectory_publisher_node has been started')

    def odom_topic_callback(self, odom_msg):
        """Store pose from odometry messages."""
        if self.start_time_ is None:
            self.start_time_ = self.get_clock().now()
            self.get_logger().info('First odom received — starting startup delay')
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
        """Publish twist and image at each timer tick."""
        twist_msg = Twist()

        # Wait until first odom message is received (Gazebo is ready)
        if self.start_time_ is None:
            image_file_name = os.path.join(self.image_dir_, 'back_no_action.jpg')
            bridge = CvBridge()
            cv_image = cv2.imread(image_file_name)
            image_message = bridge.cv2_to_imgmsg(cv_image, encoding='passthrough')
            self.image_publisher_.publish(image_message)
            self.trajectory_publisher_.publish(twist_msg)
            return

        elapsed = (self.get_clock().now() - self.start_time_).nanoseconds / 1e9

        # Startup delay — wait for Gazebo to stabilize
        if elapsed < self.startup_delay_:
            image_file_name = os.path.join(self.image_dir_, 'back_no_action.jpg')
            bridge = CvBridge()
            cv_image = cv2.imread(image_file_name)
            image_message = bridge.cv2_to_imgmsg(cv_image, encoding='passthrough')
            self.image_publisher_.publish(image_message)
            self.trajectory_publisher_.publish(twist_msg)
            self.get_logger().info(
                f'Startup delay: {elapsed:.1f}/{self.startup_delay_:.1f}s',
                throttle_duration_sec=2.0,
            )
            return

        # Time since movement started (after startup delay)
        move_time = elapsed - self.startup_delay_

        # Look up current segment from the trajectory table
        moving = False
        for end_t, lin_x, ang_z in self.TRAJ_SEGMENTS:
            if move_time < end_t:
                twist_msg.linear.x = lin_x
                twist_msg.angular.z = ang_z
                moving = lin_x > 0.0 or ang_z != 0.0
                break
        else:
            # Past all segments — stop
            twist_msg.linear.x = 0.0
            twist_msg.angular.z = 0.0
            moving = False

        # Show Thumb_Up whenever guide is actively moving (aligns with audio "start" timing)
        if moving:
            image_file_name = os.path.join(self.image_dir_, 'back_thumbs_up.jpg')
        else:
            image_file_name = os.path.join(self.image_dir_, 'back_thumbs_down.jpg')

        bridge = CvBridge()
        cv_image = cv2.imread(image_file_name)
        image_message = bridge.cv2_to_imgmsg(cv_image, encoding='passthrough')
        self.image_publisher_.publish(image_message)
        self.trajectory_publisher_.publish(twist_msg)

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
    """Entry point for the trajectory and image publisher node."""
    rclpy.init(args=args)
    node = TrajAndImgPublisher()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
