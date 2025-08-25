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

# Desc:  Waits for specific interface (e.g topic, service and action) to be up and running.  
#        Used to achieve synchronization  and serialization in launch.py

import rclpy
import subprocess
import sys
import time
import robot_config.utils as utils

def check_interface(interface_mode, interface_name):
    print(f"Waiting for interface {interface_mode} {interface_name}")
    if interface_name.startswith('//'):
        return

    while True:
        command = ['ros2', interface_mode, 'list']
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = process.communicate()

        action_services = stdout.decode().splitlines()

        if interface_name in action_services:
            print(f"Interface {interface_mode} '{interface_name}' is up and running.")
            break

        time.sleep(1)

def main(args=None):
    rclpy.init()
    if len(sys.argv) < 3:
        print("Please provide the interface type and name as a command-line argument.")
        sys.exit(1)

    check_interface(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
