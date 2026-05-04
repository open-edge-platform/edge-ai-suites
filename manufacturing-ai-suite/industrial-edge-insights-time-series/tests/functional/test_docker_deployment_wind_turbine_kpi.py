#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""
KPI tests for the Wind Turbine Anomaly Detection sample app.

Split out of ``test_docker_deployment_wind_turbine.py``.  See the MQTT and
OPC-UA sibling files for the functional halves of the suite.

All tests are marked with ``@pytest.mark.kpi`` so they can be selected /
deselected with ``pytest -m kpi`` or ``pytest -m 'not kpi'``.
"""

import os
import sys
import pytest
import logging

# Add parent directory to path for utils imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import docker_utils
from utils import constants

# Import the fixture directly from conftest_docker.py
pytest_plugins = ["conftest_docker"]

logger = logging.getLogger(__name__)


@pytest.mark.kpi
def test_mqtt_deployment_time_kpi(setup_wind_turbine_environment):
    """
    TC_021: Test Docker deployment time KPI for MQTT ingestion

    Verify that:
    1. MQTT deployment completes successfully with 100% success rate
    2. Average deployment time is within acceptable threshold
    3. All deployment attempts are successful
    """
    logger.info("TC_021: Testing Docker deployment time KPI for MQTT ingestion")
    context = setup_wind_turbine_environment

    success_rate, avg_time, min_time, max_time, times = docker_utils.measure_deployment_time(
        ingestion_type="mqtt",
        iterations=constants.KPI_TEST_ITERATIONS
    )

    # Verify KPIs are met
    logger.info(f"MQTT deployment KPI results: success_rate={success_rate}%, avg_time={avg_time:.2f}s, min={min_time:.2f}s, max={max_time:.2f}s")
    assert success_rate == constants.KPI_REQUIRED_SUCCESS_RATE, \
        f"Success rate {success_rate}% below required {constants.KPI_REQUIRED_SUCCESS_RATE}%"
    assert avg_time <= constants.KPI_DEPLOYMENT_TIME_THRESHOLD, \
        f"Average time {avg_time:.2f}s exceeds threshold of {constants.KPI_DEPLOYMENT_TIME_THRESHOLD}s"


@pytest.mark.kpi
def test_opcua_deployment_time_kpi(setup_wind_turbine_environment):
    """
    TC_022: Test Docker deployment time KPI for OPCUA ingestion

    Verify that:
    1. OPCUA deployment completes successfully with 100% success rate
    2. Average deployment time is within acceptable threshold
    3. All deployment attempts are successful
    """
    logger.info("TC_022: Testing Docker deployment time KPI for OPCUA ingestion")
    context = setup_wind_turbine_environment

    success_rate, avg_time, min_time, max_time, times = docker_utils.measure_deployment_time(
        ingestion_type="opcua",
        iterations=constants.KPI_TEST_ITERATIONS
    )

    # Verify KPIs are met
    logger.info(f"OPCUA deployment KPI results: success_rate={success_rate}%, avg_time={avg_time:.2f}s, min={min_time:.2f}s, max={max_time:.2f}s")
    assert success_rate == constants.KPI_REQUIRED_SUCCESS_RATE, \
        f"Success rate {success_rate}% below required {constants.KPI_REQUIRED_SUCCESS_RATE}%"
    assert avg_time <= constants.KPI_DEPLOYMENT_TIME_THRESHOLD, \
        f"Average time {avg_time:.2f}s exceeds threshold of {constants.KPI_DEPLOYMENT_TIME_THRESHOLD}s"


@pytest.mark.kpi
def test_container_sizes_kpi(setup_wind_turbine_environment):
    """
    TC_023: Test Docker container sizes after build

    Verify that:
    1. Docker build completes successfully
    2. Built image sizes are within defined threshold
    3. All expected images are created with acceptable sizes
    """
    logger.info("TC_023: Testing Docker container sizes after build")
    context = setup_wind_turbine_environment

    # Use size threshold from constants
    size_threshold = constants.CONTAINER_IMAGE_SIZE_THRESHOLD

    # First, invoke make build to create the images
    logger.info("Building Docker images...")
    build_success, build_output = docker_utils.invoke_make_build()
    logger.info(f"Docker build result: success={build_success}")
    assert build_success, f"Docker build failed: {build_output}"
    logger.info("Docker build completed successfully")

    # Now check the sizes of the built images
    logger.info("Checking Docker image sizes after build...")

    # Check image sizes for all built images (not deployed containers)
    success, message = docker_utils.check_image_sizes(
        size_threshold=size_threshold,
        check_deployed_only=False
    )
    logger.info(f"Image size check result: success={success}, message={message}")
    assert success, message


@pytest.mark.kpi
def test_build_time_kpi(setup_wind_turbine_environment):
    """
    TC_024: Test Docker build time KPI

    Verify that:
    1. Docker image build completes successfully with 100% success rate
    2. Average build time is within acceptable threshold
    3. All build attempts are successful
    """
    logger.info("TC_024: Testing Docker build time KPI")
    context = setup_wind_turbine_environment

    # Measure build time using our helper function
    success_rate, avg_time, min_time, max_time, times = docker_utils.measure_build_time(
        iterations=constants.KPI_TEST_ITERATIONS
    )

    # Verify KPIs are met
    logger.info(f"Build KPI results: success_rate={success_rate}%, avg_time={avg_time:.2f}s, min={min_time:.2f}s, max={max_time:.2f}s")
    assert success_rate == constants.KPI_REQUIRED_SUCCESS_RATE, \
        f"Build success rate {success_rate}% below required {constants.KPI_REQUIRED_SUCCESS_RATE}%"
    assert avg_time <= constants.KPI_BUILD_TIME_THRESHOLD, \
        f"Average build time {avg_time:.2f}s exceeds threshold of {constants.KPI_BUILD_TIME_THRESHOLD}s"
