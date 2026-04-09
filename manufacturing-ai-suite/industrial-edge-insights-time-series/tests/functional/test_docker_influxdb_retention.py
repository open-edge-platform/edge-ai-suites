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

def test_influxdb_data_retention_with_opcua_docker(setup_docker_environment):
    """TC_DOCKER_021: Testing InfluxDB data retention of 1 hour with OPC-UA plugin (Docker)."""
    logger.info("TC_DOCKER_021: Testing InfluxDB data retention of 1 hour with OPC-UA plugin (Docker).")
    
    # Get the context from the fixture
    context = setup_docker_environment
    
    # Start services with OPC-UA ingestion using the fixture's helper function
    logger.info("Starting services with OPC-UA ingestion")
    assert context["deploy_opcua"]() is True

    # Wait for containers to stabilize
    logger.info("Waiting for containers to stabilize...")
    time.sleep(10)

    # Check container status
    logger.info("Checking container status")
    status = docker_utils.check_make_status()
    assert status, "Containers are not running as expected"
    

    # Wait for application to run
    logger.info("Waiting for the application to run for 2 minutes...")
    time.sleep(120)

    # Check logs for INFO level
    assert docker_utils.check_loglevel_in_container("INFO") is True

    influxdb_retention_duration = "1h"
    logger.info(f"InfluxDB Retention Duration : {influxdb_retention_duration}")

    # Set duration in seconds for retention testing
    duration = 3600  # 1 hour in seconds corresponding to the retention duration
    logger.info(f"InfluxDB Retention Duration: {duration} seconds")

    # Execute InfluxDB commands
    logger.info("Executing InfluxDB commands")
    result = docker_utils.execute_influxdb_commands()
    logger.info("Verify if InfluxDB commands executed successfully for OPC-UA input plugin")
    assert result is not None and result != "", "InfluxDB commands did not execute successfully"
    

    # Get initial InfluxDB data before retention period expires
    logger.info("Getting initial InfluxDB data before retention period expires")
    response, success = docker_utils.verify_influxdb_retention_docker(response=None)
    logger.info(f"InfluxDB response for first record: {response}")

    logger.info(f"Waiting for the InfluxDB retention duration in secs to take effect... {2 * duration + 300}")
    docker_utils.wait_for_stability(2 * duration + 300)

    response1, success = docker_utils.verify_influxdb_retention_docker(response=None)
    logger.info(f"First record before retention duration: {response} and second record after retention: {response1}")
    if success and response1 is not None:
        if response1 != response:
            success = True
        elif response1 == response:
            logger.info("InfluxDB retention duration is not working as expected for opcua input plugin")
            success = False
        else:
            logger.info("Unable to fetch the data from InfluxDB for opcua input plugin")
            success = False
    else:
        logger.info("InfluxDB command is not fetched properly")
        success = False
    assert success is True, "InfluxDB retention duration is not working as expected for OPC-UA input plugin"
