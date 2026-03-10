#!/usr/bin/env python3
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

"""Trajectory and image publisher node for gesture-controlled robot demo."""

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
    """Publishes trajectory commands and simulated camera images for gesture demo."""

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
        # self.image_dir_ = self.get_parameter("image_dir").value
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
        self.start_time_ = self.get_clock().now()
        self.startup_delay_ = 10.0  # Wait 10 seconds before starting movement
        self.get_logger().info('trajectory_publisher_node has been started')

    def odom_topic_callback(self, odom_msg):
        """Process odometry updates from the robot."""
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
        """Publish trajectory commands and camera images at regular intervals."""
        twist_msg = Twist()

        # Wait for startup delay before starting movement
        elapsed_time = (self.get_clock().now() - self.start_time_).nanoseconds / 1e9
        if elapsed_time < self.startup_delay_:
            # During startup, stay still and show thumb up to prepare waffle
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            image_file_name = os.path.join(
                self.image_dir_, 'back_thumbs_up.jpg'
            )
            self.get_logger().info(
                f'Startup delay: {elapsed_time:.1f}/{self.startup_delay_:.1f}s',
                throttle_duration_sec=1.0
            )
        elif self.pos_[0] < 1.5:
            # Move forward slowly along X-axis (RS mode: stay within 1.5m range)
            twist_msg.linear.x = 0.08
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            image_file_name = os.path.join(self.image_dir_, 'back_thumbs_up.jpg')
        else:
            # Stop at x=1.5m to keep within detection range
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            image_file_name = os.path.join(self.image_dir_, 'back_thumbs_down.jpg')

        bridge = CvBridge()
        cv_image = cv2.imread(image_file_name)
        image_message = bridge.cv2_to_imgmsg(cv_image, encoding='passthrough')
        self.image_publisher_.publish(image_message)
        self.trajectory_publisher_.publish(twist_msg)
        # self.get_logger().info("Publishing trajectory")

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
    """Run the trajectory and image publisher node."""
    rclpy.init(args=args)
    node = TrajAndImgPublisher()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
