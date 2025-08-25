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

# Desc:  Used to achieve synchronization  and serialization in launch.py
#        

import sys
import rclpy
from rclpy.node import Node
import robot_scripts.utils as utils
import time

class WaitForNameNode(Node):
    def __init__(self):
        super().__init__('my_node')

    def wait_for_string(self, robot_name):
        self.get_logger().info(f"Waiting on {robot_name} to apear in gazebo robots list")
        while True:
            str_array = utils.call_get_parameters(None,"/gazebo", "robots")
            if robot_name in str_array.values[0].string_array_value:
                self.get_logger().info(f"{robot_name} found on gazebo robots list")
                return
            time.sleep(1.0)

def main(args=None):
    rclpy.init(args=args)
   
    node = WaitForNameNode()
    node.wait_for_string(sys.argv[1])

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

