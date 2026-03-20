#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# ROS2 Environment Setup Script
# Source this before running monitoring commands

# Check if ROS2 is installed
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
    echo "✅ ROS2 Humble sourced"
elif [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
    echo "✅ ROS2 Jazzy sourced"
else
    echo "⚠️  ROS2 not found in /opt/ros/"
    echo "Please follow the Intel Robotics AI Suite getting started guide:"
    echo "  https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html"
    exit 1
fi

# Set default ROS_DOMAIN_ID if not set
if [ -z "$ROS_DOMAIN_ID" ]; then
    export ROS_DOMAIN_ID=0
    echo "   ROS_DOMAIN_ID set to 0 (default)"
else
    echo "   ROS_DOMAIN_ID is $ROS_DOMAIN_ID"
fi

echo ""
echo "ROS2 environment ready for monitoring!"
echo "Run: make monitor-remote REMOTE_IP=<ip> REMOTE_USER=<user>"
