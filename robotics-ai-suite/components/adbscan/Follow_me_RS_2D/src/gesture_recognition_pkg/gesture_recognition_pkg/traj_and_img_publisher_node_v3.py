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

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import math
import os
from ament_index_python.packages import get_package_share_directory


class traj_and_img_publisher(Node):
    def __init__(self):
        super().__init__("traj_and_img_publisher_node")
        # declare parameters
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("twist_topic", "/cmd_vel")
        self.declare_parameter("publish_frequency", 10)
        self.declare_parameter("Camera_topic", "/sim_camera")
        self.odom_topic_name_ = self.get_parameter("odom_topic").value
        self.twist_topic_name_ = self.get_parameter("twist_topic").value
        self.publish_period_ = 1.0/self.get_parameter("publish_frequency").value
        self.camera_topic_name_ = self.get_parameter("Camera_topic").value
        # self.image_dir_ = self.get_parameter("image_dir").value
        self.image_dir_ = os.path.join(get_package_share_directory('gesture_recognition_pkg'), 'config','gesture_imgs')
        
        self.odom_subscriber_ = self.create_subscription(Odometry, self.odom_topic_name_, self.odom_topic_callback, 10)
        self.trajectory_publisher_ = self.create_publisher(Twist, self.twist_topic_name_, 10)
        self.image_publisher_ = self.create_publisher(Image, self.camera_topic_name_, 10)
        self.timer_ = self.create_timer(self.publish_period_, self.publish)
        self.pos_ = [0.0, 0.0, 0.0]
        self.rpy_ = (0.0, 0.0, 0.0)
        self.get_logger().info("trajectory_publisher_node has been started")

    def odom_topic_callback(self, odom_msg):
        self.rpy_ = self.euler_from_quaternion(odom_msg.pose.pose.orientation.x, odom_msg.pose.pose.orientation.y, odom_msg.pose.pose.orientation.z, odom_msg.pose.pose.orientation.w)
        self.pos_ = [odom_msg.pose.pose.position.x, odom_msg.pose.pose.position.y, odom_msg.pose.pose.position.z]

    def publish(self):
        twist_msg = Twist()
        
        if (self.pos_[1] > -0.1) and self.rpy_[2] < 0:
            twist_msg.linear.x = 0.1
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            self.get_logger().info("stage 1: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[1] > -0.5) and ((self.rpy_[2]) < -0.785 and self.rpy_[2] > -2.4):
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.2
            self.get_logger().info("stage 2: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[1] < -0.1) and (self.pos_[1] > -1.5) and self.rpy_[2] < 0 and self.rpy_[2] > -0.8:
            twist_msg.linear.x = 0.1
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            self.get_logger().info("stage 3: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[1] < -1.0) and ((self.rpy_[2]) < -0.6 and self.rpy_[2] > -1.57):
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = -0.25
            self.get_logger().info("stage 4: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[1] < -1.4) and (self.pos_[1] > -1.7) and self.rpy_[2] < 0:
            twist_msg.linear.x = 0.15
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            self.get_logger().info("stage 5: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[1] < -1.5) and (self.rpy_[2] < -1.57 or self.rpy_[2] > 2.2) :
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = -0.2
            self.get_logger().info("stage 6: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[0] < 2.8) and (self.pos_[0] > 1.7) and self.rpy_[2] > 0 and self.rpy_[2] > 1.5:
            twist_msg.linear.x = 0.1
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            self.get_logger().info("stage 7: x_pos: {}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[0] > 1.4) and self.rpy_[2] > 0.8 and self.rpy_[2] < 2.3:
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = -0.2
            self.get_logger().info("stage 8: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        elif (self.pos_[1] > -1.4) and self.pos_[1] < 1.2 and self.rpy_[2] > 0 :
            twist_msg.linear.x = 0.1
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
            self.get_logger().info("stage 9: x_pos:{}, y_pos:{}, z_orientation: {}".format(self.pos_[0], self.pos_[1], self.rpy_[2]))
        else:
            twist_msg.linear.x = 0.0
            twist_msg.linear.y = 0.0
            twist_msg.linear.z = 0.0
            twist_msg.angular.x = 0.0
            twist_msg.angular.y = 0.0
            twist_msg.angular.z = 0.0
        if self.pos_[0] > 1.7 and self.pos_[0] < 2.0 and self.rpy_[2] < 0 and self.rpy_[2] > -0.9:
            image_file_name = os.path.join(self.image_dir_, "back_thumbs_down.jpg")  
        elif self.pos_[0] < 1.7 and self.pos_[0] > 1.0 and self.rpy_[2] > 0:
            image_file_name = os.path.join(self.image_dir_, "back_thumbs_up.jpg")  
        else:
            image_file_name = os.path.join(self.image_dir_, "back_no_action.jpg")
        bridge = CvBridge()
        cv_image = cv2.imread(image_file_name)
        image_message = bridge.cv2_to_imgmsg(cv_image, encoding="passthrough")
        msg = Image()
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
     
        return (roll_x, pitch_y, yaw_z) # in radians

def main(args=None):
    rclpy.init(args= args)
    node = traj_and_img_publisher()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()
    