#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Test to verify FastMapping supports RealSense data for 2D mapping.

This a pytest-based test that validates:
1. FastMapping can process RealSense sensor data without crashing
2. The node can work with RViz 2D mapping configurations
3. Map data is published successfully when processing bag files

Test execution:
    pytest realsense_support_2d_map_test.py -v

Requirements:
    - ROS2 environment sourced
    - fast_mapping package built and available
    - ROS bag files with RealSense data at /opt/ros/${ROS_DISTRO}/share/bagfiles/spinning
"""

import os
import subprocess
import time
import pytest

from test_helpers import (
    check_fast_mapping_availability,
    start_fast_mapping_node,
    terminate_process_gracefully,
    wait_for_process_ready,
    start_ros_bag_playback,
    is_same_image,
    start_virtual_display,
    start_rviz_with_config,
    compare_images_with_gm,
)


GM_IMAGE_COMPARISON_TOLERANCE = 1000.0
IMAGE_COMPARISON_PIXEL_THRESHOLD = 0.13


@pytest.fixture(autouse=True)
def verify_fast_mapping_node():
    """Check if fast_mapping_node is available via ros2 run."""
    is_available, error_message = check_fast_mapping_availability()
    if not is_available:
        pytest.fail(error_message)
    yield


def get_required_test_files():
    """Check and return required file paths for the test."""
    # Get test paths
    test_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(test_dir, "assets")

    ros_distro = os.environ.get("ROS_DISTRO")
    if not ros_distro:
        pytest.fail("ROS_DISTRO environment variable is not set.")
    bag_file_path = f"/opt/ros/{ros_distro}/share/bagfiles/spinning"
    rviz_config_path = os.path.join(assets_dir, "rviz2_config_2d_v1.rviz")
    reference_image_path = os.path.join(assets_dir, f"rviz_reference_{ros_distro}.png")
    if not os.path.exists(bag_file_path):
        pytest.fail(
            f"ROS bag file not found at {bag_file_path}. "
            "This test requires RealSense bag data."
        )
    if not os.path.exists(rviz_config_path):
        pytest.fail(f"RViz config file not found at {rviz_config_path}")
    if not os.path.exists(reference_image_path):
        pytest.fail(f"Reference image not found at {reference_image_path}")
    return bag_file_path, rviz_config_path, reference_image_path


def test_realsense_support_2d_mapping():
    """Test FastMapping RealSense 2D mapping and RViz visualization.

    This test:
    1. Starts FastMapping node
    2. Starts RViz with 2D mapping config
    3. Plays RealSense bag data
    4. Screenshots RViz and compares with reference image
    """

    bag_file_path, rviz_config_path, reference_image_path = get_required_test_files()

    # Start fast_mapping_node in background
    fm_process = start_fast_mapping_node()

    # Start virtual display for RViz
    xvfb_process = None
    rviz_process = None
    bag_process = None

    try:
        # Wait for FastMapping node to start up
        wait_for_process_ready(fm_process)

        # Start Xvfb virtual display
        xvfb_process = start_virtual_display(display=":10.0")

        # Give Xvfb time to start
        time.sleep(2)

        # Start RViz with the 2D config
        rviz_process = start_rviz_with_config(rviz_config_path, display=":10.0")

        # Wait for RViz to start up
        time.sleep(10)

        # Start ROS bag playback
        bag_process = start_ros_bag_playback(bag_file_path, loop=False)

        # Let the bag play and mapping occur
        time.sleep(15)

        # Verify fast_mapping_node is still running (not crashed)
        assert fm_process.poll() is None, (
            "fast_mapping_node crashed during RealSense data processing"
        )

        # Take screenshot of RViz window
        screenshot_path = "/tmp/rviz_screenshot.png"
        env = os.environ.copy()
        env["DISPLAY"] = ":10.0"

        screenshot_process = subprocess.run(
            ["gm", "import", "-window", "root", screenshot_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )

        assert screenshot_process.returncode == 0, (
            f"Failed to take screenshot: {screenshot_process.stderr}"
        )
        assert os.path.exists(screenshot_path), "Screenshot file was not created"

        # Compare images using helper function
        images_similar, difference = compare_images_with_gm(
            reference_image_path,
            screenshot_path,
            tolerance=GM_IMAGE_COMPARISON_TOLERANCE  # Adjust this threshold as needed
        )

        assert is_same_image(
            reference_image_path, screenshot_path,
            pixel_threshold=IMAGE_COMPARISON_PIXEL_THRESHOLD, fail_on_size=False
        ), "is_same_image comparison failed"

        assert images_similar, (
            f"RViz visualization differs too much from reference. Difference: {difference}"
        )

        print(
            f"FastMapping RealSense 2D mapping visualization matches reference "
            f"(difference: {difference})"
        )

    finally:
        # Clean up all processes
        for process in [bag_process, rviz_process, xvfb_process]:
            terminate_process_gracefully(process)

        # Always clean up fast_mapping_node
        terminate_process_gracefully(fm_process)

        # Clean up screenshot file
        try:
            if os.path.exists("/tmp/rviz_screenshot.png"):
                os.remove("/tmp/rviz_screenshot.png")
        except OSError:
            pass
