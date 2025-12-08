#!/bin/bash

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

set -e

# Check if ROS_DISTRO is provided as argument
if [ $# -eq 1 ]; then
    export ROS_DISTRO=$1
elif [ -z "$ROS_DISTRO" ]; then
    echo "Usage: $0 <ros_distro>"
    echo "Example: $0 humble"
    echo "Example: $0 jazzy"
    exit 1
fi

# Validate ROS distribution
if [[ "$ROS_DISTRO" != "humble" && "$ROS_DISTRO" != "jazzy" ]]; then
    echo "Error: Unsupported ROS distribution '$ROS_DISTRO'. Only 'humble' and 'jazzy' are supported."
    exit 1
fi

current_dir="$(pwd)"

echo "=== Installing ROS $ROS_DISTRO packages with bagfile ==="

# Update packages
apt-get update

echo "=== Installing dependencies ==="
apt-get install -y \
    "ros-${ROS_DISTRO}-dbow2" \
    nlohmann-json3-dev \
    python3-ament-package \
    "ros-${ROS_DISTRO}-image-transport-plugins"

echo "=== Installing packages in correct order ==="

echo "Available deb files:"
ls -la ./*.deb

# 1. Install msgs first
echo "Installing msgs..."
for deb in "./ros-${ROS_DISTRO}-univloc-msgs"*.deb; do
    if [ -f "$deb" ]; then
        apt-get install -y "$deb"
    fi
done

# 2. Install slam
echo "Installing slam..."
for deb in "./ros-${ROS_DISTRO}-univloc-slam-sse"*.deb; do
    if [ -f "$deb" ]; then
        apt-get install -y "$deb"
    fi
done

# 3. Install tracker
echo "Installing tracker..."
for deb in "./ros-${ROS_DISTRO}-univloc-tracker-sse"*.deb; do
    if [ -f "$deb" ]; then
        apt-get install -y "$deb"
    fi
done

# 4. Install smoke test with internal bagfile
echo "Installing smoke test..."
for deb in "./ros-${ROS_DISTRO}-univloc-tracker-smoke-test"*.deb; do
    if [ -f "$deb" ]; then
        apt-get install -y "$deb"
    fi
done

echo "=== Verifying installation ==="
REQUIRED_PACKAGES=(
    "ros-${ROS_DISTRO}-univloc-msgs"
    "ros-${ROS_DISTRO}-univloc-slam-sse"
    "ros-${ROS_DISTRO}-univloc-tracker-sse"
    "ros-${ROS_DISTRO}-univloc-tracker-smoke-test"
)

missing_packages=()
for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! dpkg -l | grep -q "^ii.*$package"; then
        missing_packages+=("$package")
    fi
done

if [ ${#missing_packages[@]} -gt 0 ]; then
    echo "❌ Missing required packages:"
    printf '  %s\n' "${missing_packages[@]}"
    echo "This might cause the smoke test to fail."
else
    echo "✅ All required packages are installed"
fi

echo "=== Checking what was installed ==="
dpkg -l | grep -E "(slam|tracker|bagfile)" | grep "${ROS_DISTRO}"

echo "=== Looking for smoke test files ==="
TEST_SCRIPT=$(find "/opt/ros/${ROS_DISTRO}" -name "test_image_transport.py" 2>/dev/null | head -1)
echo "Test script: ${TEST_SCRIPT:-NOT FOUND}"

echo "=== Looking for bagfiles ==="
BAGFILE_DIR=$(find "/opt/ros/${ROS_DISTRO}" -name "*demo-mapping*" -type d 2>/dev/null | head -1)
echo "Bagfile directory: ${BAGFILE_DIR:-NOT FOUND}"

# Check what's in the bagfile directory
if [ -n "$BAGFILE_DIR" ]; then
    echo "Contents of bagfile directory:"
    ls -la "$BAGFILE_DIR"

    # Look for .db3 file (ROS2 bagfile format)
    DB3_FILE=$(find "$BAGFILE_DIR" -name "*.db3" 2>/dev/null | head -1)
    echo "DB3 file: ${DB3_FILE:-NOT FOUND}"

    # Check for metadata.yaml (ROS2 bagfile metadata)
    METADATA_FILE=$(find "$BAGFILE_DIR" -name "metadata.yaml" 2>/dev/null | head -1)
    echo "Metadata file: ${METADATA_FILE:-NOT FOUND}"
fi

# List all potential bagfile locations
echo "All bagfile locations:"
find "/opt/ros/${ROS_DISTRO}" -name "*demo*mapping*" 2>/dev/null || echo "No demo-mapping files found"
find "/opt/ros/${ROS_DISTRO}" -name "*.db3" 2>/dev/null | head -5 || echo "No .db3 files found"

if [ -n "$TEST_SCRIPT" ] && [ -n "$BAGFILE_DIR" ]; then
    echo "=== Running smoke test ==="
    echo "Test script: $TEST_SCRIPT"
    echo "Bagfile directory: $BAGFILE_DIR"

    # shellcheck disable=SC1090
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    TEST_DIR=$(dirname "$TEST_SCRIPT")
    cd "$TEST_DIR"

    echo "Current directory: $(pwd)"
    echo "Available files in test directory:"
    ls -la

    echo "Starting smoke test..."
    python3 test_image_transport.py -r false -t 550 -b "$BAGFILE_DIR" 2>&1 | tee /tmp/cslam_smoke_test_image_transport_test.log

    TEST_EXIT_CODE=${PIPESTATUS[0]}

    echo "=== Checking test results ==="
    echo "Test exit code: $TEST_EXIT_CODE"

    if [ "$TEST_EXIT_CODE" -eq 0 ]; then
        echo "✅ Test completed successfully (exit code 0)!"
    else
        echo "❌ Test failed with exit code: $TEST_EXIT_CODE"
        echo "=== Last 20 lines of test log ==="
        tail -20 /tmp/cslam_smoke_test_image_transport_test.log
        exit 1
    fi

else
    echo "❌ Missing required files for smoke test"

    if [ -z "$TEST_SCRIPT" ]; then
        echo "Test script not found. Checking smoke test package contents:"
        dpkg -L "ros-${ROS_DISTRO}-univloc-tracker-smoke-test" 2>/dev/null || echo "Smoke test package not installed"
    fi

    if [ -z "$BAGFILE_DIR" ]; then
        echo "Bagfile directory not found. Checking bagfile package contents:"
        dpkg -L "ros-${ROS_DISTRO}-bagfile-demo-mapping" 2>/dev/null || echo "Bagfile package not installed"
    fi

    exit 1
fi

cd "${current_dir}"

echo "=== Test Results ==="
cat /tmp/cslam_smoke_test_image_transport_test.log

echo "=== Summary ==="
echo "Installed packages:"
dpkg -l | grep "${ROS_DISTRO}" | grep -E "(univloc|slam|tracker|bagfile)"
