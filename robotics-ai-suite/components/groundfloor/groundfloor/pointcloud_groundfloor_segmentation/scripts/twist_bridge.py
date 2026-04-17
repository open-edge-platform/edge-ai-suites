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
from geometry_msgs.msg import Twist, TwistStamped
from rclpy.qos import QoSProfile
from rclpy.type_support import check_for_type_support


class CmdVelBridge(Node):
    def __init__(self):
        super().__init__('cmd_vel_bridge')
        qos = QoSProfile(depth=10)
        self.pub = self.create_publisher(Twist, '/cmd_vel_twist', qos)

        try:
            check_for_type_support(TwistStamped)
            self.sub = self.create_subscription(
                TwistStamped, '/cmd_vel',
                self.callback_twist_stamped, qos
            )
        except RuntimeError:
            self.sub = self.create_subscription(
                Twist, '/cmd_vel', self.callback_twist, qos
            )

    def callback_twist_stamped(self, msg: TwistStamped):
        twist = Twist()
        twist.linear = msg.twist.linear
        twist.angular = msg.twist.angular
        self.pub.publish(twist)

    def callback_twist(self, msg: Twist):
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
