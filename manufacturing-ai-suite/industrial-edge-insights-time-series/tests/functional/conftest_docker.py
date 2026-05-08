#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import sys
import pytest
import time
import logging

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import docker_utils
from utils import constants
from utils import common_utils

# Set up logger
logger = logging.getLogger(__name__)

# Docker environment variables (no proxy needed)
docker_wait_time, docker_target, docker_grafana_port, docker_mqtt_port, docker_opcua_port = docker_utils.get_docker_env_values()

@pytest.fixture
def setup_docker_environment(request):
    """
    Setup fixture for Docker testing.
    
    This fixture:
    1. Creates valid credentials in the .env file
    2. Runs make build to build the Docker images
    3. Cleans up with make down after the test completes
    
    Parameters:
        request: Built-in pytest fixture containing information about the test function
        
    Yields:
        dict: A dictionary with setup information and helper functions
    """
    logger.debug(f"Setting up Docker environment for test: {request.node.name}")
    
    # Store original directory to return to it later
    original_dir = os.getcwd()

    # Step to create valid credentials in the .env file
    case = docker_utils.generate_test_credentials(case_type="valid")
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    if not docker_utils.update_env_file(env_file_path, case):
        logger.error("Failed to update .env file with credentials")
        pytest.fail("Failed to update environment file during setup")
    logger.debug("Updated .env file with valid credentials")
        
    # Create helper functions for the test to use
    def deploy_mqtt(app=None, num_of_streams=None):
        """Deploy with MQTT ingestion
        
        Args:
            app (str): Optional app parameter to specify which application to use
            num_of_streams (int): Optional number of streams parameter for multi-stream deployments
        """
        logger.debug(f"Deploying with MQTT ingestion{f' for app {app}' if app else ''}{f' with {num_of_streams} streams' if num_of_streams else ''}")
        result = docker_utils.invoke_make_up_mqtt_ingestion(app=app, num_of_streams=num_of_streams)
        if not result:
            logger.error(f"Failed to deploy MQTT ingestion{f' for app {app}' if app else ''}{f' with {num_of_streams} streams' if num_of_streams else ''}")
            pytest.fail("MQTT deployment failed during test execution")
            return False
        logger.debug(f"Successfully deployed MQTT ingestion{f' for app {app}' if app else ''}{f' with {num_of_streams} streams' if num_of_streams else ''}")
        return True
    
    def deploy_opcua(app=None, num_of_streams=None):
        """Deploy with OPC-UA ingestion
        
        Args:
            app (str): Optional app parameter to specify which application to use
            num_of_streams (int): Optional number of streams parameter for multi-stream deployments
        """
        logger.debug(f"Deploying with OPC-UA ingestion{f' for app {app}' if app else ''}{f' with {num_of_streams} streams' if num_of_streams else ''}")
        result = docker_utils.invoke_make_up_opcua_ingestion(app=app, num_of_streams=num_of_streams)
        if not result:
            logger.error(f"Failed to deploy OPC-UA ingestion{f' for app {app}' if app else ''}{f' with {num_of_streams} streams' if num_of_streams else ''}")
            pytest.fail("OPC-UA deployment failed during test execution")
            return False
        logger.debug(f"Successfully deployed OPC-UA ingestion{f' for app {app}' if app else ''}{f' with {num_of_streams} streams' if num_of_streams else ''}")
        return True
        
    # Create a context object with all relevant information and helper functions
    context = {
        "env_file_path": env_file_path,
        "credentials": case,
        "deploy_mqtt": deploy_mqtt,
        "deploy_opcua": deploy_opcua,
        "docker_wait_time": docker_wait_time,
        "docker_target": docker_target,
        "docker_grafana_port": docker_grafana_port,
        "docker_mqtt_port": docker_mqtt_port,
        "docker_opcua_port": docker_opcua_port,
    }
    
    # Yield the context to the test
    yield context
    
    # Cleanup after test is done
    logger.debug(f"Cleaning up Docker environment after test: {request.node.name}")
    
    # Run make down to clean up
    if not docker_utils.invoke_make_down():
        logger.error("Failed to clean up Docker containers")
        pytest.fail("Docker cleanup failed after test completion")
    else:
        logger.debug("Successfully cleaned up Docker containers")
    
    # Return to original directory
    os.chdir(original_dir)

