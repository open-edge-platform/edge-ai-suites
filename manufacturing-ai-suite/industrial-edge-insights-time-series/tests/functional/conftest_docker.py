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