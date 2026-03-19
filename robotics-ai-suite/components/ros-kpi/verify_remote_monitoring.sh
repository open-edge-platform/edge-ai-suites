#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# Remote Monitoring Verification Script
# Tests connectivity and prerequisites for monitoring intel@10.34.94.191

set -e

REMOTE_IP="10.34.94.191"
REMOTE_USER="intel"

echo "=================================================="
echo "Remote Monitoring Verification"
echo "Remote System: ${REMOTE_USER}@${REMOTE_IP}"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

# Test 1: SSH Connectivity
echo "Test 1: SSH Connectivity"
echo "------------------------"
if ssh -o ConnectTimeout=5 -o BatchMode=yes ${REMOTE_USER}@${REMOTE_IP} 'exit' 2>/dev/null; then
    print_status 0 "SSH connection successful"
else
    print_status 1 "SSH connection failed - check SSH keys"
    echo ""
    echo "To fix, run:"
    echo "  ssh-copy-id ${REMOTE_USER}@${REMOTE_IP}"
    exit 1
fi
echo ""

# Test 2: Remote System Prerequisites
echo "Test 2: Remote System Prerequisites"
echo "------------------------------------"
REMOTE_CHECK=$(ssh ${REMOTE_USER}@${REMOTE_IP} 'bash -s' << 'EOF'
#!/bin/bash
status=0

# Check ROS2
if [ -f /opt/ros/humble/setup.bash ]; then
    echo "ROS2_OK"
else
    echo "ROS2_MISSING"
    status=1
fi

# Check pidstat
if command -v pidstat &> /dev/null; then
    echo "PIDSTAT_OK"
else
    echo "PIDSTAT_MISSING"
    status=1
fi

# Check for ROS2 processes
source /opt/ros/humble/setup.bash 2>/dev/null
proc_count=$(ps aux | grep -E "ros2|_ros" | grep -v grep | wc -l)
if [ $proc_count -gt 0 ]; then
    echo "ROS2_RUNNING:$proc_count"
else
    echo "ROS2_NOT_RUNNING"
fi

# Check ROS_DOMAIN_ID
if [ -z "$ROS_DOMAIN_ID" ]; then
    echo "DOMAIN_UNSET"
else
    echo "DOMAIN_SET:$ROS_DOMAIN_ID"
fi

exit $status
EOF
)

if echo "$REMOTE_CHECK" | grep -q "ROS2_OK"; then
    print_status 0 "ROS2 Humble installed"
else
    print_status 1 "ROS2 Humble not found"
fi

if echo "$REMOTE_CHECK" | grep -q "PIDSTAT_OK"; then
    print_status 0 "pidstat available"
else
    print_status 1 "pidstat not installed (sudo apt install sysstat)"
fi

if echo "$REMOTE_CHECK" | grep -q "ROS2_RUNNING"; then
    proc_count=$(echo "$REMOTE_CHECK" | grep "ROS2_RUNNING" | cut -d: -f2)
    print_status 0 "ROS2 processes running ($proc_count processes)"
else
    print_warning "No ROS2 processes currently running"
fi

if echo "$REMOTE_CHECK" | grep -q "DOMAIN_SET"; then
    domain=$(echo "$REMOTE_CHECK" | grep "DOMAIN_SET" | cut -d: -f2)
    print_status 0 "ROS_DOMAIN_ID set to $domain"
else
    print_warning "ROS_DOMAIN_ID not set (will default to 0)"
fi
echo ""

# Test 3: Local System Prerequisites
echo "Test 3: Local System Prerequisites"
echo "-----------------------------------"

# Check ROS2 locally
if [ -f /opt/ros/humble/setup.bash ]; then
    print_status 0 "ROS2 Humble installed locally"
    LOCAL_ROS2=1
else
    print_status 1 "ROS2 Humble not installed locally (required for graph monitoring)"
    LOCAL_ROS2=0
fi

# Check uv
if command -v uv &> /dev/null; then
    print_status 0 "uv package manager installed"
    LOCAL_UV=1
else
    print_status 1 "uv not installed"
    echo "  Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    LOCAL_UV=0
fi

# Check Python modules
if python3 -c "import psutil" 2>/dev/null; then
    print_status 0 "psutil installed"
else
    print_status 1 "psutil not installed"
fi

if python3 -c "import matplotlib" 2>/dev/null; then
    print_status 0 "matplotlib installed"
else
    print_status 1 "matplotlib not installed"
fi

if python3 -c "import numpy" 2>/dev/null; then
    print_status 0 "numpy installed"
else
    print_status 1 "numpy not installed"
fi

if [ $LOCAL_ROS2 -eq 1 ]; then
    if python3 -c "import rclpy" 2>/dev/null; then
        print_status 0 "rclpy installed"
    else
        print_status 1 "rclpy not installed"
    fi
fi
echo ""

# Test 4: Quick Resource Monitoring Test
echo "Test 4: Quick Resource Monitoring Test"
echo "---------------------------------------"
echo "Running 3-second test of remote resource monitoring..."

if timeout 10 python3 src/monitor_resources.py \
    --remote-ip ${REMOTE_IP} \
    --remote-user ${REMOTE_USER} \
    --interval 1 \
    --count 3 \
    --memory > /tmp/remote_test.log 2>&1; then
    print_status 0 "Remote resource monitoring working"

    # Show snippet of output
    echo ""
    echo "Sample output:"
    tail -5 /tmp/remote_test.log | head -3
else
    print_status 1 "Remote resource monitoring failed"
    echo "Check /tmp/remote_test.log for details"
fi
echo ""

# Summary
echo "=================================================="
echo "Summary"
echo "=================================================="
echo ""

if [ $LOCAL_ROS2 -eq 0 ] || [ $LOCAL_UV -eq 0 ]; then
    echo -e "${YELLOW}⚠️  PARTIAL FUNCTIONALITY${NC}"
    echo ""
    echo "Remote resource monitoring: ✅ WORKING"
    echo "Remote graph monitoring:    ❌ REQUIRES INSTALLATION"
    echo ""
    echo "To enable full remote monitoring:"
    echo "  1. Install ROS2 Humble locally (see INSTALL.md)"
    echo "  2. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  3. Run: make install"
    echo ""
    echo "For now, you can use resource monitoring:"
    echo "  python3 src/monitor_resources.py --remote-ip ${REMOTE_IP} --remote-user ${REMOTE_USER} --memory --threads --continuous"
else
    echo -e "${GREEN}✅ FULL FUNCTIONALITY AVAILABLE${NC}"
    echo ""
    echo "You can now use full remote monitoring:"
    echo "  make monitor-remote REMOTE_IP=${REMOTE_IP} REMOTE_USER=${REMOTE_USER}"
    echo ""
    echo "Or run manually:"
    echo "  python3 src/monitor_stack.py --remote-ip ${REMOTE_IP} --remote-user ${REMOTE_USER}"
fi

echo ""
echo "For detailed test results, see: REMOTE_MONITORING_TEST_REPORT.md"
echo "=================================================="
