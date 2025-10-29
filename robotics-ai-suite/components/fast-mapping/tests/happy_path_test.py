#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Test to verify FastMapping algorithm handles uninitialized CameraInfo without crashing."""

import os
import subprocess
import pytest

from test_helpers import (
    check_fast_mapping_availability,
    start_fast_mapping_node,
    terminate_process_gracefully,
    wait_for_process_ready
)


@pytest.fixture(autouse=True)
def verify_fast_mapping_node():
    """Check if fast_mapping_node is available via ros2 run."""
    # noqa: E302  # pylint: disable=R0801
    is_available, error_message = check_fast_mapping_availability()
    if not is_available:
        pytest.fail(error_message)

    yield


def test_fast_mapping_handles_empty_camera_info():
    """Test that FastMapping handles uninitialized CameraInfo messages without crashing."""
    # Start fast_mapping_node in background
    # noqa: E302  # pylint: disable=R0801
    fm_process = start_fast_mapping_node()

    try:
        # Wait for node to start up
        wait_for_process_ready(fm_process)

        # Get the path to the camera info publisher script relative to this test file
        test_dir = os.path.dirname(__file__)
        assets_dir = os.path.join(test_dir, "assets")
        camera_info_publisher_script = os.path.join(assets_dir, "publish_camera_info.py")

        # Run camera info publisher that sends empty CameraInfo and checks if node is alive
        camera_info_test_process = subprocess.run(
            ["python3", camera_info_publisher_script],
            capture_output=True, text=True, timeout=30, cwd=assets_dir, check=False
        )

        # Check that the camera info publisher script succeeded and printed "Test passed"
        assert camera_info_test_process.returncode == 0, (
            f"Camera info publisher script failed: {camera_info_test_process.stderr}"
        )
        assert "Test passed" in camera_info_test_process.stdout, (
            f"Expected 'Test passed' in output: {camera_info_test_process.stdout}"
        )

        # Verify fast_mapping_node is still running (not crashed)
        assert fm_process.poll() is None, "fast_mapping_node crashed during test"

    finally:
        # Always clean up fast_mapping_node
        terminate_process_gracefully(fm_process)
