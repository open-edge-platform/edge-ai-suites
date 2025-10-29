#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Test to check for core dumps and segmentation faults in fast_mapping_node."""

import os
import subprocess
import pytest

from test_helpers import (
    check_fast_mapping_availability,
    check_log_for_crashes,
    terminate_process_gracefully,
    wait_for_process_ready
)

LOG_FILES = ["log_exec_1.txt", "log_exec_2.txt"]


@pytest.fixture(autouse=True)
def setup_and_cleanup_core_dump_test():
    """Setup fast_mapping availability check and cleanup log files after test."""
    # Setup: Check if fast_mapping_node is available
    is_available, error_message = check_fast_mapping_availability()
    if not is_available:
        pytest.fail(error_message)

    yield

    # Cleanup: Remove log files
    for log_file in LOG_FILES:
        try:
            if os.path.exists(log_file):
                os.remove(log_file)
        except OSError:
            pass


def run_fast_mapping_node_and_check(log_file):
    """Run fast_mapping_node, log output, and check for crashes."""
    with open(log_file, "w", encoding="utf-8") as execution_log:
        with subprocess.Popen(
            ["ros2", "run", "fast_mapping", "fast_mapping_node"],
            stdout=execution_log, stderr=subprocess.STDOUT,
            start_new_session=True
        ) as process:
            wait_for_process_ready(process)
            terminate_process_gracefully(process)

    with open(log_file, "r", encoding="utf-8") as log_file_obj:
        log_content = log_file_obj.read()
        assert "fast_mapping is waiting for new frames" in log_content
        assert check_log_for_crashes(log_file), f"Crashes detected in {log_file}"


def test_fast_mapping_node_crash_check():
    """Test that fast_mapping_node does not crash or core dump on repeated runs."""
    run_fast_mapping_node_and_check(LOG_FILES[0])
    run_fast_mapping_node_and_check(LOG_FILES[1])
