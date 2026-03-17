#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# Quick test script for the improved latency measurement tools

echo "=================================================="
echo "ROS2 KPI - Latency Measurement Test"
echo "=================================================="
echo ""

# Check ROS2
if [ -z "$ROS_DISTRO" ]; then
    echo " ROS2 not sourced. Run: source /opt/ros/humble/setup.bash"
    exit 1
fi

echo " ROS2 $ROS_DISTRO detected"
echo ""

# Get user choice
echo "Select test mode:"
echo "  1) Roundtrip Latency Test (performance_test-style)"
echo "  2) Enhanced Monitor Test (existing functionality with new stats)"
echo "  3) Both (requires 3 terminals)"
echo ""
read -p "Choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "Starting Roundtrip Latency Test"
        echo "================================"
        echo ""
        echo "This test requires TWO terminals:"
        echo ""
        echo "Terminal 1 (Main - this one):"
        echo "  uv run latency-tester --mode Main --rate 1000 --max-runtime 30 --logfile latency_test.csv"
        echo ""
        echo "Terminal 2 (Relay):"
        echo "  source /opt/ros/humble/setup.bash"
        echo "  cd ~/Documents/ros2-kpi"
        echo "  uv run latency-tester --mode Relay"
        echo ""
        read -p "Press Enter when Terminal 2 Relay is running..."
        
        uv run latency-tester --mode Main --rate 1000 --max-runtime 30 --logfile latency_test.csv --print-console
        echo ""
        echo "Results saved to: latency_test.csv"
        ;;
        
    2)
        echo ""
        echo "Starting Enhanced Monitor"
        echo "========================="
        echo ""
        
        # Check if any ROS nodes are running
        nodes_count=$(ros2 node list 2>/dev/null | grep -v "^$" | wc -l)
        
        if [ "$nodes_count" -eq 0 ]; then
            echo "  No ROS2 nodes detected. Options:"
            echo ""
            echo "  a) Start ros-humble-wandering-gazebo-tutorial:"
            echo "     ros2 launch wandering_gazebo_tutorial wandering.launch.py"
            echo ""
            echo "  b) Start turtlesim test:"
            echo "     ros2 run turtlesim turtlesim_node"
            echo ""
            read -p "Start one of these in another terminal, then press Enter..."
        fi
        
        echo "Available nodes:"
        ros2 node list
        echo ""
        read -p "Enter node name to monitor (or press Enter for all): " target_node
        
        if [ -z "$target_node" ]; then
            uv run python src/ros2_graph_monitor.py --log-file monitor_enhanced.csv
        else
            uv run python src/ros2_graph_monitor.py --node "$target_node" --log-file monitor_enhanced.csv
        fi
        
        echo ""
        echo "Results saved to: monitor_enhanced.csv"
        ;;
        
    3)
        echo ""
        echo "Full Test Suite Requires 3 Terminals"
        echo "====================================="
        echo ""
        echo "Terminal 1 - Relay Node:"
        echo "  source /opt/ros/humble/setup.bash && cd ~/Documents/ros2-kpi"
        echo "  uv run latency-tester --mode Relay"
        echo ""
        echo "Terminal 2 - Enhanced Monitor:"
        echo "  source /opt/ros/humble/setup.bash && cd ~/Documents/ros2-kpi"
        echo "  uv run python src/ros2_graph_monitor.py --log-file full_test.csv"
        echo ""
        echo "Terminal 3 - Main Latency Test (this one):"
        echo "  uv run latency-tester --mode Main --rate 1000 --max-runtime 30 --logfile latency_test.csv"
        echo ""
        read -p "Press Enter when Terminals 1 & 2 are running..."
        
        uv run latency-tester --mode Main --rate 1000 --max-runtime 30 --logfile latency_test.csv --print-console
        
        echo ""
        echo "Results:"
        echo "  - latency_test.csv (roundtrip measurements)"
        echo "  - full_test.csv (enhanced monitor data)"
        ;;
        
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Test complete!"
echo ""
echo "To analyze results:"
echo "  # For roundtrip test"
echo "  python3 << 'EOF'"
echo "  import pandas as pd"
echo "  df = pd.read_csv('latency_test.csv', skiprows=6)"
echo "  print(df['latency_ms'].describe())"
echo "  EOF"
echo ""
echo "  # For monitor data"
echo "  python3 << 'EOF'"
echo "  import pandas as pd"
echo "  df = pd.read_csv('monitor_enhanced.csv')"
echo "  print(df[['latency_min_ms', 'latency_max_ms', 'latency_mean_ms']].describe())"
echo "  EOF"
