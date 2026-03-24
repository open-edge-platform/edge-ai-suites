#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import sys
import pytest
import time
import subprocess
import logging
from pathlib import Path
sys.path.append(os.path.join(os.path.dirname(__file__), '../utils'))
import docker_utils
import constants

# Import the fixture directly from conftest_docker.py
pytest_plugins = ["conftest_docker"]

# Set up logger for this module
logger = logging.getLogger(__name__)


def test_long_run_stability_one_hour(setup_docker_environment):
    """
    Long run test: Run sample app for 1 hour and check for CPU/memory leaks.
    """
    logger.info("Long run test: Deploying sample app and monitoring for 1 hour.")
    context = setup_docker_environment
    context["deploy_mqtt"]()  # or context["deploy_opcua"](), adjust as needed

    # Record initial resource usage
    initial_stats = docker_utils.get_resource_usage()
    logger.info(f"Initial resource usage: {initial_stats}")

    # Run for 1 hour (3600 seconds)
    logger.info("Waiting for 1 hour to monitor resource usage...")
    docker_utils.wait_for_stability(3600)

    # Record final resource usage
    final_stats = docker_utils.get_resource_usage()
    logger.info(f"Final resource usage: {final_stats}")

    # Compare stats and assert no significant leaks (define your own threshold)
    assert docker_utils.check_resource_leak(initial_stats, final_stats, memory_leak_threshold_mb=200), \
    "Significant CPU or memory leak detected after 1 hour run."

    # Assert all containers are still running
    containers = docker_utils.get_the_deployed_containers()
    assert containers, "No containers found after 1 hour run."
    logger.info("Long run test completed successfully.")


def test_long_run_stability_one_hour_opcua(setup_docker_environment):
    """
    Long run test: Run sample app with OPCUA for 1 hour and check for CPU/memory leaks.
    """
    logger.info("Long run test (OPCUA): Deploying sample app and monitoring for 1 hour.")
    context = setup_docker_environment
    context["deploy_opcua"]()

    # Record initial resource usage
    initial_stats = docker_utils.get_resource_usage()
    logger.info(f"Initial resource usage: {initial_stats}")

    # Run for 1 hour (3600 seconds)
    logger.info("Waiting for 1 hour to monitor resource usage (OPCUA)...")
    docker_utils.wait_for_stability(3600)

    # Record final resource usage
    final_stats = docker_utils.get_resource_usage()
    logger.info(f"Final resource usage: {final_stats}")

    # Compare stats and assert no significant leaks (define your own threshold)
    assert docker_utils.check_resource_leak(initial_stats, final_stats, memory_leak_threshold_mb=200), \
        "Significant CPU or memory leak detected after 1 hour run (OPCUA)."

    # Assert all containers are still running
    containers = docker_utils.get_the_deployed_containers()
    assert containers, "No containers found after 1 hour run (OPCUA)."
    logger.info("Long run test (OPCUA) completed successfully.")