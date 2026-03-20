#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# Auto-Setup Script for ROS2 KPI Toolkit
# Automatically sources ROS2 and sets up environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED=$(printf '\033[0;31m')
GREEN=$(printf '\033[0;32m')
YELLOW=$(printf '\033[1;33m')
NC=$(printf '\033[0m') # No Color

setup_ros2() {
    # Check if ROS2 is already sourced
    if [ -n "$ROS_DISTRO" ]; then
        echo -e "${GREEN}✅ ROS2 $ROS_DISTRO already sourced${NC}"
        return 0
    fi

    # Try to source ROS2
    if [ -f "/opt/ros/humble/setup.bash" ]; then
        source /opt/ros/humble/setup.bash
        echo -e "${GREEN}✅ ROS2 Humble sourced${NC}"
    elif [ -f "/opt/ros/jazzy/setup.bash" ]; then
        source /opt/ros/jazzy/setup.bash
        echo -e "${GREEN}✅ ROS2 Jazzy sourced${NC}"
    else
        echo -e "${RED}❌ ROS2 not found. Please install ROS2.${NC}"
        return 1
    fi

    # Set ROS_DOMAIN_ID if not set
    if [ -z "$ROS_DOMAIN_ID" ]; then
        export ROS_DOMAIN_ID=0
        echo -e "${YELLOW}⚙️  Set ROS_DOMAIN_ID=0${NC}"
    else
        echo -e "${GREEN}✅ ROS_DOMAIN_ID=$ROS_DOMAIN_ID${NC}"
    fi

    return 0
}

# Check if uv is available
check_uv() {
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ uv not found. Installing...${NC}"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        echo -e "${GREEN}✅ uv available${NC}"
    fi
}

# Main setup
main() {
    echo "=========================================="
    echo "ROS2 KPI Toolkit - Auto Setup"
    echo "=========================================="
    echo ""

    setup_ros2 || exit 1
    check_uv

    # Change to script directory
    cd "$SCRIPT_DIR"

    echo ""
    echo -e "${GREEN}Ready!${NC}"
    echo ""

    # Execute the command if provided
    if [ $# -gt 0 ]; then
        exec "$@"
    fi
}

main "$@"