@pytest.fixture
def setup_multimodal_environment(request):
    """
    Setup fixture for Multimodal Docker testing.
    
    This fixture:
    1. Creates valid credentials in the .env file for multimodal deployment
    2. Runs make up to deploy the multimodal stack
    3. Cleans up with make down after the test completes
    
    Parameters:
        request: Built-in pytest fixture containing information about the test function
        
    Yields:
        dict: A dictionary with setup information and helper functions
    """
    logger.debug(f"Setting up multimodal environment for test: {request.node.name}")
    
    # Store original directory to return to it later
    original_dir = os.getcwd()
    
    # Change to multimodal directory - use the pre-defined constant
    multimodal_dir = constants.MULTIMODAL_APPLICATION_DIRECTORY
    
    try:
        os.chdir(multimodal_dir)
        logger.debug(f"✓ Successfully changed to: {multimodal_dir}")
        
        # Step to create valid credentials in the .env file
        case = docker_utils.generate_multimodal_test_credentials(case_type="valid")
        
        # Validate that S3 credentials are present and valid
        if "S3_STORAGE_USERNAME" not in case or not case["S3_STORAGE_USERNAME"]:
            logger.error("S3_STORAGE_USERNAME is missing or empty in generated credentials")
            pytest.fail("S3_STORAGE_USERNAME missing during multimodal setup")
        if "S3_STORAGE_PASSWORD" not in case or not case["S3_STORAGE_PASSWORD"]:
            logger.error("S3_STORAGE_PASSWORD is missing or empty in generated credentials")
            pytest.fail("S3_STORAGE_PASSWORD missing during multimodal setup")
            
        logger.debug(f"Generated S3_STORAGE_USERNAME: [REDACTED]")
        
        env_file_path = os.path.join(multimodal_dir, ".env")
        if not docker_utils.update_env_file(env_file_path, case):
            logger.error("Failed to update .env file with credentials for multimodal")
            pytest.fail("Failed to update multimodal environment file during setup")
        logger.debug("Updated .env file with valid credentials for multimodal")
        
        # Update HOST_IP with system IP address for multimodal deployment
        logger.debug("Updating HOST_IP with system IP address for multimodal deployment")
        if not common_utils.update_host_ip_in_env(env_file_path):
            logger.warning("Failed to update HOST_IP in .env file, using default value")
        else:
            logger.debug("✓ Successfully updated HOST_IP with system IP address")
            
        # Create helper functions for the test to use
        def deploy_multimodal():
            """Deploy multimodal stack with vision and time series analytics"""
            logger.debug("Deploying multimodal stack")
            result = docker_utils.invoke_make_up_in_current_dir()
            if not result:
                logger.error("Failed to deploy multimodal stack")
                pytest.fail("Multimodal deployment failed during test execution")
                return False
            logger.debug("Successfully deployed multimodal stack")
            return True
        
        # Create a context object with all relevant information and helper functions
        context = {
            "env_file_path": env_file_path,
            "credentials": case,
            "deploy_multimodal": deploy_multimodal,
            "multimodal_dir": multimodal_dir,
            "docker_wait_time": docker_wait_time,
            "docker_target": docker_target,
            "docker_grafana_port": docker_grafana_port,
            "docker_mqtt_port": docker_mqtt_port,
            "docker_opcua_port": docker_opcua_port,
        }
        
        # Yield the context to the test
        yield context
        
    finally:
        # Cleanup after test is done
        logger.debug(f"Cleaning up multimodal environment after test: {request.node.name}")
        
        # Run make down to clean up (from multimodal directory)
        if not docker_utils.invoke_make_down_in_current_dir():
            logger.error("Failed to clean up multimodal Docker containers")
            pytest.fail("Multimodal Docker cleanup failed after test completion")
        else:
            logger.debug("Successfully cleaned up multimodal Docker containers")
        
        # Return to original directory
        os.chdir(original_dir)


