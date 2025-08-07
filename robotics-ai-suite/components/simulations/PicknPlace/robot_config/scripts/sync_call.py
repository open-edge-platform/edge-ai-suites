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

# Desc:  Wrapper script to perform synchronization from within launch.py.

import sys
import time
import robot_config.utils as utils

def main(args=None):
    if len(sys.argv) < 3:
        print("Please provide the event name and mode as a command-line argument.")
        sys.exit(1)
    if sys.argv[1] == 'set':
        utils.wait_for_event(sys.argv[2])
    else:
        utils.set_event(sys.argv[2])

if __name__ == '__main__':
    main()