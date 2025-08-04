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
from std_msgs.msg import String
import math
import os
from ament_index_python.packages import get_package_share_directory


class audio_publisher(Node):
    def __init__(self):
        super().__init__("audio_publisher_node")
        # declare parameters
        self.declare_parameter("odom_topic", "/guide_robot/odom")
        self.declare_parameter("publish_frequency", 10)
        
        self.odom_topic_name_ = self.get_parameter("odom_topic").value
        self.publish_period_ = 1.0/self.get_parameter("publish_frequency").value
        
        self.odom_subscriber_ = self.create_subscription(Odometry, self.odom_topic_name_, self.odom_topic_callback, 10)
        self.audio_publisher_ = self.create_publisher(String, "audio_filename", 10)
        self.timer_ = self.create_timer(self.publish_period_, self.publish)
        self.pos_ = [0.0, 0.0, 0.0]
        self.rpy_ = (0.0, 0.0, 0.0)
        self.start_audio_published = False
        self.stop_audio_published = False
        self.get_logger().info("audio_publisher_node has been started")

    def odom_topic_callback(self, odom_msg):
        self.rpy_ = self.euler_from_quaternion(odom_msg.pose.pose.orientation.x, odom_msg.pose.pose.orientation.y, odom_msg.pose.pose.orientation.z, odom_msg.pose.pose.orientation.w)
        self.pos_ = [odom_msg.pose.pose.position.x, odom_msg.pose.pose.position.y, odom_msg.pose.pose.position.z]

    def publish(self):
        audio_filename_msg = String()
        
   
        # if (self.pos_[1] <= 0.4) and (self.pos_[1] > -0.5) and self.pos_[0] < 0.7:
        #     audio_filename_msg.data = "start-1.wav"
        if (self.pos_[1] <= 1.0) and (self.pos_[1] > -0.5) and self.pos_[0] < 1.0:
            audio_filename_msg.data = "start-1.wav"
        elif (self.pos_[1] > -1.0 and self.pos_[1] < 0.7) and (self.rpy_[2] > 0) :
            audio_filename_msg.data = "stop-1.wav"
        else:
            audio_filename_msg.data = ""
        self.audio_publisher_.publish(audio_filename_msg)
        self.get_logger().info("publishing audio file: {}".format(audio_filename_msg.data))


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
    node = audio_publisher()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()