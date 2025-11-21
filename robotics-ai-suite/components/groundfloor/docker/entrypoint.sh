#!/bin/bash

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

set -e

# setup ros2 environment
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash

cd /ws
exec "$@"