# ---------------------------------------------------------------------------
# Wind Turbine — dedicated module-scoped fixture
# ---------------------------------------------------------------------------
# Expected containers for MQTT and OPC-UA wind turbine deployments
_WIND_MQTT_CONTAINERS = [
    constants.CONTAINERS["influxdb"]["name"],
    constants.CONTAINERS["telegraf"]["name"],
    constants.CONTAINERS["time_series_analytics"]["name"],
    constants.CONTAINERS["mqtt_broker"]["name"],
    constants.CONTAINERS["mqtt_publisher"]["name"],
]
_WIND_OPCUA_CONTAINERS = [
    constants.CONTAINERS["influxdb"]["name"],
    constants.CONTAINERS["telegraf"]["name"],
    constants.CONTAINERS["time_series_analytics"]["name"],
    constants.CONTAINERS["mqtt_broker"]["name"],
    constants.CONTAINERS["opcua_server"]["name"],
]

@pytest.fixture(scope="module")
def setup_wind_turbine_environment(request):
    """
    Module-scoped setup fixture dedicated to the Wind Turbine Anomaly Detection test suite.

    Differences from the generic ``setup_docker_environment``:
    - **Module scope** — containers are deployed once per test module and torn down
      after the last test, instead of once per test function.  This eliminates the
      ~36 make-up/make-down cycles that cause the suite to take 6 hours.
    - **Polling readiness** — uses ``wait_until_containers_up`` and
      ``wait_until_service_ready`` (HTTP health endpoint poll) instead of fixed
      ``wait_for_stability`` sleeps, mirroring the Helm ``verify_pods`` approach.
    - The ``deploy_mqtt`` / ``deploy_opcua`` helpers call the polling functions after
      each deployment so individual tests receive a ready stack immediately.

    The 180-second stability soak tests (TC_019 / TC_020) retain their own
    ``wait_for_stability(180)`` calls because the soak duration IS the assertion.

    Yields:
        dict: Context with ``deploy_mqtt``, ``deploy_opcua`` helpers and metadata.
    """
    logger.info("=== Setting up Wind Turbine module-scoped Docker environment ===")

    original_dir = os.getcwd()

    # Back up the existing .env (if any) so we can restore it on teardown and
    # avoid cross-test contamination with other suites that mutate the same file.
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    original_env_contents = None
    if os.path.exists(env_file_path):
        try:
            with open(env_file_path, "r") as _f:
                original_env_contents = _f.read()
            logger.info("[WT fixture] Backed up existing .env (%d bytes) for restore on teardown",
                        len(original_env_contents))
        except OSError as e:
            logger.warning("[WT fixture] Could not back up .env (%s); teardown will delete it", e)

    # Write valid credentials into the shared .env file once for the whole module
    case = docker_utils.generate_test_credentials(case_type="valid")
    if not docker_utils.update_env_file(env_file_path, case):
        pytest.fail("Wind Turbine fixture: failed to update .env file")

    # ------------------------------------------------------------------
    # Helper: deploy MQTT and wait until stack is actually ready
    # ------------------------------------------------------------------
    def deploy_mqtt(app=constants.WIND_SAMPLE_APP, num_of_streams=None):
        """Deploy with MQTT ingestion and poll until containers + service are ready.

        For multi-stream deployments (``num_of_streams`` set) the publisher is
        a docker-compose scaled service (``mqtt_publisher_1``, ``_2``, ...) and
        is verified separately via prefix-based counting so multi-stream
        readiness is not silently skipped.
        """
        logger.info(f"[WT fixture] Deploying MQTT (app={app}, streams={num_of_streams})")
        result = docker_utils.invoke_make_up_mqtt_ingestion(app=app, num_of_streams=num_of_streams)
        if not result:
            pytest.fail("Wind Turbine MQTT deployment failed")
            return False
        publisher_name = constants.CONTAINERS["mqtt_publisher"]["name"]
        # Base set: every container that keeps its plain name regardless of scale
        base = [c for c in _WIND_MQTT_CONTAINERS if c != publisher_name]
        # Single-stream: publisher keeps its plain name
        if num_of_streams is None:
            base.append(publisher_name)
        if not docker_utils.wait_until_containers_up(base, timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT):
            pytest.fail("Wind Turbine MQTT: containers did not come up in time")
            return False
        # Multi-stream: verify the scaled publisher replicas explicitly
        if num_of_streams is not None and int(num_of_streams) >= 1:
            if not docker_utils.wait_until_scaled_containers_up(
                publisher_name, int(num_of_streams),
                timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT,
            ):
                pytest.fail(f"Wind Turbine MQTT: only some '{publisher_name}*' replicas came up")
                return False
        if not docker_utils.wait_until_service_ready(timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT):
            pytest.fail("Wind Turbine MQTT: ts-api health endpoint did not respond in time")
            return False
        logger.info("[WT fixture] MQTT stack ready ✓")
        return True

    # ------------------------------------------------------------------
    # Helper: deploy OPC-UA and wait until stack is actually ready
    # ------------------------------------------------------------------
    def deploy_opcua(app=constants.WIND_SAMPLE_APP, num_of_streams=None):
        """Deploy with OPC-UA ingestion and poll until containers + service are ready.

        For multi-stream deployments (``num_of_streams`` set) the OPC-UA server
        is a docker-compose scaled service (``opcua_server_1``, ``_2``, ...) and
        is verified separately via prefix-based counting so multi-stream
        readiness is not silently skipped.
        """
        logger.info(f"[WT fixture] Deploying OPC-UA (app={app}, streams={num_of_streams})")
        result = docker_utils.invoke_make_up_opcua_ingestion(app=app, num_of_streams=num_of_streams)
        if not result:
            pytest.fail("Wind Turbine OPC-UA deployment failed")
            return False
        opcua_name = constants.CONTAINERS["opcua_server"]["name"]
        base = [c for c in _WIND_OPCUA_CONTAINERS if c != opcua_name]
        if num_of_streams is None:
            base.append(opcua_name)
        if not docker_utils.wait_until_containers_up(base, timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT):
            pytest.fail("Wind Turbine OPC-UA: containers did not come up in time")
            return False
        if num_of_streams is not None and int(num_of_streams) >= 1:
            if not docker_utils.wait_until_scaled_containers_up(
                opcua_name, int(num_of_streams),
                timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT,
            ):
                pytest.fail(f"Wind Turbine OPC-UA: only some '{opcua_name}*' replicas came up")
                return False
        if not docker_utils.wait_until_service_ready(timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT):
            pytest.fail("Wind Turbine OPC-UA: ts-api health endpoint did not respond in time")
            return False
        logger.info("[WT fixture] OPC-UA stack ready ✓")
        return True

    context = {
        "env_file_path": env_file_path,
        "credentials": case,
        "deploy_mqtt": deploy_mqtt,
        "deploy_opcua": deploy_opcua,
        "docker_wait_time": docker_wait_time,
        "docker_target": docker_target,
        "docker_grafana_port": docker_grafana_port,
        "docker_mqtt_port": docker_mqtt_port,
        "docker_opcua_port": docker_opcua_port,
    }

    yield context

    # ------------------------------------------------------------------
    # Module-level teardown — runs once after the last test in the module
    # ------------------------------------------------------------------
    logger.info("=== Tearing down Wind Turbine module-scoped Docker environment ===")
    if not docker_utils.invoke_make_down():
        logger.error("Wind Turbine fixture: make down failed during module teardown")
    else:
        logger.info("Wind Turbine fixture: make down completed ✓")

    # Restore the original .env contents (or remove the file if none existed)
    # so subsequent test modules in the same run start from a clean baseline.
    try:
        if original_env_contents is not None:
            with open(env_file_path, "w") as _f:
                _f.write(original_env_contents)
            logger.info("[WT fixture] Restored original .env contents")
        elif os.path.exists(env_file_path):
            os.remove(env_file_path)
            logger.info("[WT fixture] Removed .env created by this fixture")
    except OSError as e:
        logger.error("[WT fixture] Failed to restore .env: %s", e)

    os.chdir(original_dir)