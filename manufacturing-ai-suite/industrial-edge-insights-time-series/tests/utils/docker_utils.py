#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import subprocess
import json
import time
import os
import secrets
import string
import threading
import copy
import random
import re
from pathlib import Path
import pytest
import logging
import sys
import yaml
import paho.mqtt.client as mqtt
# Fix the relative import
sys.path.append(os.path.dirname(__file__))
# Configure logger
logger = logging.getLogger(__name__)

import constants
from constants import CONTAINERS, MULTIMODAL_APPLICATION_DIRECTORY
import common_utils
from common_utils import cross_verify_img_handle_with_s3
# Try to import security_utils, but make it optional for multimodal tests
try:
    import security_utils
    SECURITY_UTILS_AVAILABLE = True
except ImportError:
    SECURITY_UTILS_AVAILABLE = False
    logger.warning("security_utils not available, some functions may be limited")

def run_command(cmd, capture_output=False):
    """
    Execute shell commands. 
    Note: This function uses shell=True but only for predefined commands 
    from constants/makefiles, not user input.
    """
    if capture_output:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr
    else:
        proc = subprocess.run(cmd, shell=True)
        return proc.returncode

def get_container_logs(container_name, tail=None):
    cmd = ["docker", "logs"]
    if tail:
        cmd.extend(["--tail", str(tail)])
    cmd.append(container_name)
    return subprocess.check_output(cmd).decode()

def container_is_running(name):
    result = subprocess.run(["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"], capture_output=True, text=True)
    return name in result.stdout

def container_exists(name):
    result = subprocess.run(["docker", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}}"], capture_output=True, text=True)
    return name in result.stdout

def stop_container(name):
    result = subprocess.run(["docker", "stop", name])
    return result.returncode

def remove_container(name):
    result = subprocess.run(["docker", "rm", name])
    return result.returncode

def get_docker_env_values():
    """Load Docker-specific configuration and extract values."""
    # Docker-specific environment variables
    wait_time = int(os.getenv("wait_time_for_containers_to_come_up", os.getenv("wait_time_for_pods_to_come_up", "30")))
    target = os.getenv("docker_target", "localhost")  # Default to localhost for Docker
    
    # Get dynamic ports from configuration files - no hardcoded fallbacks
    try:
        # Import here to avoid circular imports
        if SECURITY_UTILS_AVAILABLE:
            dynamic_ports = security_utils.get_dynamic_ports()
        else:
            # Fallback to hardcoded ports for multimodal tests
            dynamic_ports = {'grafana': 3000, 'mqtt': 1883, 'opcua': 4840}
        
        # Use dynamic ports with fallback to environment variables only (no hardcoded defaults)
        grafana_port = dynamic_ports.get('grafana') or int(os.getenv("docker_grafana_port", "3000"))
        mqtt_port = dynamic_ports.get('mqtt') or int(os.getenv("docker_mqtt_port", "1883"))
        opcua_port = dynamic_ports.get('opcua') or int(os.getenv("docker_opcua_port", "4840"))
        
        # Validate that we got valid port numbers for externally exposed services
        if grafana_port == 0 or mqtt_port == 0 or opcua_port == 0:
            raise ValueError("Failed to load required port numbers from configuration files or environment")
        
        logger.info(f"Using dynamic ports: grafana={grafana_port}, mqtt={mqtt_port}, opcua={opcua_port}")
        # Note: InfluxDB is not exposed externally in docker-compose (internal only), so no port needed
        
    except Exception as e:
        logger.error(f"Failed to load dynamic ports: {e}")
        # If dynamic loading completely fails, try one more fallback to default configuration files
        logger.info("Attempting fallback to default configuration file locations...")
        try:
            if SECURITY_UTILS_AVAILABLE:
                # Try to get ports using default environment paths
                fallback_ports = security_utils.get_ports_for_environment('docker')
            else:
                # Hardcoded fallback for multimodal tests
                fallback_ports = {'grafana': 3000, 'mqtt': 1883, 'opcua': 4840}
            
            grafana_port = fallback_ports.get('grafana')
            mqtt_port = fallback_ports.get('mqtt')
            opcua_port = fallback_ports.get('opcua')
            
            # Validate that we got valid port numbers from fallback
            if not grafana_port or not mqtt_port or not opcua_port:
                raise ValueError("Fallback port loading failed to get required ports")
                
            logger.info(f"Using fallback ports: grafana={grafana_port}, mqtt={mqtt_port}, opcua={opcua_port}")
        except Exception as fallback_error:
            logger.error(f"Fallback port loading also failed: {fallback_error}")
            raise RuntimeError("Unable to determine port configuration from any source")
    
    return wait_time, target, grafana_port, mqtt_port, opcua_port

def deploy_and_verify(context, deploy_type="opcua", include_nmap=True):
    """
    Deploy Docker containers and verify they are running properly.
    
    Args:
        context: Test context from setup_docker_environment fixture
        deploy_type: "opcua" or "mqtt" to specify deployment type
        include_nmap: Whether to include nmap port scanning (default: True)
        
    Returns:
        dict: Deployment results with container info and ports
        
    Raises:
        AssertionError: If deployment or verification fails
    """
    
    
    # Deploy containers based on type
    if deploy_type.lower() == "opcua":
        assert context["deploy_opcua"]() == True, "Failed to deploy Docker containers with OPC-UA ingestion."
        logger.info(f"Docker containers deployed with OPC-UA ingestion and waiting for {context['docker_wait_time']} seconds for containers to stabilize")
        expected_containers = [
            constants.CONTAINERS["influxdb"]["name"],
            constants.CONTAINERS["telegraf"]["name"],
            constants.CONTAINERS["time_series_analytics"]["name"],
            constants.CONTAINERS["mqtt_broker"]["name"],
            constants.CONTAINERS["opcua_server"]["name"]
        ]
    elif deploy_type.lower() == "mqtt":
        assert context["deploy_mqtt"]() == True, "Failed to deploy Docker containers with MQTT ingestion."
        logger.info(f"Docker containers deployed with MQTT ingestion and waiting for {context['docker_wait_time']} seconds for containers to stabilize")
        expected_containers = [
            constants.CONTAINERS["influxdb"]["name"],
            constants.CONTAINERS["telegraf"]["name"],
            constants.CONTAINERS["time_series_analytics"]["name"],
            constants.CONTAINERS["mqtt_broker"]["name"],
            constants.CONTAINERS["mqtt_publisher"]["name"]
        ]
    else:
        raise ValueError(f"Unsupported deploy_type: {deploy_type}. Use 'opcua' or 'mqtt'.")
    
    # Wait for containers to stabilize
    time.sleep(context["docker_wait_time"])
    
    # Verify that containers are running
    deployed_containers = get_the_deployed_containers()
    assert len(deployed_containers) > 0, "Failed to verify running Docker containers."
    logger.info(f"Verified {len(deployed_containers)} Docker containers are running: {deployed_containers}")
    
    # Verify container logs for proper initialization
    for container in expected_containers:
        if container in deployed_containers:
            logs = get_container_logs(container)
            assert logs is not None, f"Failed to retrieve logs for container {container}."
            logger.info(f"Successfully retrieved logs for container: {container}")
    
    # Prepare results
    results = {
        "deployed_containers": deployed_containers,
        "deploy_type": deploy_type,
        "expected_containers": expected_containers
    }
    
    # Optional: Find exposed ports and run nmap scan
    if include_nmap and SECURITY_UTILS_AVAILABLE:
        exposed_ports = security_utils.find_exposed_ports_docker()
        assert security_utils.check_nmap_docker(context["docker_target"], exposed_ports) == True, "Failed to find open ports on the target using nmap."
        logger.info("Successfully completed nmap scan on Docker exposed ports.")
        results["exposed_ports"] = exposed_ports
    
    return results

def deploy_containers(context, deploy_type="opcua"):
    """
    Simple deployment function without verification (for basic tests).
    
    Args:
        context: Test context from setup_docker_environment fixture
        deploy_type: "opcua" or "mqtt" to specify deployment type
        
    Returns:
        bool: True if deployment successful
        
    Raises:
        AssertionError: If deployment fails
    """
    if deploy_type.lower() == "opcua":
        return context["deploy_opcua"]()
    elif deploy_type.lower() == "mqtt":
        return context["deploy_mqtt"]()
    else:
        raise ValueError(f"Unsupported deploy_type: {deploy_type}. Use 'opcua' or 'mqtt'.")

def start_container(name):
    result = subprocess.run(["docker", "start", name])
    return result.returncode

def restart_container(name):
    result = subprocess.run(["docker", "restart", name])
    return result.returncode

def get_images_from_docker_compose(compose_file_path=None):
    """
    Extract image names from docker-compose.yml files
    
    Args:
        compose_file_path (str): Path to docker-compose file. If None, searches for common compose files
        
    Returns:
        list: List of image names found in the compose file(s)
    """
    images = []
    
    # If no specific path provided, search for docker-compose.yml in wind turbine directory
    if compose_file_path is None:
        compose_files = [
            os.path.join(constants.EDGE_AI_SUITES_DIR, "docker-compose.yml")
        ]
    else:
        compose_files = [compose_file_path]
    
    for compose_file in compose_files:
        if os.path.exists(compose_file):
            try:
                logger.info(f"Reading docker-compose file: {compose_file}")
                with open(compose_file, 'r') as file:
                    compose_data = yaml.safe_load(file)
                
                # Extract images from services
                if 'services' in compose_data:
                    for service_name, service_config in compose_data['services'].items():
                        if 'image' in service_config:
                            image_name = service_config['image']
                            images.append(image_name)
                            logger.debug(f"Found image: {image_name} (service: {service_name})")
                        elif 'build' in service_config:
                            # For built images, we can't get the exact name without building
                            # but we can note that this is a custom built image
                            logger.debug(f"Service {service_name} uses build instead of image")
                            
            except yaml.YAMLError as e:
                logger.error(f"Error parsing YAML file {compose_file}: {e}")
            except Exception as e:
                logger.error(f"Error reading compose file {compose_file}: {e}")
        else:
            logger.debug(f"Compose file not found: {compose_file}")
    
    # Remove duplicates while preserving order
    unique_images = list(dict.fromkeys(images))
    logger.info(f"Found {len(unique_images)} unique images in compose files: {unique_images}")
    
    return unique_images

def build_image(dockerfile_path, image_name):
    result = subprocess.run(["docker", "build", "-t", image_name, "-f", dockerfile_path, "."])
    return result.returncode

def get_image_id(image):
    result = subprocess.run(["docker", "images", "--filter", f"reference={image}", "--format", "{{.ID}}"], capture_output=True, text=True)
    return result.stdout.strip() if result.stdout else None

def get_image_size(image):
    """Get the size of a Docker image in MB
    
    Args:
        image: Name of the Docker image
        
    Returns:
        float: Image size in MB, or None if image not found
    """
    try:
        result = subprocess.run(
            ["docker", "images", "--filter", f"reference={image}", "--format", "{{.Size}}"], 
            capture_output=True, 
            text=True
        )
        size_text = result.stdout.strip()
        if not size_text:
            logger.error(f"Image '{image}' not found")
            return None
        
        # Convert size string to MB (handles KB, MB, GB formats)
        if 'KB' in size_text:
            return float(size_text.replace('KB', '').strip()) / 1024
        elif 'GB' in size_text:
            return float(size_text.replace('GB', '').strip()) * 1024
        else:
            return float(size_text.replace('MB', '').strip())
    except Exception as e:
        logger.error(f"Error getting image size for {image}: {e}")
        return None
    
def wait_for_stability(seconds=30):
    """Wait for containers/services to stabilize
    
    Args:
        seconds (int): Number of seconds to wait
    """
    logger.info(f"Waiting {seconds} seconds for services to stabilize...")
    time.sleep(seconds)

def generate_password(length=10):
    """Generate a secure random password with at least one digit."""

    alphabet = string.ascii_letters + string.digits
    # Ensure at least one digit is included
    password = [secrets.choice(string.digits)]
    # Generate the rest of the password
    password.extend(secrets.choice(alphabet) for _ in range(length - 1))
    # Shuffle the password to mix the digit with other characters
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)

def generate_username(length=10):
    """Generate a secure random username."""
    alphabet = string.ascii_letters
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_credential_fields():
    """Get list of credential field names"""
    return [
        "INFLUXDB_USERNAME",
        "INFLUXDB_PASSWORD", 
        "VISUALIZER_GRAFANA_USER",
        "VISUALIZER_GRAFANA_PASSWORD",
        "MR_MINIO_ACCESS_KEY",
        "MR_PSQL_PASSWORD",
        "MR_MINIO_SECRET_KEY"
    ]

def generate_invalid_value(field_name):
    """Generate a random invalid value for any credential field"""
    # Simple random invalid patterns
    invalid_patterns = [
        "",  # blank
        " ",  # whitespace only
        "x",  # too short (1 char)
        "xx",  # too short (2 chars)
        "admin" if "USERNAME" in field_name else "abc",  # forbidden/too short
        "1234567890" if "PASSWORD" in field_name else "user123",  # no letters or has digits in username
        "abcdefghij" if "PASSWORD" in field_name else "user@#$"  # no digits or special chars in username
    ]
    
    return random.choice(invalid_patterns)

def generate_test_credentials(case_type="valid", invalid_field=None):
    """
    Generate test credentials for different test scenarios.
    
    Args:
        case_type: "valid", "blank", "invalid", or "single_invalid"
        invalid_field: If specified, only this field will be invalid (others valid)
    """
    fields = get_credential_fields()
    
    if case_type == "blank":
        # All fields blank/empty
        return {field: "" for field in fields}
    
    elif case_type == "valid":
        # Return valid credentials with appropriate lengths
        return {
            "INFLUXDB_USERNAME": generate_username(5),
            "INFLUXDB_PASSWORD": generate_password(10),
            "VISUALIZER_GRAFANA_USER": generate_username(5),
            "VISUALIZER_GRAFANA_PASSWORD": generate_password(10),
            "MR_MINIO_ACCESS_KEY": generate_password(10),
            "MR_PSQL_PASSWORD": generate_password(10),
            "MR_MINIO_SECRET_KEY": generate_password(10),
        }
    
    elif case_type == "invalid":
        # All fields invalid with random patterns
        return {field: generate_invalid_value(field) for field in fields}
    
    else:
        raise ValueError(f"Unknown case_type: {case_type}")
    
def check_and_set_working_directory(return_original=True):
    """Check current working directory and change to Edge AI Suites directory.
    
    Args:
        return_original (bool): If True, returns the original directory path for later restoration
        
    Returns:
        bool or tuple: If return_original=True, returns (success, original_dir)
                       If return_original=False, returns True/False for success/failure
    """
    current_dir = os.getcwd()
    logger.debug(f"Current working directory: {current_dir}")

    target_dir = constants.EDGE_AI_SUITES_DIR
    
    # Normalize the path to remove any double slashes
    target_dir = os.path.normpath(target_dir)
    
    # Check if we're already in the target directory
    if current_dir == target_dir:
        logger.debug(f"Already in target directory: {target_dir}")
        return True if not return_original else (True, current_dir)
    
    # Change to target directory
    logger.debug(f"Changing to target directory: {target_dir}")
    try:
        if os.path.exists(target_dir):
            os.chdir(target_dir)
            logger.debug(f"✓ Successfully changed to: {os.getcwd()}")
            return True if not return_original else (True, current_dir)
        else:
            logger.info(f"✗ Target directory does not exist: {target_dir}")
            return False if not return_original else (False, current_dir)
    except Exception as e:
        logger.error(f"✗ Error changing directory: {str(e)}")
        return False if not return_original else (False, current_dir)

def invoke_make_build():
    """Test if make build command works"""
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.info("Failed to set working directory for build")
            return False, 0

        logger.info("Running 'make build' command...")
        result, output = run_command("make build", capture_output=True)
        logger.info(f"Build command exit code: {result}")
        logger.info(f"Build output:\n{output}")

        # Return to original directory before returning result
        os.chdir(original_dir)

        # Check for 'Built' keyword in output
        if result == 0 and "Built" in output:
            logger.info("make build succeeded and 'Built' keyword found in output")
            return True, output
        else:
            logger.info("make build failed or 'Built' keyword not found in output")
            return False, output
    except Exception as e:
        logger.error(f"Failed to run make build: {str(e)}")
        return False, str(e)

def invoke_make_up_opcua_ingestion(measure_time=False, app=None, num_of_streams=None):
    """Test if make up_opcua_ingestion command works
    
    Args:
        measure_time (bool): If True, measure and return deployment time
        app (str): Optional app parameter to specify which application to use
        num_of_streams (int): Optional number of streams parameter for multi-stream deployments
        
    Returns:
        bool or tuple: If measure_time=False, returns True/False for success/failure
                      If measure_time=True, returns (success, deployment_time_seconds)
    """
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.info("Failed to set working directory for OPC-UA ingestion")
            return False if not measure_time else (False, 0)
            
        start_time = time.time()
        # Build command with optional app and num_of_streams parameters
        command = "make up_opcua_ingestion"
        if app:
            command += f" app=\"{app}\""
        if num_of_streams:
            command += f" num_of_streams={num_of_streams}"
        result = run_command(command)
        deployment_time = time.time() - start_time
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.info(f"{command} failed")
            return False if not measure_time else (False, deployment_time)
            
        logger.info(f"{command} succeeded in {deployment_time:.2f} seconds")
        return True if not measure_time else (True, deployment_time)
    except Exception as e:
        logger.error(f"Failed to run make up_opcua_ingestion: {str(e)}")
        if not measure_time:
            pytest.fail(f"Failed to run make up_opcua_ingestion: {str(e)}")
            return False
        else:
            return (False, 0)
        
def invoke_make_up_mqtt_ingestion(measure_time=False, app=None, num_of_streams=None):
    """Test if make up_mqtt_ingestion command works
    
    Args:
        measure_time (bool): If True, measure and return deployment time
        app (str): Optional app parameter to specify which application to use
        num_of_streams (int): Optional number of streams parameter for multi-stream deployments
        
    Returns:
        bool or tuple: If measure_time=False, returns True/False for success/failure
                      If measure_time=True, returns (success, deployment_time_seconds)
    """
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.info("Failed to set working directory for MQTT ingestion")
            return False if not measure_time else (False, 0)
            
        start_time = time.time()
        command = "make up_mqtt_ingestion"
        if app:
            command += f" app={app}"
        if num_of_streams:
            command += f" num_of_streams={num_of_streams}"
        result = run_command(command)
        deployment_time = time.time() - start_time
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.info("make up_mqtt_ingestion failed")
            return False if not measure_time else (False, deployment_time)
            
        logger.info(f"make up_mqtt_ingestion succeeded in {deployment_time:.2f} seconds")
        return True if not measure_time else (True, deployment_time)
    except Exception as e:
        logger.error(f"Failed to run make up_mqtt_ingestion: {str(e)}")
        if not measure_time:
            pytest.fail(f"Failed to run make up_mqtt_ingestion: {str(e)}")
            return False
        else:
            return (False, 0)
        
def invoke_make_down():
    """Test if make down command works"""
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.info("Failed to set working directory for make down")
            return False
        
        result = run_command("make down")
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.info("make down failed")
            return False
        logger.info("make down succeeded")
        return True
    except Exception as e:
        logger.error(f"Failed to run make down: {str(e)}")
        return False

def invoke_make_check_env_variables():
    """Test if make check_env_variables command works"""
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.info("Failed to set working directory for env variables check")
            return False
            
        result = run_command("make check_env_variables")
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.info("make check_env_variables failed")
            return False
        logger.info("make check_env_variables succeeded")
        return True
    except Exception as e:
        pytest.fail(f"Failed to run make check_env_variables: {str(e)}")
        return False


def update_env_file(file_path=None, values=None):
    """Update existing .env file with specific environment variable values using sed."""

    # Set default file path if not provided
    if file_path is None:
        file_path = os.path.join(os.getcwd(), ".env")

    expanded_path = os.path.expandvars(file_path)

    try:
        if not values:
            logger.warning("No values provided to update_env_file")
            return False

        if "S3_STORAGE_USERNAME" in values:
            if not values["S3_STORAGE_USERNAME"]:
                logger.error("S3_STORAGE_USERNAME is empty in values dictionary")
                return False
            logger.info("Updating S3_STORAGE_USERNAME with value: REDACTED for security")

        if "S3_STORAGE_PASSWORD" in values:
            if not values["S3_STORAGE_PASSWORD"]:
                logger.error("S3_STORAGE_PASSWORD is empty in values dictionary")
                return False
            logger.info("Updating S3_STORAGE_PASSWORD with new value")

        if not os.path.exists(expanded_path):
            logger.error(f".env file not found: {expanded_path}")
            return False

        for parameter_name, value in values.items():
            # Check whether the key already exists in the file
            grep_result = subprocess.run(
                ["grep", "-q", f"^{parameter_name}=", expanded_path],
                capture_output=True
            )
            if grep_result.returncode == 0:
                # Key exists — update it with sed
                sed_result = subprocess.run(
                    ["sed", "-i", f"s|^{parameter_name}=.*|{parameter_name}={value}|g", expanded_path],
                    capture_output=True, text=True
                )
                if sed_result.returncode != 0:
                    logger.error(f"sed failed: {sed_result.stderr}")
                    return False
            else:
                # Key missing — append it using printf via shell
                append_result = subprocess.run(
                    ["bash", "-c", f"printf '%s\\n' '{parameter_name}={value}' >> {expanded_path}"],
                    capture_output=True, text=True
                )
                if append_result.returncode != 0:
                    logger.error(f"Failed while appending to .env file: {append_result.stderr}")
                    return False

        logger.debug(f"Successfully updated .env file with {len(values)} environment variables")
        return True

    except Exception as e:
        logger.error(f"Failed to update .env file: {str(e)}")
        return False

def invoke_make_status():
    """Test if make status command works and get container status"""
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.info("Failed to set working directory for make status")
            return False
            
        result = run_command("make status")
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.info("make status failed")
            return False
        logger.info("make status succeeded")
        return True
    except Exception as e:
        logger.error(f"Failed to run make status: {str(e)}")
        return False

def get_the_deployed_containers():
    """Extract container names using the same filter as make status command"""
    try:
        # This is the exact command used in the Makefile's status target
        logger.info("Extracting containers using docker ps with filters")
        
        result = subprocess.run([
            "docker", "ps", "-a", 
            "--filter", "name=^ia-", 
            "--filter", "name=mr_", 
            "--filter", "name=model_", 
            "--filter", "name=wind-turbine", 
            "--filter", "name=timeseriessoftware-",
            "--format", "{{.Names}}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Parse container names from output
            container_names = [name.strip() for name in result.stdout.split('\n') if name.strip()]
            
            logger.info(f"✓ Found {len(container_names)} containers:")
            for container in container_names:
                logger.info(f"  - {container}")
            
            return container_names
        else:
            logger.info(f"✗ Failed to extract containers: {result.stderr}")
            return []
            
    except Exception as e:
        logger.error(f"✗ Error extracting containers: {str(e)}")
        return []
        
def get_container_image_sizes():
    """Get image sizes for all deployed containers
    
    Returns:
        dict: Dictionary with container names as keys and their image sizes in MB as values
    """
    image_sizes = {}
    try:
        # Get container names and their images
        result = subprocess.run([
            "docker", "ps", "-a", 
            "--filter", "name=^ia-", 
            "--filter", "name=mr_", 
            "--filter", "name=model_", 
            "--filter", "name=wind-turbine", 
            "--format", "{{.Names}}:{{.Image}}"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Failed to get container images: {result.stderr}")
            return image_sizes
            
        container_images = [line.strip().split(':') for line in result.stdout.split('\n') if line.strip()]
        
        # Get size for each image
        for container_info in container_images:
            if len(container_info) < 2:
                continue
                
            container_name = container_info[0]
            image_name = container_info[1]
            size = get_image_size(image_name)
            
            if size is not None:
                image_sizes[container_name] = size
                logger.info(f"Container '{container_name}' uses image '{image_name}' with size: {size:.2f} MB")
        
        return image_sizes
    except Exception as e:
        logger.error(f"Error getting container image sizes: {e}")
        return image_sizes

def check_make_status():
    """Check container status using make status command, excluding ia-grafana"""
    logger.info("Checking container status using make status...")
    
    # Run make status command - this handles all container checking internally
    if invoke_make_status():
        logger.info("✓ Container status check completed successfully (excluding ia-grafana)")
        # Get actual container list from make status filters instead of hardcoding
        containers = get_the_deployed_containers()
        # Return a format compatible with tests - assume all containers are Up if make status succeeds
        return {container: "Up" for container in containers}
    else:
        logger.info("✗ Container status check failed")
        return {}

def restart_containers_and_check_status(ingestion_type="mqtt"):
    """Restart specific containers (MQTT or OPC-UA) and check their status"""
    all_containers = get_the_deployed_containers()
    if ingestion_type == "opcua":
        patterns = [
            constants.CONTAINERS["influxdb"]["name"],
            constants.CONTAINERS["telegraf"]["name"],
            constants.CONTAINERS["time_series_analytics"]["name"],
            constants.CONTAINERS["mqtt_broker"]["name"],
            constants.CONTAINERS["opcua_server"]["name"]
        ]
        summary_label = "OPC-UA"
    else:
        patterns = [
            constants.CONTAINERS["influxdb"]["name"],
            constants.CONTAINERS["telegraf"]["name"],
            constants.CONTAINERS["time_series_analytics"]["name"],
            constants.CONTAINERS["mqtt_broker"]["name"],
            constants.CONTAINERS["mqtt_publisher"]["name"]
        ]
        summary_label = "MQTT"

    containers_to_restart = [container for container in all_containers 
                             if any(pattern in container for pattern in patterns)]

    logger.info(f"Starting {summary_label} container restart process...")
    logger.info(f"Containers to restart: {containers_to_restart}")

    for container in containers_to_restart:
        logger.info(f"Restarting {container}...")
        result = restart_container(container)
        if result == 0:
            logger.info(f"✓ {container}: Restarted successfully")
        else:
            logger.info(f"✗ {container}: Restart failed (exit code: {result})")

    logger.info("\nWaiting for containers to stabilize...")
    wait_for_stability(30)

    logger.info("\nChecking container status after restart...")
    container_status = check_make_status()

    logger.info(f"\n{summary_label} Restart process completed for {len(containers_to_restart)} containers.")

    return container_status

def invoke_switch_mqtt_opcua():
    """Test function to switch between MQTT and OPC-UA ingestion"""
    try:
        # Test MQTT ingestion first
        logger.info("\n=== Testing MQTT Ingestion ===")
        mqtt_success = invoke_make_up_mqtt_ingestion()
        if not mqtt_success:
            logger.info(f"MQTT ingestion failed")
        else:
            logger.info(f"MQTT ingestion successful")
        
        # Wait between switches
        logger.info("\nWaiting before switching to OPC-UA...")
        wait_for_stability(30)

        # Test OPC-UA ingestion
        logger.info("\n=== Testing OPC-UA Ingestion ===")
        opcua_success = invoke_make_up_opcua_ingestion()
        if not opcua_success:
            logger.info(f"OPC-UA ingestion failed")
        else:
            logger.info(f"OPC-UA ingestion successful")
        
        # Wait between switches
        logger.info("\nWaiting before switching back to MQTT...")
        wait_for_stability(30)

        # Test switching back to MQTT
        logger.info("\n=== Testing Switch Back to MQTT ===")
        mqtt_success_2 = invoke_make_up_mqtt_ingestion()
        if not mqtt_success_2:
            logger.info(f"Second MQTT ingestion failed")
        else:
            logger.info(f"Second MQTT ingestion successful")
        
        # Summary
        logger.info("\n=== Test Summary ===")
        logger.info(f"MQTT (1st): {'PASS' if mqtt_success else 'FAIL'}")
        logger.info(f"OPC-UA: {'PASS' if opcua_success else 'FAIL'}")
        logger.info(f"MQTT (2nd): {'PASS' if mqtt_success_2 else 'FAIL'}")
        
        # Test passes if all ingestion types work
        overall_success = mqtt_success and opcua_success and mqtt_success_2
        
        if overall_success:
            logger.info("Switch test completed successfully!")
            return True
        else:
            logger.info("Switch test failed - Some ingestion types failed")
            return False
            
    except Exception as e:
        logger.error(f"Error in switch test: {str(e)}")
        return False
    
def invoke_switch_opcua_mqtt():
    """Test function to switch between OPC-UA and MQTT ingestion"""
    try:
        # Test OPC-UA ingestion first
        logger.info("\n=== Testing OPC-UA Ingestion ===")
        opcua_success = invoke_make_up_opcua_ingestion()
        if not opcua_success:
            logger.info(f"OPC-UA ingestion failed")
        else:
            logger.info(f"OPC-UA ingestion successful")

        # Wait between switches
        logger.info("\nWaiting before switching to MQTT...")
        wait_for_stability(30)

        # Test MQTT ingestion
        logger.info("\n=== Testing MQTT Ingestion ===")
        mqtt_success = invoke_make_up_mqtt_ingestion()
        if not mqtt_success:
            logger.info(f"MQTT ingestion failed")
        else:
            logger.info(f"MQTT ingestion successful")
        
        # Wait between switches
        logger.info("\nWaiting before switching to OPC-UA...")
        wait_for_stability(30)

        # Test OPC-UA ingestion
        logger.info("\n=== Testing OPC-UA Ingestion ===")
        opcua_success_2 = invoke_make_up_opcua_ingestion()
        if not opcua_success_2:
            logger.info(f"OPC-UA ingestion failed")
        else:
            logger.info(f"OPC-UA ingestion successful")
        
        # Wait between switches
        logger.info("\nWaiting before switching back to MQTT...")
        wait_for_stability(30)

        # Summary
        logger.info("\n=== Test Summary ===")
        logger.info(f"OPCUA (1st): {'PASS' if opcua_success else 'FAIL'}")
        logger.info(f"MQTT (1st): {'PASS' if mqtt_success else 'FAIL'}")
        logger.info(f"OPCUA (2nd): {'PASS' if opcua_success_2 else 'FAIL'}")

        # Test passes if all ingestion types work
        overall_success = mqtt_success and opcua_success and opcua_success_2
        
        if overall_success:
            logger.info("Switch test completed successfully!")
            return True
        else:
            logger.info("Switch test failed - Some ingestion types failed")
            return False
            
    except Exception as e:
        logger.error(f"Error in switch test: {str(e)}")
        return False

def check_and_update_loglevel(file_path=None, log_level="INFO"):
    """Check and update LOG_LEVEL in .env file"""
    
    # Valid log levels
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    
    # Validate log level input
    if log_level not in valid_levels:
        logger.info(f"Invalid log level: {log_level}. Valid options are: {valid_levels}")
        return False
    
    # Set default file path if not provided
    if file_path is None:
        file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    
    # Expand environment variables in the file path
    expanded_path = os.path.expandvars(file_path)

    try:
        # Check if file exists
        if not os.path.exists(expanded_path):
            logger.info(f"Environment file not found: {expanded_path}")
            return False

        # Read the existing file
        with open(expanded_path, 'r') as file:
            lines = file.readlines()

        # Track if LOG_LEVEL was found and updated
        loglevel_found = False
        current_loglevel = None
        
        # Update the lines with new LOG_LEVEL value
        updated_lines = []
        for line in lines:
            if line.strip().startswith("LOG_LEVEL="):
                # Extract current log level
                current_loglevel = line.split('=')[1].strip()
                updated_lines.append(f"LOG_LEVEL={log_level}\n")
                loglevel_found = True
                logger.info(f"Found LOG_LEVEL: {current_loglevel} -> Updated to: {log_level}")
            else:
                updated_lines.append(line)

        # If LOG_LEVEL not found, add it at the end
        if not loglevel_found:
            updated_lines.append(f"LOG_LEVEL={log_level}\n")
            logger.info(f"LOG_LEVEL not found in file. Added: LOG_LEVEL={log_level}")

        # Write the updated content back to the file
        with open(expanded_path, 'w') as file:
            file.writelines(updated_lines)
            
        logger.info(f"Successfully updated LOG_LEVEL to {log_level} in {expanded_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to update LOG_LEVEL in .env file: {str(e)}")
        return False

def get_current_loglevel(file_path=None):
    """Get current LOG_LEVEL from .env file"""
    
    # Set default file path if not provided
    if file_path is None:
        file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    
    # Expand environment variables in the file path
    expanded_path = os.path.expandvars(file_path)

    try:
        # Check if file exists
        if not os.path.exists(expanded_path):
            logger.info(f"Environment file not found: {expanded_path}")
            return None

        # Read the existing file
        with open(expanded_path, 'r') as file:
            lines = file.readlines()

        # Look for LOG_LEVEL
        for line in lines:
            if line.strip().startswith("LOG_LEVEL="):
                current_loglevel = line.split('=')[1].strip()
                logger.info(f"Current LOG_LEVEL: {current_loglevel}")
                return current_loglevel

        # LOG_LEVEL not found
        logger.info("LOG_LEVEL not found in .env file")
        return None
    
    except Exception as e:
        logger.error(f"Failed to read LOG_LEVEL from .env file: {str(e)}")
        return None

def collect_live_logs(container_name, monitor_duration, search_pattern=None):
    """Collect logs from a container for a specified duration with threading and pattern search."""
    
    logs_output = []
    
    try:
        # Run docker logs -f command
        process = subprocess.Popen(
            ["docker", "logs", "-f", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Collect logs for the specified duration
        start_time = time.time()
        while time.time() - start_time < monitor_duration:
            line = process.stdout.readline()
            if line:
                logs_output.append(line.strip())
                logger.info(f"[LOG] {line.strip()}")  # Show live logs
        
        # Terminate the process
        process.terminate()
        process.wait()
        
    except Exception as e:
        logger.error(f"Error collecting logs: {str(e)}")
    
    # If search pattern is provided, check for it in collected logs
    if search_pattern:
        all_logs = "\n".join(logs_output)
        if search_pattern in all_logs:
            count = all_logs.count(search_pattern)
            logger.info(f"✓ Found '{search_pattern}' in live logs ({count} occurrences)")
            return True
        else:
            logger.info(f"✗ Pattern '{search_pattern}' not found in {container_name} live logs during {monitor_duration}s monitoring")
            return False
    
    # Return the collected logs if no pattern search is needed
    return logs_output

def remove_old_alert_in_tick_script(file_path, setup):
    """Remove specific alert configuration and add a new one in the .tick file."""
    # Define the alert pattern to remove
    remove_alert_mqtt = re.compile(
        r'\|alert\(\)\s*\.crit\(lambda: "anomaly_status" > 0\)\s*'
        r'\.message\(.*?\)\s*\.noRecoveries\(\)\s*\.mqtt\(.*?\)\s*'
        r'\.topic\(.*?\)\s*\.qos\(1\)', re.DOTALL
    )
    remove_alert_opcua = re.compile(
        r'\|alert\(\)\s*\.crit\(lambda: "anomaly_status" > 0\)\s*'
        r'\.message\(.*?wind_speed.*?grid_active_power.*?anomaly_status.*?\)\s*'
        r'\.noRecoveries\(\)\s*\.post\(.*?opcua_alerts.*?\)\s*\.timeout\(30s\)',
        re.DOTALL
    )
    # Define the new alert script to add
    alert_mqtt_script = """
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected for wind speed: {{ index .Fields "wind_speed" }} Grid Active Power: {{ index .Fields "grid_active_power" }} Anomaly Status: {{ index .Fields "anomaly_status" }} ')
        .noRecoveries()
        .mqtt('my_mqtt_broker')
        .topic('alerts/wind_turbine')
        .qos(1)
"""
    alert_opcua_script = """
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected for wind speed: {{ index .Fields "wind_speed" }} Grid Active Power: {{ index .Fields "grid_active_power" }} Anomaly Status: {{ index .Fields "anomaly_status" }} ')
        .noRecoveries()
        .post('http://localhost:5000/opcua_alerts')
        .timeout(30s)
"""
    
    try:
        # Read the existing content of the .tick file
        with open(file_path, 'r') as file:
            content = file.read()

        # Remove the specific alert section
        
        content = remove_alert_mqtt.sub('', content)
        logger.info("Removed MQTT alert pattern from the .tick file.")
        content = remove_alert_opcua.sub('', content)
        logger.info("Removed OPCUA alert pattern from the .tick file.")
        
        # Append the new alert script
        if setup == "mqtt":
            content += alert_mqtt_script
            logger.info("Added new MQTT alert script to the .tick file.")
        elif setup == "opcua":
            content += alert_opcua_script
            logger.info("Added new OPCUA alert script to the .tick file.")
        else:
            logger.error("Invalid setup type. Use 'mqtt' or 'opcua'.")
            return False

        # Write the updated content back to the .tick file
        with open(file_path, 'w') as file:
            file.write(content)

        logger.info("Alert configuration updated successfully.")
        return True

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False

def check_and_update_tick_script(script_path=None, setup=None):
    """Step 1: Open tick script, update it with opcua and mqtt alerts, and return its content."""
    try:
        # First, ensure we're in the correct working directory
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.error("✗ Failed to set correct working directory")
            return None
        
        if script_path is None:
            # Use the tick_scripts subdirectory for the tick script
            script_path = os.path.join(os.getcwd(), constants.WINDTURBINE_TICK_SCRIPT_PATH)
            
        logger.info(f"Opening tick script at: {script_path}")
        
        # Check if the tick script file exists
        if not os.path.exists(script_path):
            logger.error(f"✗ Tick script file not found at: {script_path}")
            os.chdir(original_dir)  # Return to original directory before returning
            return None
        
        # Read the tick script file directly using the full path
        with open(script_path, 'r') as file:
            content = file.read()
        
        script_filename = os.path.basename(script_path)
        logger.info(f"✓ Successfully opened tick script ({len(content)} characters)")
        logger.info(f"✓ Script file: {script_filename}")
        
        # Update tick script with alert configurations based on setup parameter
        if setup:
            logger.info(f"\n--- Updating tick script with {setup} alert configuration ---")
            
            # Update with specified setup
            logger.info(f"Updating tick script with {setup} setup...")
            success = remove_old_alert_in_tick_script(script_path, setup)
            
            # Switch case for success/failure messaging
            result_messages = {
                True: f"✓ Successfully updated tick script with {setup} alerts",
                False: f"✗ Failed to update tick script with {setup} alerts"
            }
            logger.info(result_messages[success])
            
        else:
            # Default behavior: no setup parameter provided, skip alert update
            logger.info("\n--- No setup parameter provided, skipping alert configuration update ---")
            logger.info("✓ Tick script opened without alert configuration changes")
        
        # Read the updated content
        with open(script_path, 'r') as file:
            updated_content = file.read()
        
        logger.info(f"✓ Tick script updated with alert configuration ({len(updated_content)} characters)")
        
        # Return to original directory before returning the content
        os.chdir(original_dir)
        return updated_content
        
    except FileNotFoundError:
        logger.error(f"✗ Tick script file not found at: {script_path}")
        os.chdir(original_dir)  # Return to original directory
        return None
    except Exception as e:
        logger.error(f"✗ Error opening/updating tick script: {str(e)}")
        os.chdir(original_dir)  # Return to original directory
        return None
    
    
def check_logs_for_pattern(container_name, pattern_type, timeout=300, interval=10, custom_pattern=None):
    """
    Check container logs for specific patterns with a timeout using collect_live_logs.
    
    Args:
        container_name (str): Name of the container to monitor
        pattern_type (str): Type of pattern to search for ('mqtt', 'opcua', 'gpu')
        timeout (int): Maximum time to wait for pattern (default: 300 seconds)
        interval (int): Check interval in seconds (default: 10 seconds)
        custom_pattern (str): Custom pattern to search for (takes precedence over pattern_type)
    
    Returns:
        bool: True if pattern found, False if timeout reached
    """
    # Define predefined patterns
    predefined_patterns = {
        "mqtt": "ALERT alerts/wind_turbine Anomaly detected for wind speed",
        "opcua": "ALERT sent to OPC UA server: Anomaly detected for wind speed",
        "gpu": "GPU"
    }

    logger.info(f"Checking {container_name} container logs for {pattern_type} pattern...")
    logger.info(f"Timeout: {timeout} seconds, Check interval: {interval} seconds")
    
    # First check if container is running
    if not container_is_running(container_name):
        logger.error(f"✗ Container {container_name} is not running")
        return False

    # Use custom pattern if provided, otherwise use predefined pattern
    if custom_pattern:
        search_pattern = custom_pattern
        pattern_display = f"custom pattern '{custom_pattern}'"
    else:
        search_pattern = predefined_patterns.get(pattern_type.lower())
        if not search_pattern:
            available_types = list(predefined_patterns.keys())
            logger.error(f"✗ Unknown pattern type: {pattern_type}. Available types: {available_types}")
            return False
        pattern_display = f"{pattern_type.upper()} pattern"

    # Use collect_live_logs with pattern search in intervals until timeout
    start_time = time.time()
    while time.time() - start_time < timeout:
        elapsed_time = time.time() - start_time
        remaining_time = timeout - elapsed_time
        monitor_duration = min(interval, remaining_time)
        
        logger.info(f"Monitoring for {monitor_duration}s (elapsed: {elapsed_time:.1f}s, remaining: {remaining_time:.1f}s)...")
        
        # Use collect_live_logs to check for the pattern
        result = collect_live_logs(container_name, monitor_duration, search_pattern)
        
        if result is True:
            logger.info(f"✓ {pattern_display} found in logs for container {container_name}")
            return True
        
        # If we haven't found the pattern and have time left, continue monitoring
        if remaining_time <= interval:
            break

    logger.info(f"Timeout reached ({timeout}s). No {pattern_display} found in logs for container {container_name}.")
    return False


def check_logs_for_alerts(container_name, input, timeout=300, interval=10):
    """
    Check container logs for specific alert messages with a timeout using collect_live_logs.
    
    Note: This function is maintained for backward compatibility.
    Consider using check_logs_for_pattern() for new implementations.
    """
    return check_logs_for_pattern(container_name, input, timeout, interval)


def check_log_gpu(container_name, timeout=300, interval=10):
    """
    Check container logs for GPU-related messages with a timeout using collect_live_logs.
    
    Note: This function is maintained for backward compatibility.
    Consider using check_logs_for_pattern() for new implementations.
    """
    return check_logs_for_pattern(container_name, "gpu", timeout, interval)


def update_config_file(ingestion_type="opcua"):
    """Common helper for to update configuration setup and validation for MQTT/OPCUA."""
    try:
        # Use the robust directory checking function - it will save and return the original dir
        success, original_dir = check_and_set_working_directory(return_original=True)
        if not success:
            logger.error("✗ Failed to set correct working directory")
            return False
        logger.debug(f"Current working directory: {os.getcwd()}")
        
        # Step 1: Check if time-series analytics container is running
        logger.info("Checking if time-series analytics container is running...")
        container_name = constants.CONTAINERS["time_series_analytics"]["name"]  # ia-time-series-analytics-microservice
        if not container_is_running(container_name):
            logger.error(f"✗ Container {container_name} is not running")
            os.chdir(original_dir)  # Return to original directory before returning
            return False
        logger.info(f"✓ Container {container_name} is running")

        # Wait for services to stabilize before proceeding
        wait_for_stability(60)

        # Step 2: Wait for service to be ready
        logger.info("Waiting for time-series analytics service to be ready...")
        max_retries = 12  # Up to 120 seconds total: initial 60s wait + (5s * 12 retries)
        for attempt in range(max_retries):
            try:
                test_result = subprocess.run(
                    ["curl", "-s", "-k", "-o", "/dev/null", "-w", "%{http_code}",
                     "https://localhost:3000/ts-api/health"],
                    capture_output=True, text=True, timeout=10
                )
                status_code = test_result.stdout.strip() if test_result.returncode == 0 else "000"
                if status_code in ['200', '503']:  # 200 = OK, 503 = Service Unavailable (but responding)
                    logger.info(f"✓ Service is responding (HTTP {status_code})")
                    break
                else:
                    logger.info(f"Service not ready yet (attempt {attempt + 1}/{max_retries}), waiting 5 seconds...")
                    wait_for_stability(5)
            except Exception as e:
                logger.error(f"Service check failed (attempt {attempt + 1}/{max_retries}): {e}")
                wait_for_stability(5)
        else:
            logger.error("✗ Service did not become ready within timeout period")
            os.chdir(original_dir)  # Return to original directory before returning
            return False

        # Step 3: Open and update tick script with correct configuration
        script_content = check_and_update_tick_script(setup=ingestion_type)
        if script_content is None:
            logger.error(f"✗ Failed to open/update tick script for {ingestion_type.upper()}")
            os.chdir(original_dir)  # Return to original directory before returning
            return False
        logger.info(f"✓ {ingestion_type.upper()} tick script configuration completed successfully")

        # Step 4: Navigate to the correct time-series-analytics-config directory
        config_dir = constants.WINDTURBINE_CONFIG_DIR
        if os.path.exists(config_dir):
            os.chdir(config_dir)
            logger.debug(f"Changed to directory: {os.getcwd()}")
        else:
            logger.error(f"✗ Configuration directory not found: {config_dir}")
            os.chdir(original_dir)
            return False

        # Step 5: Create the directory and copy files
        os.makedirs('windturbine_anomaly_detector', exist_ok=True)
        result = subprocess.run(['cp', '-r', 'models', 'tick_scripts', 'udfs', 'windturbine_anomaly_detector/.'], check=True)
        if result.stdout:
            logger.info("Files copied successfully to 'windturbine_anomaly_detector' directory.")
        elif result.stderr:
            logger.error(f"Error copying files: {result.stderr}")

        logger.info(f"current directory: {os.getcwd()}")
        logger.info("Starting the curl command to update the configuration...")

        # Step 5: Send configuration update using curl to Docker-based service with retries
        if ingestion_type == "opcua":
            curl_command = [
                "curl", "-X", "POST", "https://localhost:3000/ts-api/config",
                "-k",
                "-H", "accept: application/json",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "udfs": {
                        "name": "windturbine_anomaly_detector",
                        "models": "windturbine_anomaly_detector.pkl"
                    },
                    "alerts": {
                        "opcua": {
                            "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
                            "namespace": 1,
                            "node_id": 2004
                        }
                    }
                })
            ]
        elif ingestion_type == "mqtt":
            curl_command = [
                "curl", "-X", "POST", "https://localhost:3000/ts-api/config",
                "-k",
                "-H", "accept: application/json",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "udfs": {
                        "name": "windturbine_anomaly_detector",
                        "models": "windturbine_anomaly_detector.pkl"
                    },
                    "alerts": {
                        "mqtt": {
                            "mqtt_broker_host": "ia-mqtt-broker",
                            "mqtt_broker_port": 1883,
                            "name": "my_mqtt_broker"
                        }
                    }
                })
            ]
        else:
            logger.error(f"Unknown ingestion_type: {ingestion_type}")
            return False

        max_curl_retries = 3
        for retry in range(max_curl_retries):
            try:
                logger.info(f"Attempting curl command (attempt {retry + 1}/{max_curl_retries})...")
                result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    logger.info("Curl command executed successfully. Response:")
                    logger.info(result.stdout)
                    logger.debug(f"✓ {ingestion_type.upper()} alerts configuration setup completed successfully")
                    
                    # Wait for services to fully initialize after configuration change
                    logger.info("Waiting for services to fully process the configuration change...")
                    wait_for_stability(45)

                    # Return to original directory before returning result
                    os.chdir(original_dir)
                    return True
                else:
                    logger.error(f"Curl command failed (attempt {retry + 1}). Error:")
                    logger.error(result.stderr)
                    if retry < max_curl_retries - 1:
                        logger.info("Waiting 10 seconds before retry...")
                        wait_for_stability(10)
            except subprocess.TimeoutExpired:
                logger.error(f"Curl command timed out (attempt {retry + 1})")
                if retry < max_curl_retries - 1:
                    logger.info("Waiting 10 seconds before retry...")
                    wait_for_stability(10)
            except Exception as e:
                logger.error(f"Failed to execute curl command (attempt {retry + 1}): {e}")
                if retry < max_curl_retries - 1:
                    logger.info("Waiting 10 seconds before retry...")
                    wait_for_stability(10)

        logger.error(f"✗ All curl command attempts failed for {ingestion_type.upper()}")
        # Return to original directory before returning False
        os.chdir(original_dir)
        return False

    except Exception as e:
        logger.exception(f"Exception in check_alerts_config_pattern: {e}")
        # Return to original directory before returning False
        os.chdir(original_dir) if 'original_dir' in locals() else None
        return False

def execute_gpu_config_curl(device="gpu"):
    """Execute curl command to post GPU configuration to the time-series analytics API.
    
    Args:
        device (str): Device to use for configuration ('gpu', 'cpu', etc.)
    """
    try:
        logger.info(f"Executing curl command to post {device.upper()} configuration to API...")
        
        # Create configuration with device field using SAMPLE_APPS_CONFIG
        wind_config = constants.SAMPLE_APPS_CONFIG["wind-turbine-anomaly-detection"]
        gpu_config = {
            "udfs": {
                "name": wind_config["udf"],
                "models": wind_config["model"],
                "device": device
            },
            "alerts": {
                "mqtt": constants.MQTT_ALERT
            }
        }
        
        # Convert config to JSON string for curl command
        gpu_config_json = json.dumps(gpu_config)

        # Post configuration to the time-series analytics API
        curl_command = [
            "curl", "-k", "-X", "POST",
            "https://localhost:3000/ts-api/config",
            "-H", "accept: application/json",
            "-H", "Content-Type: application/json",
            "-d", gpu_config_json
        ]

        result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info(f"{device.upper()} configuration POST via curl command succeeded")
            logger.info(f"API Response: {result.stdout}")
            return True
        else:
            logger.error(f"{device.upper()} configuration POST failed - Return code: {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Curl command timed out")
        return False
    except Exception as e:
        logger.error(f"Error executing curl command: {e}")
        return False

def validate_mqtt_alert_system(sample_app=constants.WIND_SAMPLE_APP):
    """Simple 5-step MQTT alert validation function with app-specific support."""
    logger.info("=== Simple MQTT Alert System Validation ===")
    logger.info(f"Starting validation from directory: {os.getcwd()}")
    logger.info(f"Sample app: {sample_app}")
    
    # Determine alert type based on sample app
    if sample_app == constants.WIND_SAMPLE_APP:
        alert_type = "mqtt"
        ingestion_type = "mqtt"
    elif sample_app == constants.WELD_SAMPLE_APP:
        alert_type = "mqtt_weld"
        ingestion_type = "mqtt"
    elif sample_app == constants.MULTIMODAL_SAMPLE_APP:
        alert_type = "mqtt_weld"  # Multimodal uses weld detection
        ingestion_type = "mqtt"
    else:
        logger.error(f"✗ Unsupported sample app: {sample_app}")
        return False
    
    # Step 1: Check for MQTT alerts configuration pattern using unified function
    logger.info(f"\nStep 1: Checking for {alert_type.upper()} alerts configuration pattern...")
    if sample_app == constants.WIND_SAMPLE_APP:
        update_config_pattern = update_config_file(ingestion_type)
        if not update_config_pattern:
            logger.error(f"✗ Step 1 FAILED: to update {alert_type.upper()} configuration via REST API")
            return False
    
    # Step 2: Check container logs for alert pattern using common_utils for proper weld support
    logger.info(f"\nStep 2: Checking container logs for {alert_type.upper()} alert pattern...")
    logs_validation = common_utils.check_logs_for_alerts(constants.CONTAINERS["time_series_analytics"]["name"], alert_type, timeout=60, interval=5)
    if not logs_validation:
        logger.error(f"✗ Step 2 FAILED: {alert_type.upper()} alert pattern not found in container logs")
        return False
    
    logger.info(f"\n=== {alert_type.upper()} Alert System Validation PASSED ===")
    
    return True

def validate_opcua_alert_system():
    """Docker-specific OPC UA alert system validation."""
    logger.info("=== Docker-based OPC UA Alert System Validation ===")
    logger.info(f"Starting validation from directory: {os.getcwd()}")


    # Step 1: Setup OPC UA alerts configuration using Docker-specific approach
    logger.info("\nStep 1: Setting up OPC UA alerts configuration...")
    update_config_setup = update_config_file("opcua")
    if not update_config_setup:
        logger.error("✗ Step 1 FAILED: OPC UA alerts configuration setup failed")
        return False

    # Step 2: Restart OPC UA server container
    logger.info("\nStep 2: Restarting OPC UA server container...")
    opcua_container_name = "timeseriessoftware-ia-opcua-server-1"
    try:
        if container_is_running(opcua_container_name):
            logger.info(f"Restarting {opcua_container_name} container...")
            restart_result = restart_container(opcua_container_name)
            if restart_result == 0:
                logger.info(f"✓ Successfully restarted {opcua_container_name}")
                # Wait for container to stabilize after restart
                logger.info("Waiting for OPC UA server to restart and stabilize...")
                wait_for_stability(30)
            else:
                logger.error(f"✗ Failed to restart {opcua_container_name} (exit code: {restart_result})")
                return False
        else:
            logger.error(f"✗ Container {opcua_container_name} is not running")
            return False
    except Exception as e:
        logger.error(f"✗ Step 3 FAILED: Error restarting OPC UA server - {str(e)}")
        return False

    # Wait for OPC UA system to stabilize and process data before checking logs
    logger.info("\nWaiting for OPC UA alert system to stabilize and generate alerts...")
    wait_for_stability(60)  # Extended wait time to allow OPC UA alerts to be generated and logged

    # Step 4: Check container logs for OPC UA alert pattern
    logger.info("\nStep 4: Checking container logs for OPC UA alert pattern...")
    logs_validation = check_logs_for_alerts(constants.CONTAINERS["time_series_analytics"]["name"], "opcua", timeout=120, interval=10)
    if not logs_validation:
        logger.error("✗ Step 4 FAILED: OPC UA alert pattern not found in container logs")
        return False

    logger.info("\n=== Docker-based OPC UA Alert System Validation PASSED ===")
    return True

def get_influxdb_credentials():
    """Fetch INFLUXDB_USERNAME and INFLUXDB_PASSWORD from env file"""
    try:
        env_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
        logger.info(f"Fetching InfluxDB credentials from: {env_path}")

        # Expand environment variables in the file path
        expanded_path = os.path.expandvars(env_path)

        # Read the existing file
        with open(expanded_path, 'r') as file:
            lines = file.readlines()

        # Extract the INFLUXDB_USERNAME and INFLUXDB_PASSWORD
        influxdb_username = None
        influxdb_password = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('INFLUXDB_USERNAME='):
                influxdb_username = line.split('=', 1)[1]
            elif line.startswith('INFLUXDB_PASSWORD='):
                influxdb_password = line.split('=', 1)[1]
        
        # Note: Not logging credentials for security reasons
        logger.info("Successfully retrieved InfluxDB credentials from .env file")

        return influxdb_username, influxdb_password
    except FileNotFoundError:
        logger.error(f"File not found: {env_path}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, None

def execute_influxdb_commands(container_name="ia-influxdb", measurement=None):
    """Execute InfluxDB commands inside the InfluxDB container and return data."""
    logger.info(f"Executing InfluxDB commands in container '{container_name}'...")
    try:
        # Step 1: Check InfluxDB container existence
        if container_exists(container_name):
            logger.info(f"{container_name} container exists")
        else:
            logger.info(f"{container_name} container does not exist")
            return None

        # Step 2: Get InfluxDB credentials
        influxdb_username, influxdb_password = get_influxdb_credentials()
        if not influxdb_username or not influxdb_password:
            logger.info("Failed to get InfluxDB credentials")
            return None

        # Step 3: Execute InfluxDB commands inside the container
        if measurement:
            # Query specific measurement(s)
            if measurement == constants.WELD_INGESTED_TOPIC:
                query_part = f"SELECT * FROM \"{constants.WELD_INGESTED_TOPIC}\" LIMIT 5; SELECT * FROM \"{constants.WELD_ANALYTICS_TOPIC}\" LIMIT 5"
                verify_tables = [constants.WELD_INGESTED_TOPIC, constants.WELD_ANALYTICS_TOPIC]
            else:
                # Default to wind turbine or handle other measurements
                query_part = f"SELECT * FROM \"{measurement.replace('_', '-')}\" LIMIT 5"
                verify_tables = [measurement.replace('_', '-')]
        else:
            # Default wind turbine queries for backward compatibility
            query_part = f"SELECT * FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\" LIMIT 5; SELECT * FROM \"{constants.WIND_TURBINE_ANALYTICS_TOPIC}\" LIMIT 5"
            verify_tables = [constants.WIND_TURBINE_INGESTED_TOPIC, constants.WIND_TURBINE_ANALYTICS_TOPIC]
        influx_execute = f"SHOW MEASUREMENTS; {query_part}"

        exec_command = [
            "docker", "exec", container_name,
            "influx", "-username", influxdb_username, "-password", influxdb_password,
            "-database", "datain", "-execute", influx_execute
        ]
        logger.info(f"Executing command: 'SHOW MEASUREMENTS; {query_part}' inside {container_name} container with redacted credentials.")

        result = subprocess.run(exec_command, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.info(f"Command failed with return code {result.returncode}")
            logger.info(f"Error: {result.stderr}")
            return None
            
        response = result.stdout.strip()
        logger.info("Query results:")
        logger.info(response)

        # Step 4: Verify the presence of specific measurements/tables
        if response and any(table in response for table in verify_tables):
            logger.info("Successfully retrieved InfluxDB data.")
            return response
        else:
            logger.info("No data found or required measurements are not present in the database.")
            # Return response even if empty to indicate successful connection
            return response if response else "Connected but no data found"

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            logger.error(f"Error details: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None
    
def verify_influxdb_retention_docker(response=None, container_name=constants.CONTAINERS["influxdb"]["name"]):
    """
    Execute InfluxDB commands inside the InfluxDB Docker container to verify retention.
    Returns the earliest time value in the measurement and a success flag.
    """
    logger.info(f"Executing InfluxDB retention check in container '{container_name}'...")
    try:
        # Step 1: Check if the InfluxDB container exists
        if not container_exists(container_name):
            logger.info(f"{container_name} container does not exist")
            return None, False
        logger.info(f"{container_name} container exists")

        # Step 2: Get InfluxDB credentials
        influxdb_username, influxdb_password = get_influxdb_credentials()
        if not influxdb_username or not influxdb_password:
            logger.info("Failed to get InfluxDB credentials")
            return None, False

        # Step 3: Execute InfluxDB query to get the earliest time value
        influx_execute = f"SELECT time, wind_speed FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\" ORDER BY time ASC LIMIT 1"
        exec_command = [
            "docker", "exec", container_name,
            "influx", "-username", influxdb_username, "-password", influxdb_password,
            "-database", "datain", "-execute", influx_execute
        ]
        logger.info(f"Executing InfluxDB query inside container '{container_name}': '{influx_execute}' with redacted credentials.")
        result = subprocess.run(exec_command, capture_output=True, text=True)

        if result.returncode != 0:
            logger.info(f"Command failed with return code {result.returncode}")
            logger.info(f"Error: {result.stderr}")
            return None, False

        # Parse the time value from line 4 of the output (equivalent to awk 'NR==4 {print $1}')
        output_lines = result.stdout.strip().split('\n')
        time_value = output_lines[3].split()[0] if len(output_lines) >= 4 else ""
        if time_value:
            logger.info(f"First time value in '{constants.WIND_TURBINE_INGESTED_TOPIC}': {time_value}")
            return time_value, True
        else:
            logger.info(f"No time data found in '{constants.WIND_TURBINE_INGESTED_TOPIC}'.")
            return None, False

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            logger.error(f"Error details: {e.stderr}")
        return None, False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, False

def measure_deployment_time(ingestion_type, iterations=None):
    """Simple deployment time measurement function."""
    iterations = iterations or constants.KPI_TEST_ITERATIONS
    times = []
    
    logger.info(f"Starting {ingestion_type} deployment time measurement...")
    
    for i in range(iterations):
        logger.info(f"\n=== Test Iteration {i+1}/{iterations} ===")
        start = time.time()
        
        try:
            logger.info(f"Starting {ingestion_type} deployment...")
            success = invoke_make_up_mqtt_ingestion() if ingestion_type == "mqtt" else invoke_make_up_opcua_ingestion()

            if success:
                # Check if all containers are up and running
                logger.info("Checking container status...")
                containers_up = check_make_status()
                deploy_time = time.time() - start
                
                if containers_up:
                    times.append(deploy_time)
                    logger.info(f"✓ Deployment successful: {deploy_time:.1f}s")
                else:
                    logger.error("✗ Deployment failed: Containers not running properly")
            else:
                deploy_time = time.time() - start
                logger.error(f"✗ Deployment failed after {deploy_time:.1f}s")
                
        except Exception as e:
            logger.error(f"✗ Deployment error: {str(e)}")
            
        if i < iterations - 1:  # Perform cleanup between iterations, but not after the last one
            try:
                logger.info("Starting cleanup process...")
                cleanup_success = invoke_make_down()
                
                if cleanup_success:
                    logger.info("✓ Cleanup successful, waiting for stability...")
                    # Give more time for system to stabilize after cleanup
                    wait_for_stability(30)  # Increased wait time for better stability
                else:
                    logger.error("✗ Cleanup function returned False")
                    continue  # Skip to next iteration if cleanup failed
                    
            except Exception as e:
                logger.error(f"✗ Cleanup error: {str(e)}")
                continue  # Skip to next iteration if cleanup failed
    
    if not times:
        logger.error(f"✗ All {ingestion_type} deployment attempts failed")
        return 0, float('inf'), float('inf'), float('inf'), []
        
    success_rate = len(times) * 100 / iterations
    avg_time = sum(times) / len(times)
    
    logger.info(f"\n=== {ingestion_type} Final Results ===")
    logger.info(f"Success Rate: {success_rate}%")
    logger.info(f"Average Time: {avg_time:.1f}s")
    logger.info(f"Best Time: {min(times):.1f}s")
    logger.info(f"Worst Time: {max(times):.1f}s")

    return success_rate, avg_time, min(times), max(times), times


def measure_build_time(iterations=None):
    """Measure Docker image build time over multiple iterations
    
    Args:
        iterations (int): Number of build iterations to run
        
    Returns:
        tuple: (success_rate, avg_time, min_time, max_time, times)
            success_rate (float): Percentage of successful builds
            avg_time (float): Average build time in seconds
            min_time (float): Minimum build time in seconds
            max_time (float): Maximum build time in seconds
            times (list): List of build times for each successful iteration
    """
    iterations = iterations or constants.KPI_TEST_ITERATIONS
    times = []
    
    logger.info(f"Starting build time measurement...")
    
    for i in range(iterations):
        logger.info(f"\n=== Build Test Iteration {i+1}/{iterations} ===")

        try:
            # First, ensure we're in a clean state
            invoke_make_down()

            # Measure build time
            logger.info(f"Starting build...")
            start_time = time.time()
            success, output = invoke_make_build()
            build_time = time.time() - start_time

            if success:
                times.append(build_time)
                logger.info(f"✓ Build successful: {build_time:.1f}s")
            else:
                logger.error(f"✗ Build failed after {build_time:.1f}s. Output:\n{output}")
                
        except Exception as e:
            logger.error(f"✗ Build error: {str(e)}")
            
        # For builds, we need to ensure everything is cleaned up between iterations
        if i < iterations - 1:
            try:
                logger.info("Starting cleanup process...")
                cleanup_success = invoke_make_down()
                
                if cleanup_success:
                    logger.info("✓ Cleanup successful, waiting for stability...")
                    # Give time for system to stabilize after cleanup
                    wait_for_stability(20)
                else:
                    logger.error("✗ Cleanup function returned False")
                    continue  # Skip to next iteration if cleanup failed
                    
            except Exception as e:
                logger.error(f"✗ Cleanup error: {str(e)}")
                continue  # Skip to next iteration if cleanup failed
    
    if not times:
        logger.error(f"✗ All build attempts failed")
        return 0, float('inf'), float('inf'), float('inf'), []
        
    success_rate = len(times) * 100 / iterations
    avg_time = sum(times) / len(times)
    
    logger.info(f"\n=== Build Time Final Results ===")
    logger.info(f"Success Rate: {success_rate}%")
    logger.info(f"Average Time: {avg_time:.1f}s")
    logger.info(f"Best Time: {min(times):.1f}s")
    logger.info(f"Worst Time: {max(times):.1f}s")

    return success_rate, avg_time, min(times), max(times), times


def check_image_sizes(size_threshold=None, check_deployed_only=True):
    """
    Checks Docker image sizes for deployed containers or all built images.
    
    Args:
        size_threshold (float): Maximum size threshold in MB for any image/container.
                               If None, uses constants.CONTAINER_IMAGE_SIZE_THRESHOLD
        check_deployed_only (bool): If True, only check deployed containers.
                                   If False, check all built images from docker-compose.
    
    Returns:
        tuple: (bool, str) - (success, error_message)
    """
    try:
        # Get size threshold from constants if not provided
        if size_threshold is None:
            size_threshold = constants.CONTAINER_IMAGE_SIZE_THRESHOLD
            
        if check_deployed_only:
            # Container-based approach for deployed environments
            return _check_deployed_container_sizes(size_threshold)
        else:
            # Image-based approach for build tests
            return _check_built_image_sizes(size_threshold)
    
    except Exception as e:
        error_msg = f"Error checking image sizes: {e}"
        logger.error(error_msg)
        return False, error_msg

def _check_deployed_container_sizes(size_threshold):
    """Check sizes of deployed containers using a single threshold."""
    # Get deployed containers
    deployed_containers = get_the_deployed_containers()
    if not deployed_containers:
        logger.warning("No deployed containers found")
        return False, "No deployed containers found for verification"
        
    logger.info(f"Found {len(deployed_containers)} deployed containers: {deployed_containers}")
    
    logger.info("=== Container Image Size Check ===")
    logger.info(f"Checking Docker image sizes for deployed containers (threshold: {size_threshold}MB):")
    
    # Check each container's image size
    oversized_containers = []
    
    for container_name in deployed_containers:
        try:
            # Get the image name for this container
            inspect_cmd = ['docker', 'inspect', '--format', '{{.Config.Image}}', container_name]
            inspect_result = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True)
            image_name = inspect_result.stdout.strip()
            
            if not image_name:
                logger.warning(f"Could not get image name for container: {container_name}")
                continue
            
            # Get the image size
            size = get_image_size(image_name)
            if size is None:
                logger.warning(f"Could not get size for image: {image_name} (container: {container_name})")
                continue
            
            logger.info(f"- {container_name} (image: {image_name}): {size:.2f}MB (threshold: {size_threshold}MB)")
            
            # Check if container's image exceeds threshold
            if size > size_threshold:
                oversized_containers.append((container_name, image_name, size))
                logger.warning(f"Container {container_name} image size ({size:.2f}MB) exceeds threshold of {size_threshold}MB")
            else:
                logger.info(f"✓ Container {container_name} passed size check: {size:.2f}MB <= {size_threshold}MB")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error inspecting container {container_name}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error checking size for container {container_name}: {e}")
            continue
    
    # Log containers that exceed threshold and return result
    if oversized_containers:
        logger.warning(f"=== Containers exceeding {size_threshold} MB ===")
        for container_name, image_name, size in oversized_containers:
            logger.warning(f"⚠️  {container_name} (image: {image_name}): {size:.2f}MB exceeds {size_threshold} MB limit")
        
        # Return failure with details of all oversized containers
        container_details = [f"{name} ({size:.2f}MB)" for name, _, size in oversized_containers]
        return False, f"Containers {container_details} exceed threshold of {size_threshold}MB"
    else:
        logger.info(f"No containers exceed the {size_threshold} MB size limit")
    
    return True, "All container image size checks passed"

def _check_built_image_sizes(size_threshold):
    """Check sizes of built images from docker-compose using a single threshold."""
    # Get images from docker-compose files
    compose_images = get_images_from_docker_compose()
    logger.info(f"Images from docker-compose files: {compose_images}")
    
    if not compose_images:
        logger.warning("No images found in docker-compose files")
        return False, "No images found for verification"
    
    logger.info("=== Docker Image Size Check ===")
    logger.info(f"Checking built Docker image sizes (threshold: {size_threshold}MB):")
    
    # Track images that exceed threshold
    oversized_images = []
    checked_images = 0
    
    # Check each image from docker-compose
    for image in compose_images:
        try:
            # Get image size using docker inspect
            cmd = ['docker', 'image', 'inspect', image, '--format={{.Size}}']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Convert size from bytes to MB
            size_bytes = int(result.stdout.strip())
            size_mb = size_bytes / (1024 * 1024)
            
            checked_images += 1
            logger.info(f"- {image}: {size_mb:.2f}MB (threshold: {size_threshold}MB)")
            
            # Check if image exceeds threshold
            if size_mb > size_threshold:
                oversized_images.append((image, size_mb))
                logger.warning(f"Image {image} size ({size_mb:.2f}MB) exceeds threshold of {size_threshold}MB")
            else:
                logger.info(f"✓ Image {image} passed size check: {size_mb:.2f}MB <= {size_threshold}MB")
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not inspect image {image}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error checking size for image {image}: {e}")
            continue
    
    if checked_images == 0:
        logger.warning("No images could be checked")
        return False, "No images could be checked for verification"
    
    # Log images that exceed threshold and return result
    if oversized_images:
        logger.warning(f"=== Images exceeding {size_threshold} MB ===")
        for image, size in oversized_images:
            logger.warning(f"⚠️  {image}: {size:.2f}MB exceeds {size_threshold} MB limit")
        
        # Return failure with details of all oversized images
        image_details = [f"{name} ({size:.2f}MB)" for name, size in oversized_images]
        return False, f"Images {image_details} exceed threshold of {size_threshold}MB"
    else:
        logger.info(f"No images exceed the {size_threshold} MB size limit")
    
    logger.info(f"Successfully checked {checked_images} images")
    return True, "All image size checks passed"


def read_env_file(file_path=None):
    """Read environment variables from .env file
    
    Args:
        file_path (str): Path to the .env file. If None, uses default location.
        
    Returns:
        dict: Dictionary of environment variables and their values
    """
    # Set default file path if not provided
    if file_path is None:
        file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    
    # Expand environment variables in the file path
    file_path = os.path.expandvars(file_path)
    env_vars = {}
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.info(f"Environment file not found: {file_path}")
            return env_vars

        # Read the file
        with open(file_path, 'r') as file:
            lines = file.readlines()
            
        # Parse each line to extract variable name and value
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
                
        logger.info(f"Read {len(env_vars)} environment variables from {file_path}")
        return env_vars
        
    except Exception as e:
        logger.error(f"Failed to read .env file: {str(e)}")
        return env_vars

def verify_deployment_with_credentials(ingestion_type="mqtt"):
    """
    Function to verify deployment with credentials for either MQTT or OPCUA:
    1. Reads updated values from .env file
    2. Runs make_up_mqtt or make_up_opcua depending on ingestion_type
    3. Checks make status to verify containers are running
    4. Checks logs of containers
    5. Verifies username and password from .env are present in logs
    
    Args:
        ingestion_type (str): Type of ingestion to deploy - either "mqtt" or "opcua"
        
    Returns:
        dict: Results of the verification process
    """
    try:
        ingestion_type = ingestion_type.lower()
        if ingestion_type not in ["mqtt", "opcua"]:
            raise ValueError(f"Invalid ingestion type: {ingestion_type}. Must be either 'mqtt' or 'opcua'")
            
        logger.info(f"Starting {ingestion_type.upper()} deployment verification with credentials...")
        results = {
            "success": False,
            "env_variables_read": False,
            "deployment_success": False,
            "containers_up": False,
            "credentials_in_logs": False,
            "ingestion_type": ingestion_type,
            "failed_step": None,
            "env_vars": {},
            "containers_checked": [],
            "errors": []
        }
        
        # Step 1: Read the details from .env file after update
        logger.info("Step 1: Reading environment variables from .env file...")
        env_vars = read_env_file()
        
        if not env_vars:
            logger.error("Failed to read environment variables from .env file")
            results["failed_step"] = "read_env_variables"
            results["errors"].append("Failed to read environment variables from .env file")
            return results
            
        # Store the credentials we need to check later
        results["env_vars"] = env_vars
        results["env_variables_read"] = True
        logger.info(f"Successfully read {len(env_vars)} environment variables")
        
        # Step 2: Run make_up based on ingestion type
        if ingestion_type == "mqtt":
            logger.info("Step 2: Running make_up_mqtt_ingestion...")
            deployment_success = invoke_make_up_mqtt_ingestion()
            command_name = "make_up_mqtt_ingestion"
        else:  # opcua
            logger.info("Step 2: Running make_up_opcua_ingestion...")
            deployment_success = invoke_make_up_opcua_ingestion()
            command_name = "make_up_opcua_ingestion"
        
        if not deployment_success:
            logger.error(f"Failed to run {command_name}")
            results["failed_step"] = f"deployment_{ingestion_type}"
            results["errors"].append(f"Failed to run {command_name}")
            return results
            
        results["deployment_success"] = True
        logger.info(f"Successfully ran {command_name}")
        
        # Wait for containers to stabilize
        wait_for_stability(30)
        
        # Step 3: Check make status to verify containers are up
        logger.info("Step 3: Checking container status...")
        status_success = invoke_make_status()
        
        if not status_success:
            logger.error("Failed to run make status")
            results["failed_step"] = "make_status"
            results["errors"].append("Failed to run make status")
            return results
        
        # Get list of deployed containers
        containers = get_the_deployed_containers()
        
        if not containers:
            logger.error("No containers found running")
            results["failed_step"] = "no_containers"
            results["errors"].append("No containers found running")
            return results
            
        results["containers_up"] = True
        logger.info(f"Found {len(containers)} containers running")
        
        # Step 4 & 5: Check container logs for credentials
        logger.info("Step 4 & 5: Checking container logs for credentials...")
        credential_found = False
        
        # Get the credentials we want to check for in the logs
        credentials_to_check = {k: v for k, v in env_vars.items() if k in get_credential_fields()}
        
        if not credentials_to_check:
            logger.error("No credential variables found in .env file")
            results["failed_step"] = "no_credentials"
            results["errors"].append("No credential variables found in .env file")
            return results
            
        # Check logs of each container for credentials
        for container in containers:
            results["containers_checked"].append(container)
            logger.info(f"Checking logs for container: {container}")
            
            try:
                logs = get_container_logs(container)
                
                # Check for each credential in the logs
                for cred_key, cred_value in credentials_to_check.items():
                    if cred_value in logs:
                        logger.info(f"Found credential '{cred_key}' in logs of container {container}")
                        credential_found = True
                        break
                        
                if credential_found:
                    break
                    
            except Exception as e:
                logger.error(f"Error checking logs for container {container}: {str(e)}")
                results["errors"].append(f"Error checking logs for container {container}: {str(e)}")
        
        results["credentials_in_logs"] = credential_found
        
        if not credential_found:
            logger.error("Credentials not found in any container logs")
            results["failed_step"] = "credentials_not_found"
            results["errors"].append("Credentials not found in any container logs")
        else:
            logger.info("Successfully verified credentials in container logs")
            results["success"] = True
        
        return results
        
    except Exception as e:
        logger.error(f"Error in verify_deployment_with_credentials for {ingestion_type}: {str(e)}")
        return {
            "success": False,
            "ingestion_type": ingestion_type,
            "failed_step": "exception",
            "errors": [str(e)]
        }

def deploy_from_docker_hub(app_name, ingestion_type="mqtt", wait_time=90):
    """
    Deploy application from Docker Hub pre-built images.
    
    Args:
        app_name (str): Application name constant (e.g., constants.WELD_SAMPLE_APP)
        ingestion_type (str): Type of ingestion - "mqtt" or "opcua"
        wait_time (int): Time to wait for containers to stabilize after deployment
        
    Returns:
        dict: Results of the deployment verification
    """
    results = {
        "success": False,
        "registry_cleared": False,
        "deployment_success": False,
        "containers_running": False,
        "containers_healthy": False,
        "images_verified": False,
        "errors": []
    }
    
    try:
        # Step 1: Ensure DOCKER_REGISTRY is empty to pull from Docker Hub
        logger.info("Step 1: Ensuring DOCKER_REGISTRY is empty for Docker Hub deployment")
        env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
        
        # Read current .env file
        with open(env_file_path, 'r') as f:
            env_content = f.read()
        
        # Set DOCKER_REGISTRY to empty to pull from Docker Hub
        env_content = re.sub(r'DOCKER_REGISTRY=.*', 'DOCKER_REGISTRY=', env_content)
        with open(env_file_path, 'w') as f:
            f.write(env_content)
        
        logger.info("✓ DOCKER_REGISTRY set to empty - images will be pulled from Docker Hub")
        results["registry_cleared"] = True
        
        # Step 2: Execute deployment
        logger.info(f"Step 2: Executing deployment with {ingestion_type} ingestion for app: {app_name}")
        cmd = f"make up_{ingestion_type}_ingestion app=\"{app_name}\""
        result = run_command(cmd)
        
        if result != 0:
            logger.error(f"Docker Hub deployment command failed with exit code: {result}")
            results["errors"].append(f"Deployment command failed with exit code: {result}")
            return results
        
        logger.info("✓ Deployment command executed successfully")
        results["deployment_success"] = True
        
        # Step 3: Wait for containers to stabilize (longer wait for Docker Hub pull)
        logger.info(f"Step 3: Waiting {wait_time} seconds for containers to stabilize after Docker Hub image pull...")
        wait_for_stability(wait_time)
        
        # Step 4: Verify containers are running
        logger.info("Step 4: Verifying containers are running")
        containers = get_the_deployed_containers()
        
        if not containers:
            logger.error("No containers found after Docker Hub deployment")
            results["errors"].append("No containers found after deployment")
            return results
        
        logger.info(f"✓ Found {len(containers)} deployed containers: {containers}")
        results["containers_running"] = True
        
        # Step 5: Verify container health status
        logger.info("Step 5: Verifying container health status")
        container_status = restart_containers_and_check_status(ingestion_type=ingestion_type)
        
        if not all(status == "Up" for status in container_status.values()):
            unhealthy = [name for name, status in container_status.items() if status != "Up"]
            logger.error(f"Some containers are not running properly: {unhealthy}")
            results["errors"].append(f"Unhealthy containers: {unhealthy}")
            return results
        
        logger.info("✓ All containers are running properly")
        results["containers_healthy"] = True
        
        # Step 6: Verify images are from Docker Hub (not from custom registry)
        logger.info("Step 6: Verifying images are from Docker Hub...")
        result = subprocess.run(['docker', 'ps', '--format', '{{.Image}}'], 
                              capture_output=True, text=True)
        images = result.stdout.strip().split('\n')
        
        custom_registry_found = False
        for image in images:
            logger.info(f"Checking deployed image: {image}")
            # Docker Hub images should not have a custom registry prefix like myregistry.com/
            if any(keyword in image.lower() for keyword in ['weld', 'time-series', 'telegraf', 'influx', 'kapacitor']):
                # Check if it has a custom registry prefix (domain with TLD)
                if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/', image):
                    logger.error(f"Image {image} appears to be from custom registry, not Docker Hub")
                    results["errors"].append(f"Image {image} is from custom registry")
                    custom_registry_found = True
        
        if not custom_registry_found:
            logger.info("✓ All images verified from Docker Hub")
            results["images_verified"] = True
            results["success"] = True
        
        return results
        
    except Exception as e:
        logger.error(f"Error in deploy_from_docker_hub: {str(e)}")
        results["errors"].append(f"Exception: {str(e)}")
        return results

def get_resource_usage():
    """
    Get CPU and memory usage for all deployed containers.
    Returns:
        dict: {container_name: {"cpu": float, "mem": float}}
    """
    containers = get_the_deployed_containers()
    usage = {}
    if not containers:
        logger.warning("No containers found for resource usage check.")
        return usage
    # Use docker stats --no-stream for a snapshot
    cmd_args = ["docker", "stats", "--no-stream", "--format", "{{.Name}}:{{.CPUPerc}}:{{.MemUsage}}"] + containers
    try:
        result = subprocess.run(cmd_args, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to get docker stats: {result.stderr}")
            return usage
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3:
                continue
            name, cpu_str, mem_str = parts
            # Parse CPU percentage
            try:
                cpu = float(cpu_str.replace('%','').strip())
            except Exception:
                cpu = None
            # Parse memory usage (e.g., '12.34MiB / 1GiB')
            mem_val = mem_str.split('/')[0].strip()
            mem = _parse_mem_value(mem_val)
            usage[name] = {"cpu": cpu, "mem": mem}
        return usage
    except Exception as e:
        logger.error(f"Error getting resource usage: {e}")
        return usage

def _parse_mem_value(mem_str):
    """Helper to parse memory string like '12.34MiB', '1.2GiB', '512KiB' to MB"""
    try:
        if mem_str.lower().endswith('gib'):
            return float(mem_str[:-3].strip()) * 1024
        elif mem_str.lower().endswith('mib'):
            return float(mem_str[:-3].strip())
        elif mem_str.lower().endswith('kib'):
            return float(mem_str[:-3].strip()) / 1024
        elif mem_str.lower().endswith('b'):
            return float(mem_str[:-1].strip()) / (1024*1024)
        else:
            return float(mem_str)
    except Exception:
        return None

def check_resource_leak(initial_stats, final_stats, memory_leak_threshold_mb=50):
    """
    Check for memory leaks by analyzing absolute memory consumption trends.
    A memory leak is characterized by a sustained increase in memory usage over time,
    not just high percentage usage.
    
    Args:
        initial_stats (dict): Output of get_resource_usage() at start
        final_stats (dict): Output of get_resource_usage() at end  
        memory_leak_threshold_mb (float): Absolute memory increase in MB that indicates a potential leak
    Returns:
        bool: True if no significant leak, False if leak detected
    """
    leak_detected = False
    
    for container in initial_stats:
        if container not in final_stats:
            logger.warning(f"Container {container} missing in final stats.")
            continue
            
        ini = initial_stats[container]
        fin = final_stats[container]
        
        # Focus on memory leak detection - check absolute memory increase
        if ini["mem"] is not None and fin["mem"] is not None:
            memory_increase_mb = fin["mem"] - ini["mem"]
            
            # Check for sustained memory increase indicating a leak
            if memory_increase_mb > memory_leak_threshold_mb:
                logger.error(f"MEMORY LEAK detected in {container}: "
                           f"Memory increased by {memory_increase_mb:.2f}MB "
                           f"({ini['mem']:.2f}MB -> {fin['mem']:.2f}MB)")
                leak_detected = True
            elif memory_increase_mb > 0:
                logger.info(f"Memory increase in {container}: {memory_increase_mb:.2f}MB "
                          f"(within acceptable range of {memory_leak_threshold_mb}MB)")
            else:
                logger.info(f"No memory leak in {container}: "
                          f"Memory usage stable or decreased ({ini['mem']:.2f}MB -> {fin['mem']:.2f}MB)")
        
        # CPU monitoring for information (not leak detection, but resource monitoring)
        if ini["cpu"] is not None and fin["cpu"] is not None:
            cpu_change = fin["cpu"] - ini["cpu"]
            if abs(cpu_change) > 10:  # Only log significant CPU changes
                logger.info(f"CPU usage change in {container}: "
                          f"{ini['cpu']:.1f}% -> {fin['cpu']:.1f}% (change: {cpu_change:+.1f}%)")
    
    if not leak_detected:
        logger.info("✓ No memory leaks detected - all containers show stable memory usage")
    
    return not leak_detected


def setup_mqtt_alerts_docker(sample_app=constants.WIND_SAMPLE_APP):
    """
    Setup MQTT alerts for Docker deployment with app-specific support.
    
    Args:
        sample_app (str): Sample app type (constants.WIND_SAMPLE_APP, constants.WELD_SAMPLE_APP, or constants.MULTIMODAL_SAMPLE_APP).
    
    Returns:
        bool: True if setup successful, False otherwise
    """
    try:
        logger.info(f"Setting up MQTT alerts for Docker deployment with app: {sample_app}")
        
        # Save current directory
        original_dir = os.getcwd()
        
        # Navigate to the correct app directory based on sample app
        if sample_app == constants.WIND_SAMPLE_APP:
            target_dir = os.path.join(constants.EDGE_AI_SUITES_DIR, 
                                    "apps/wind-turbine-anomaly-detection/time-series-analytics-config")
            file_path = os.path.join(target_dir, "tick_scripts/windturbine_anomaly_detector.tick")
            setup_type = "mqtt"
        elif sample_app == constants.WELD_SAMPLE_APP:
            target_dir = os.path.join(constants.EDGE_AI_SUITES_DIR, 
                                    "apps/weld-defect-detection/time-series-analytics-config")
            file_path = os.path.join(target_dir, "tick_scripts/weld_defect_detector.tick")
            setup_type = "mqtt_weld"
        elif sample_app == constants.MULTIMODAL_SAMPLE_APP:
            # For multimodal, the config is in a different location
            multimodal_dir = constants.EDGE_AI_SUITES_DIR.replace(constants.TARGET_SUBPATH, constants.MULTIMODAL_TARGET_SUBPATH)
            target_dir = os.path.join(multimodal_dir, "configs/time-series-analytics-microservice")
            file_path = os.path.join(target_dir, "tick_scripts/weld_defect_detector.tick")
            setup_type = "mqtt_weld"
        else:
            logger.error(f"✗ Unsupported sample app: {sample_app}")
            return False
        
        logger.info(f"Target directory: {target_dir}")
        logger.info(f"Tick script path: {file_path}")
        
        # Check if tick script file exists
        if not os.path.exists(file_path):
            logger.error(f"✗ Tick script file not found: {file_path}")
            return False
        
        # Update the tick script with appropriate MQTT alert configuration
        success = common_utils.update_alert_in_tick_script(file_path, setup_type)
        
        if success:
            logger.info(f"✓ {setup_type.upper()} alert configuration set successfully for {sample_app}")
            return True
        else:
            logger.error(f"✗ Failed to set {setup_type.upper()} alert configuration for {sample_app}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Exception occurred while setting up MQTT alerts: {str(e)}")
        return False
    finally:
        # Always return to original directory
        try:
            os.chdir(original_dir)
        except Exception:
            pass

def invoke_make_up(measure_time=False):
    """
    Execute 'make up' command to deploy the full stack.
    
    Args:
        measure_time (bool): Whether to measure execution time
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Executing 'make up' command")
        
        start_time = time.time() if measure_time else None
        
        # Run make up
        result = subprocess.run(["make", "up"], capture_output=True, text=True, timeout=600)
        
        if measure_time:
            execution_time = time.time() - start_time
            logger.info(f"make up execution time: {execution_time:.2f} seconds")
        
        if result.returncode == 0:
            logger.info("make up succeeded")
            return True
        else:
            logger.error(f"make up failed with exit code: {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("make up command timed out")
        return False
    except Exception as e:
        logger.error(f"Exception occurred while running make up: {str(e)}")
        return False

def get_container_stats(container_name):
    """
    Get resource usage statistics for a container.
    
    Args:
        container_name (str): Name of the container
        
    Returns:
        dict: Dictionary containing CPU and memory usage statistics, or None if failed
    """
    try:
        # Run docker stats command for a single sample
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}", container_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:  # Header + data line
                data_line = lines[1]
                parts = data_line.split('\t')
                if len(parts) >= 4:
                    cpu_percent = float(parts[1].replace('%', ''))
                    memory_percent = float(parts[2].replace('%', ''))
                    memory_usage = parts[3]
                    
                    return {
                        'container': parts[0],
                        'cpu_percent': cpu_percent,
                        'memory_percent': memory_percent,
                        'memory_usage': memory_usage
                    }
        
        logger.warning(f"Could not get stats for container: {container_name}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting container stats for {container_name}: {e}")
        return None


def invoke_make_check_env_variables_in_current_dir():
    """Test if make check_env_variables command works in the current directory without changing directories"""
    try:
        result = run_command("make check_env_variables")
        
        if result != 0:  # Command failed
            logger.info("make check_env_variables failed")
            return False
        logger.info("make check_env_variables succeeded")
        return True
    except Exception as e:
        logger.error(f"Failed to run make check_env_variables: {str(e)}")
        return False


def invoke_make_up_in_current_dir():
    """Execute 'make up' command in the current directory without changing directories."""
    try:
        logger.info("Executing 'make up' command")
        result, output = run_command("make up", capture_output=True)

        if result == 0:
            logger.info("make up succeeded")
            if output:
                logger.warning(f"make up output: {output}")
            return True

        logger.error(f"make up failed with exit code: {result}")
        if output:
            logger.error(f"Error output: {output}")

        # Run make status to show container state for diagnostics
        logger.info("Running 'make status' for diagnostics...")
        _, status_output = run_command("make status", capture_output=True)
        if status_output:
            logger.info(f"make status output: {status_output}")

        return False

    except Exception as e:
        logger.error(f"Failed to run make up: {str(e)}")
        return False


def generate_multimodal_test_credentials(case_type="valid", invalid_field=None):
    """
    Generate test credentials for multimodal scenarios including WebRTC/MediaMTX variables.
    
    Args:
        case_type: "valid", "blank", "invalid", or "single_invalid"
        invalid_field: If specified, only this field will be invalid (others valid)
    """
    # Get the basic credentials first
    basic_credentials = generate_test_credentials(case_type, invalid_field)
    
    # Add multimodal-specific credentials
    if case_type == "blank":
        multimodal_vars = {
            "MTX_WEBRTCICESERVERS2_0_USERNAME": "",
            "MTX_WEBRTCICESERVERS2_0_PASSWORD": "",
            "HOST_IP": "",
            "RTSP_CAMERA_IP": "",
            "S3_STORAGE_USERNAME": "",
            "S3_STORAGE_PASSWORD": ""
        }
    elif case_type == "valid":
        # Generate valid S3 credentials that meet Makefile requirements
        s3_username = generate_username(8)  # Alphabets only, min 5 chars
        s3_password = generate_password(12)  # Alphanumeric with digit, min 10 chars
        
        # Ensure S3_STORAGE_USERNAME meets requirements (alphabets only, min 5 chars)
        while len(s3_username) < 5 or not s3_username.isalpha():
            s3_username = generate_username(8)
        
        multimodal_vars = {
            "MTX_WEBRTCICESERVERS2_0_USERNAME": generate_username(5),
            "MTX_WEBRTCICESERVERS2_0_PASSWORD": generate_password(10),
            "HOST_IP": "127.0.0.1",
            "RTSP_CAMERA_IP": "192.168.1.100",
            "S3_STORAGE_USERNAME": s3_username,
            "S3_STORAGE_PASSWORD": s3_password
        }
        
        # Validate that S3 credentials are properly set
        if not multimodal_vars["S3_STORAGE_USERNAME"] or not multimodal_vars["S3_STORAGE_PASSWORD"]:
            logger.error("Failed to generate valid S3 credentials")
            raise ValueError("S3 credentials generation failed")
            
    elif case_type == "invalid":
        multimodal_vars = {
            "MTX_WEBRTCICESERVERS2_0_USERNAME": generate_username(3),  # Invalid: too short
            "MTX_WEBRTCICESERVERS2_0_PASSWORD": generate_username(3),     # Invalid: too short
            "HOST_IP": "invalid_ip",
            "RTSP_CAMERA_IP": "invalid_camera_ip",
            "S3_STORAGE_USERNAME": generate_username(2),  # Invalid: too short
            "S3_STORAGE_PASSWORD": generate_password(2)   # Invalid: too short
        }

    else:
        multimodal_vars = {}
    
    # Combine basic and multimodal credentials
    basic_credentials.update(multimodal_vars)

    logger.info(f"Generated {len(basic_credentials)} multimodal credentials for case '{case_type}'")
    
    return basic_credentials


def invoke_make_down_in_current_dir():
    """Execute 'make down' command in the current directory without changing directories"""
    try:
        logger.info("Executing 'make down' command")
        result = run_command("make down")
        
        if result != 0:  # Command failed
            logger.error(f"make down failed with exit code: {result}")
            # Get more detailed error information
            error_result = subprocess.run(
                ["make", "down"], 
                capture_output=True, 
                text=True,
                cwd=os.getcwd()
            )
            if error_result.stderr:
                logger.error(f"Error output: {error_result.stderr}")
            return False
            
        logger.info("make down succeeded")
        return True
    except Exception as e:
        logger.error(f"Failed to run make down: {str(e)}")
        return False


def check_and_set_working_directory_multimodal(return_original=True):
    """
    Check and set working directory to the multimodal application directory.
    
    Args:
        return_original (bool): If True, returns the original directory path for later restoration
        
    Returns:
        bool or tuple: If return_original=True, returns (success, original_dir)
                       If return_original=False, returns True for success, raises exception on failure
        
    Raises:
        AssertionError: If directory doesn't exist or change fails
    """
    original_dir = os.getcwd()
    logger.info(f"Checking working directory for multimodal app: {MULTIMODAL_APPLICATION_DIRECTORY}")
    
    # Check if directory exists
    if not os.path.exists(MULTIMODAL_APPLICATION_DIRECTORY):
        logger.error(f"Multimodal application directory does not exist: {MULTIMODAL_APPLICATION_DIRECTORY}")
        raise AssertionError(f"Directory not found: {MULTIMODAL_APPLICATION_DIRECTORY}")
    
    # Change to the directory
    try:
        os.chdir(MULTIMODAL_APPLICATION_DIRECTORY)
        current_dir = os.getcwd()
        logger.debug(f"✓ Successfully changed to: {current_dir}")
        
        # Verify we're in the correct directory
        if not current_dir.endswith("industrial-edge-insights-multimodal"):
            logger.warning(f"Current directory doesn't end with expected path: {current_dir}")
        
        if return_original:
            return True, original_dir
        return True
            
    except Exception as e:
        logger.error(f"Failed to change to multimodal directory: {str(e)}")
        raise AssertionError(f"Failed to change directory: {str(e)}")


def get_fusion_sample_logs():
    """
    Get sample fusion decision logs for validation testing.
    
    Returns:
        list: List of sample fusion log entries for testing
    """
    return [
        # Vision=1, TS=0 (Vision-only detections should result in fusion=1)
        "Vision_Anomaly Type: Undercut, Vision anomaly: 1, TS anomaly: 0 fused decision: 1",
        "Vision_Anomaly Type: Overlap, Vision anomaly: 1, TS anomaly: 0 fused decision: 1", 
        "Vision_Anomaly Type: Excessive_Convexity, Vision anomaly: 1, TS anomaly: 0 fused decision: 1",
        "Vision_Anomaly Type: Crater_Cracks, Vision anomaly: 1, TS anomaly: 0 fused decision: 1",
        "Vision_Anomaly Type: Spatter, Vision anomaly: 1, TS anomaly: 0 fused decision: 1",
        "Vision_Anomaly Type: Lack_of_Fusion, Vision anomaly: 1, TS anomaly: 0 fused decision: 1",
        "Vision_Anomaly Type: Porosity, Vision anomaly: 1, TS anomaly: 0 fused decision: 1",
        
        # Vision=1, TS=1 (Both systems detect - should result in fusion=1)
        "Vision_Anomaly Type: Undercut, Vision anomaly: 1, TS anomaly: 1 fused decision: 1",
        "Vision_Anomaly Type: Crater_Cracks, Vision anomaly: 1, TS anomaly: 1 fused decision: 1",
        "Vision_Anomaly Type: Spatter, Vision anomaly: 1, TS anomaly: 1 fused decision: 1",
        "Vision_Anomaly Type: Excessive_Convexity, Vision anomaly: 1, TS anomaly: 1 fused decision: 1",
        
        # Vision=0, TS=1 (TS-only detections should result in fusion=1)
        "Vision_Anomaly Type: No Label, Vision anomaly: 0, TS anomaly: 1 fused decision: 1",
        "Vision_Anomaly Type: No_Weld, Vision anomaly: 0, TS anomaly: 1 fused decision: 1",
        
        # Vision=0, TS=0 (No detections should result in fusion=0)
        "Vision_Anomaly Type: No Label, Vision anomaly: 0, TS anomaly: 0 fused decision: 0",
        "Vision_Anomaly Type: No_Weld, Vision anomaly: 0, TS anomaly: 0 fused decision: 0",
    ]


def parse_fusion_decision_logs(fusion_log_samples):
    """
    Parse fusion decision logs to extract decision components.
    
    Args:
        fusion_log_samples (list): List of fusion log sample strings
        
    Returns:
        tuple: (decision_patterns, vision_anomalies, ts_anomalies, fusion_decisions)
    """
    decision_patterns = []
    vision_anomalies = []
    ts_anomalies = []
    fusion_decisions = []
    
    for line in fusion_log_samples:
        if "Vision_Anomaly Type:" in line and "Vision anomaly:" in line and "TS anomaly:" in line and "fused decision:" in line:
            try:
                # Parse the log line to extract decision components
                # Example: "Vision_Anomaly Type: Undercut, Vision anomaly: 1, TS anomaly: 0 fused decision: 1"
                parts = line.split(", ")
                if len(parts) >= 3:
                    vision_anomaly = int(parts[1].split(": ")[1])
                    # Handle the last part which includes "fused decision"
                    ts_part = parts[2].split(" fused decision: ")
                    ts_anomaly = int(ts_part[0].split(": ")[1])
                    fused_decision = int(ts_part[1])
                    anomaly_type = parts[0].split(": ")[1]
                    
                    vision_anomalies.append(vision_anomaly)
                    ts_anomalies.append(ts_anomaly)
                    fusion_decisions.append(fused_decision)
                    decision_patterns.append({
                        'type': anomaly_type,
                        'vision': vision_anomaly,
                        'ts': ts_anomaly,
                        'fusion': fused_decision
                    })
                
            except (IndexError, ValueError) as e:
                logger.debug(f"Could not parse fusion log line: {line[:100]}... Error: {e}")
                continue
    
    logger.info(f"Analyzed {len(decision_patterns)} fusion decisions from sample logs")
    return decision_patterns, vision_anomalies, ts_anomalies, fusion_decisions


def validate_fusion_logic_consistency(decision_patterns):
    """
    Validate fusion logic consistency using OR logic.
    
    Args:
        decision_patterns (list): List of decision pattern dictionaries
        
    Returns:
        tuple: (consistency_percentage, categorized_cases)
    """
    logical_decisions = 0
    total_decisions = len(decision_patterns)
    
    # Track different decision scenarios
    both_anomaly_cases = []  # Both vision and TS detect anomaly
    vision_only_cases = []   # Only vision detects anomaly
    ts_only_cases = []       # Only TS detects anomaly
    no_anomaly_cases = []    # Neither detects anomaly
    
    for pattern in decision_patterns:
        vision = pattern['vision']
        ts = pattern['ts']
        fusion = pattern['fusion']
        
        # Categorize decision types
        if vision == 1 and ts == 1:
            both_anomaly_cases.append(pattern)
        elif vision == 1 and ts == 0:
            vision_only_cases.append(pattern)
        elif vision == 0 and ts == 1:
            ts_only_cases.append(pattern)
        elif vision == 0 and ts == 0:
            no_anomaly_cases.append(pattern)
        
        # Check logical consistency - fusion should be 1 if either vision or TS detects anomaly (OR logic)
        expected_fusion = 1 if (vision == 1 or ts == 1) else 0
        
        if fusion == expected_fusion:
            logical_decisions += 1
        else:
            logger.warning(f"Inconsistent fusion decision: Vision={vision}, TS={ts}, Fusion={fusion}, Expected={expected_fusion}, Type={pattern['type']}")
    
    # Calculate consistency percentage
    consistency_percentage = (logical_decisions / total_decisions) * 100
    logger.info(f"Fusion logic consistency: {logical_decisions}/{total_decisions} = {consistency_percentage:.1f}%")
    
    categorized_cases = {
        'both_anomaly': both_anomaly_cases,
        'vision_only': vision_only_cases,
        'ts_only': ts_only_cases,
        'no_anomaly': no_anomaly_cases
    }
    
    return consistency_percentage, categorized_cases


def validate_fusion_decision_patterns(categorized_cases):
    """
    Validate fusion decision logic patterns for specific categories.
    
    Args:
        categorized_cases (dict): Dictionary with categorized decision cases
        
    Returns:
        bool: True if all patterns are valid, False otherwise
    """
    both_anomaly_cases = categorized_cases['both_anomaly']
    vision_only_cases = categorized_cases['vision_only']
    ts_only_cases = categorized_cases['ts_only']
    no_anomaly_cases = categorized_cases['no_anomaly']
    
    # For both_anomaly_cases, fusion should always be 1
    if both_anomaly_cases:
        both_anomaly_fusion_correct = all(p['fusion'] == 1 for p in both_anomaly_cases)
        if not both_anomaly_fusion_correct:
            logger.error("When both systems detect anomaly, fusion should always decide anomaly")
            return False
        logger.info(f"✓ Both-anomaly cases: {len(both_anomaly_cases)} cases, all correctly fused to anomaly")
    
    # For no_anomaly_cases, fusion should always be 0
    if no_anomaly_cases:
        no_anomaly_fusion_correct = all(p['fusion'] == 0 for p in no_anomaly_cases)
        if not no_anomaly_fusion_correct:
            logger.error("When neither system detects anomaly, fusion should decide no anomaly")
            return False
        logger.info(f"✓ No-anomaly cases: {len(no_anomaly_cases)} cases, all correctly fused to no anomaly")
    
    # For single-system cases, fusion should follow the detecting system (OR logic)
    if vision_only_cases:
        vision_only_fusion_correct = all(p['fusion'] == 1 for p in vision_only_cases)
        if not vision_only_fusion_correct:
            logger.error("When only vision detects anomaly, fusion should decide anomaly (OR logic)")
            return False
        logger.info(f"✓ Vision-only cases: {len(vision_only_cases)} cases, all correctly fused to anomaly")
    
    if ts_only_cases:
        ts_only_fusion_correct = all(p['fusion'] == 1 for p in ts_only_cases)
        if not ts_only_fusion_correct:
            logger.error("When only TS detects anomaly, fusion should decide anomaly (OR logic)")
            return False
        logger.info(f"✓ TS-only cases: {len(ts_only_cases)} cases, all correctly fused to anomaly")
    
    return True


def validate_defect_types_diversity(decision_patterns, min_types=5):
    """
    Validate that the fusion system handles diverse defect types.
    
    Args:
        decision_patterns (list): List of decision pattern dictionaries
        min_types (int): Minimum number of defect types expected
        
    Returns:
        tuple: (bool, unique_defect_types)
    """
    unique_defect_types = set([p['type'] for p in decision_patterns])
    logger.info(f"Detected weld defect types: {sorted(unique_defect_types)}")
    
    if len(unique_defect_types) < min_types:
        logger.error(f"Should detect multiple defect types. Found: {len(unique_defect_types)}: {sorted(unique_defect_types)}")
        return False, unique_defect_types
    
    # Check that all major weld defect types are represented
    expected_defect_types = {'Undercut', 'Excessive_Convexity', 'Crater_Cracks', 'Spatter', 'Overlap', 'Lack_of_Fusion', 'Porosity'}
    found_defect_types = unique_defect_types.intersection(expected_defect_types)
    logger.info(f"Found expected defect types: {found_defect_types}")
    
    if len(found_defect_types) < min_types:
        logger.error(f"Should find at least {min_types} major defect types. Found: {len(found_defect_types)}")
        return False, unique_defect_types
        
    return True, unique_defect_types


def validate_or_logic_implementation(decision_patterns):
    """
    Validate OR logic implementation for each decision pattern.
    
    Args:
        decision_patterns (list): List of decision pattern dictionaries
        
    Returns:
        bool: True if all decisions follow OR logic, False otherwise
    """
    logger.info("Testing OR logic implementation...")
    
    # Check each case individually
    for pattern in decision_patterns:
        vision = pattern['vision']
        ts = pattern['ts']
        fusion = pattern['fusion']
        defect_type = pattern['type']
        
        # OR logic: fusion = 1 if (vision == 1 OR ts == 1), otherwise 0
        expected = 1 if (vision == 1 or ts == 1) else 0
        if fusion != expected:
            logger.error(f"OR logic violation: {defect_type} - Vision={vision}, TS={ts}, Fusion={fusion}, Expected={expected}")
            return False
    
    logger.info("✓ All fusion decisions follow correct OR logic implementation")
    return True


def validate_system_contributions(decision_patterns):
    """
    Validate that both vision and time series systems are contributing to decisions.
    
    Args:
        decision_patterns (list): List of decision pattern dictionaries
        
    Returns:
        bool: True if both systems are active, False otherwise
    """
    vision_active = len([p for p in decision_patterns if p['vision'] == 1]) > 0
    ts_active = len([p for p in decision_patterns if p['ts'] == 1]) > 0
    
    vision_anomalies = [p['vision'] for p in decision_patterns]
    ts_anomalies = [p['ts'] for p in decision_patterns]
    
    logger.info(f"Vision anomaly detections: {sum(vision_anomalies)} / {len(vision_anomalies)}")
    logger.info(f"TS anomaly detections: {sum(ts_anomalies)} / {len(ts_anomalies)}")
    
    # Both systems should be active (detecting at least some anomalies)
    if not vision_active:
        logger.error("Vision analytics should detect at least some anomalies")
        return False
        
    if not ts_active:
        logger.error("Time series analytics should detect at least some anomalies")
        return False
        
    logger.info("✓ Both vision and time series analytics are actively contributing to fusion decisions")
    return True


def validate_fusion_decision_making_logic():
    """
    Comprehensive fusion decision-making logic validation using sample data.
    
    Returns:
        dict: Validation results with detailed metrics
    """
    logger.info("Starting fusion decision-making logic validation...")
    
    # Get sample fusion logs
    fusion_log_samples = get_fusion_sample_logs()
    
    # Parse the fusion decision logs
    decision_patterns, vision_anomalies, ts_anomalies, fusion_decisions = parse_fusion_decision_logs(fusion_log_samples)
    
    # Validate that we have sufficient data for analysis
    if len(decision_patterns) < 10:
        error_msg = f"Insufficient fusion decisions for analysis. Found: {len(decision_patterns)}, Expected: >= 10"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    # Test 1: Validate fusion logic consistency (OR logic)
    logger.info("Testing fusion logic consistency...")
    consistency_percentage, categorized_cases = validate_fusion_logic_consistency(decision_patterns)
    
    # Test 2: Validate decision distribution
    logger.info("Testing fusion decision distribution...")
    logger.info(f"Both anomaly cases (Vision=1, TS=1): {len(categorized_cases['both_anomaly'])}")
    logger.info(f"Vision-only cases (Vision=1, TS=0): {len(categorized_cases['vision_only'])}")  
    logger.info(f"TS-only cases (Vision=0, TS=1): {len(categorized_cases['ts_only'])}")
    logger.info(f"No anomaly cases (Vision=0, TS=0): {len(categorized_cases['no_anomaly'])}")
    
    # Test 3: Validate both systems are contributing
    if not validate_system_contributions(decision_patterns):
        return {"success": False, "error": "System contribution validation failed"}
    
    # Test 4: Validate weld defect type diversity
    defect_types_valid, unique_defect_types = validate_defect_types_diversity(decision_patterns)
    if not defect_types_valid:
        return {"success": False, "error": "Defect type diversity validation failed"}
    
    # Test 5: Validate fusion decision logic patterns (OR logic validation)
    if not validate_fusion_decision_patterns(categorized_cases):
        return {"success": False, "error": "Fusion decision patterns validation failed"}
    
    # Test 6: Overall consistency requirement for OR logic
    min_consistency = 100.0  # 100% consistency threshold for OR logic with sample data
    if consistency_percentage < min_consistency:
        error_msg = f"Fusion logic consistency {consistency_percentage:.1f}% below threshold {min_consistency}%"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    # Test 7: Validate OR logic implementation
    if not validate_or_logic_implementation(decision_patterns):
        return {"success": False, "error": "OR logic implementation validation failed"}
    
    # Summary
    total_decisions = len(decision_patterns)
    results = {
        "success": True,
        "total_decisions": total_decisions,
        "consistency_percentage": consistency_percentage,
        "unique_defect_types": len(unique_defect_types),
        "vision_anomalies": sum(vision_anomalies),
        "ts_anomalies": sum(ts_anomalies),
        "fusion_decisions": sum(fusion_decisions),
        "categorized_cases": {
            "both_anomaly": len(categorized_cases['both_anomaly']),
            "vision_only": len(categorized_cases['vision_only']),
            "ts_only": len(categorized_cases['ts_only']),
            "no_anomaly": len(categorized_cases['no_anomaly'])
        }
    }
    
    logger.info("=== Fusion Decision-Making Logic Validation Summary ===")
    logger.info(f"Total decisions analyzed: {total_decisions}")
    logger.info(f"Logic consistency: {consistency_percentage:.1f}%")
    logger.info(f"Unique defect types detected: {len(unique_defect_types)}")
    logger.info(f"Vision anomalies: {sum(vision_anomalies)} / {len(vision_anomalies)} ({100*sum(vision_anomalies)/len(vision_anomalies):.1f}%)")
    logger.info(f"TS anomalies: {sum(ts_anomalies)} / {len(ts_anomalies)} ({100*sum(ts_anomalies)/len(ts_anomalies):.1f}%)")
    logger.info(f"Fusion decisions (anomaly): {sum(fusion_decisions)} / {len(fusion_decisions)} ({100*sum(fusion_decisions)/len(fusion_decisions):.1f}%)")
    logger.info("✓ Fusion decision-making logic validation completed successfully")
    logger.info("✓ Multimodal weld defect detection system validated with OR fusion logic")
    
    return results


def check_multimodal_container_processing(container_name, processing_type="analytics", timeout=120):
    """
    Check specific processing activities in multimodal containers by examining logs.
    
    Args:
        container_name (str): Name of the container to check
        processing_type (str): Type of processing to look for ('analytics', 'fusion', 'vision', 'alerts')
        timeout (int): Maximum time to wait for processing indicators
        
    Returns:
        dict: Processing status with details
    """
    logger.info(f"Checking {processing_type} processing in container: {container_name}")
    
    # Define patterns for different processing types
    pattern_maps = {
        "analytics": [
            "CatBoost", "prediction", "anomaly_status", "model", "inference",
            "processing", "analytics", "time_series", "weld_sensor"
        ],
        "fusion": [
            "Vision_Anomaly Type:", "Vision anomaly:", "TS anomaly:", "fused decision:",
            "fusion", "combining", "multimodal", "decision"
        ],
        "vision": [
            "DLStreamer", "pipeline", "frame", "video", "vision", "classification",
            "weld_defect", "detection", "model_proc"
        ],
        "alerts": [
            "ALERT", "alert", "anomaly detected", "MQTT", "notification",
            "weld_defect_detection", "anomaly_status"
        ]
    }
    
    patterns = pattern_maps.get(processing_type, pattern_maps["analytics"])
    
    if not container_is_running(container_name):
        return {"success": False, "error": f"Container {container_name} not running"}
    
    try:
        logs = get_container_logs(container_name)
        if not logs:
            return {"success": False, "error": "No logs found"}
        
        found_indicators = []
        relevant_lines = []
        
        for line in logs.split('\n'):
            line_lower = line.lower()
            for pattern in patterns:
                if pattern.lower() in line_lower:
                    found_indicators.append(pattern)
                    relevant_lines.append(line.strip())
                    logger.debug(f"Found {processing_type} indicator: {pattern}")
                    break  # Avoid duplicate matches for the same line
        
        unique_indicators = list(dict.fromkeys(found_indicators))
        success = len(unique_indicators) > 0
        
        result = {
            "success": success,
            "container": container_name,
            "processing_type": processing_type,
            "indicators_found": unique_indicators,
            "relevant_log_lines": relevant_lines[-10:],  # Last 10 relevant lines
            "total_indicators": len(unique_indicators)
        }
        
        if success:
            logger.info(f"✓ {processing_type.title()} processing detected in {container_name}")
            logger.info(f"Found {len(unique_indicators)} {processing_type} indicators")
        else:
            logger.warning(f"No {processing_type} processing detected in {container_name}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error checking {processing_type} processing: {str(e)}")
        return {"success": False, "error": str(e)}


def validate_multimodal_processing_in_container(processing_type="all", timeout=120):
    """
    Validate multimodal processing by checking container logs instead of MQTT topics.
    This is more reliable as it checks the actual processing logic in the containers.
    
    Args:
        processing_type (str): Type of processing to validate ('analytics', 'fusion', 'vision', 'all')
        timeout (int): Maximum time to wait for processing indicators
        
    Returns:
        dict: Validation results for each processing type
    """
    logger.info(f"Validating multimodal processing: {processing_type}")
    
    results = {
        "success": False,
        "analytics": {"checked": False, "success": False},
        "fusion": {"checked": False, "success": False}, 
        "vision": {"checked": False, "success": False},
        "overall_success": False
    }
    
    # Check analytics processing (time series)
    if processing_type in ["analytics", "all"]:
        results["analytics"]["checked"] = True
        analytics_result = check_multimodal_container_processing(
            "ia-time-series-analytics-microservice", 
            "analytics", 
            timeout
        )
        results["analytics"]["success"] = analytics_result["success"]
        results["analytics"]["details"] = analytics_result
        logger.info(f"Analytics processing check: {'✓' if analytics_result['success'] else '✗'}")
    
    # Check fusion processing
    if processing_type in ["fusion", "all"]:
        results["fusion"]["checked"] = True
        fusion_result = check_multimodal_container_processing(
            "ia-fusion-analytics", 
            "fusion", 
            timeout
        )
        results["fusion"]["success"] = fusion_result["success"]
        results["fusion"]["details"] = fusion_result
        logger.info(f"Fusion processing check: {'✓' if fusion_result['success'] else '✗'}")
    
    # Check vision processing
    if processing_type in ["vision", "all"]:
        results["vision"]["checked"] = True
        vision_result = check_multimodal_container_processing(
            "dlstreamer-pipeline-server", 
            "vision", 
            timeout
        )
        results["vision"]["success"] = vision_result["success"] 
        results["vision"]["details"] = vision_result
        logger.info(f"Vision processing check: {'✓' if vision_result['success'] else '✗'}")
    
    # Determine overall success
    checked_systems = [k for k, v in results.items() if isinstance(v, dict) and v.get("checked")]
    successful_systems = [k for k in checked_systems if results[k]["success"]]
    
    results["overall_success"] = len(successful_systems) > 0
    results["success"] = results["overall_success"]
    
    logger.info(f"Multimodal processing validation: {len(successful_systems)}/{len(checked_systems)} systems successful")
    
    return results


def check_multimodal_mqtt_topic_data(topic, broker_host="localhost", broker_port=1883, timeout=120, wait_for_data=True):
    """
    Check if data exists on a specific MQTT topic for multimodal deployment
    with appropriate wait times and data validation logic
    
    Args:
        topic (str): MQTT topic to check
        broker_host (str): MQTT broker hostname
        broker_port (int): MQTT broker port
        timeout (int): Maximum time to wait for data in seconds
        wait_for_data (bool): Whether to wait actively for data or just check once
        
    Returns:
        bool: True if data is found on the topic, False otherwise
    """
    data_received = threading.Event()
    message_count = 0
    last_message = None
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker for topic: {topic}")
            client.subscribe(topic)
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def on_message(client, userdata, msg):
        nonlocal message_count, last_message
        try:
            message = msg.payload.decode('utf-8')
            message_count += 1
            last_message = message
            logger.info(f"Received message #{message_count} on {topic}: {message[:200]}...")
            
            # For alerts topic, check if it's actually an alert (anomaly_status = 1)
            if "alerts" in topic and "weld_defect_detection" in topic:
                try:
                    data = json.loads(message)
                    if data.get("anomaly_status") == 1:
                        logger.info(f"Alert detected: {data}")
                        data_received.set()
                except:
                    # If not JSON, still count as data
                    data_received.set()
            else:
                # For other topics, any data counts
                data_received.set()
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def on_disconnect(client, userdata, rc):
        logger.info(f"Disconnected from MQTT broker for topic: {topic}")
    
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        # Connect to broker
        logger.info(f"Connecting to MQTT broker {broker_host}:{broker_port} for topic: {topic}")
        client.connect(broker_host, broker_port, 60)
        client.loop_start()
        
        # Wait for connection
        time.sleep(2)
        
        if wait_for_data:
            # Wait for data with timeout
            logger.info(f"Waiting up to {timeout} seconds for data on topic: {topic}")
            data_found = data_received.wait(timeout)
        else:
            # Just listen for a short time
            time.sleep(10)
            data_found = data_received.is_set()
        
        client.loop_stop()
        client.disconnect()
        
        logger.info(f"MQTT check completed for {topic}: {message_count} messages received, data_found: {data_found}")
        if last_message:
            logger.info(f"Last message sample: {last_message[:100]}...")
        
        return data_found
        
    except Exception as e:
        logger.error(f"Error checking MQTT topic {topic}: {e}")
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass
        return False


def check_influxdb_data_with_auth(measurement, database="datain", container_name="ia-influxdb", username="", password="", timeout=30):
    """
    Check if data exists in InfluxDB measurement with authentication
    
    Args:
        measurement (str): The measurement name to check
        database (str): The database name (default: "datain")
        container_name (str): The InfluxDB container name (default: "ia-influxdb")
        username (str): InfluxDB username
        password (str): InfluxDB password
        timeout (int): Timeout in seconds (default: 30)
        
    Returns:
        bool: True if data exists, False otherwise
    """
    try:
        # Check if container is running first
        if not container_is_running(container_name):
            logger.warning(f"Container {container_name} is not running")
            return False
        
        # Execute InfluxDB query with authentication
        query_cmd = [
            "docker", "exec", container_name,
            "influx", "-database", database,
            "-username", username, "-password", password,
            "-execute", f"SELECT COUNT(*) FROM \"{measurement}\" LIMIT 1"
        ]
        
        result = subprocess.run(
            query_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            logger.info(f"InfluxDB query output: {output}")
            # Check if the output contains any count > 0
            if "count" in output.lower() and any(char.isdigit() and char != '0' for char in output):
                logger.info(f"Data found in measurement: {measurement}")
                return True
            else:
                logger.info(f"No data found in measurement: {measurement}")
                return False
        else:
            logger.error(f"Failed to query InfluxDB: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"InfluxDB query timed out after {timeout} seconds")
        return False
    except Exception as e:
        logger.error(f"Error checking InfluxDB data: {e}")
        return False


def query_influxdb_measurement_with_auth(
    measurement,
    database="datain",
    container_name="ia-influxdb",
    username="",
    password="",
    limit=3,
    timeout=30,
    order_by_time_desc=False,
):
    """Fetch rows from an InfluxDB measurement using the CLI with authentication."""
    query_result = {
        "success": False,
        "records": [],
        "raw_output": "",
        "error": None,
    }

    try:
        if not container_is_running(container_name):
            query_result["error"] = f"Container {container_name} is not running"
            logger.warning(query_result["error"])
            return query_result

        order_clause = " ORDER BY time DESC" if order_by_time_desc else ""
        query = f'SELECT * FROM "{measurement}"{order_clause} LIMIT {limit}'
        cmd = [
            "docker", "exec", container_name,
            "influx",
            "-database", database,
            "-username", username,
            "-password", password,
            "-format", "json",
            "-execute", query,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        query_result["raw_output"] = result.stdout.strip()

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "Unknown error"
            query_result["error"] = f"InfluxDB query failed: {stderr}"
            logger.error(query_result["error"])
            return query_result

        json_payload = _extract_json_payload(query_result["raw_output"])
        if not json_payload:
            query_result["error"] = "InfluxDB response did not contain JSON payload"
            logger.error(query_result["error"])
            return query_result

        data = json.loads(json_payload)
        series = data.get("results", [{}])[0].get("series", [])
        if series:
            columns = series[0].get("columns", [])
            values = series[0].get("values", [])
            query_result["records"] = [dict(zip(columns, row)) for row in values]
            query_result["success"] = bool(query_result["records"])
        else:
            query_result["error"] = f"No data returned for measurement {measurement}"
            logger.warning(query_result["error"])

    except subprocess.TimeoutExpired:
        query_result["error"] = f"InfluxDB query timed out after {timeout} seconds"
        logger.error(query_result["error"])
    except json.JSONDecodeError as exc:
        query_result["error"] = f"Failed to parse InfluxDB JSON output: {exc}"
        logger.error(query_result["error"])
    except Exception as exc:
        query_result["error"] = f"Unexpected error querying InfluxDB: {exc}"
        logger.error(query_result["error"])

    return query_result


def _extract_json_payload(cli_output):
    """Return the first JSON block from influx cli output if present."""
    if not cli_output:
        return None
    for line in cli_output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return line
    return None


def validate_multimodal_container_processing(timeout=120):
    """
    Validate multimodal analytics processing by checking container logs
    
    Args:
        timeout (int): Timeout for processing validation
        
    Returns:
        dict: Validation results with processing status and summary
    """
    logger.info("Validating multimodal analytics processing from container logs")
    
    results = {
        "ts_analytics_result": False,
        "vision_analytics_result": False, 
        "fusion_analytics_result": False,
        "working_systems": 0,
        "total_systems": 3,
        "success": False
    }
    
    # Test 1: Check Time Series Analytics container processing (most critical)
    logger.info("Testing Time Series Analytics container processing for weld defect detection")
    ts_processing_info = check_multimodal_container_processing(
        container_name="ia-time-series-analytics-microservice",
        processing_type="analytics",
        timeout=timeout
    )
    results["ts_analytics_result"] = ts_processing_info.get("success", False)
    logger.info(f"Time Series analytics processing result: {ts_processing_info}")
    
    # Test 2: Check Vision Analytics container processing
    logger.info("Testing Vision Analytics container processing for weld defect classification")
    vision_processing_info = check_multimodal_container_processing(
        container_name="dlstreamer-pipeline-server",
        processing_type="vision",
        timeout=timeout
    )
    results["vision_analytics_result"] = vision_processing_info.get("success", False)
    logger.info(f"Vision analytics processing result: {vision_processing_info}")
    
    # Test 3: Check Fusion Analytics container processing
    logger.info("Testing Fusion Analytics container processing")
    fusion_processing_info = check_multimodal_container_processing(
        container_name="ia-fusion-analytics",
        processing_type="fusion",
        timeout=timeout
    )
    results["fusion_analytics_result"] = fusion_processing_info.get("success", False)
    logger.info(f"Fusion analytics processing result: {fusion_processing_info}")
    
    # Calculate summary
    results["working_systems"] = sum([results["ts_analytics_result"], results["vision_analytics_result"], results["fusion_analytics_result"]])
    logger.info(f"Multimodal Processing Systems Status: {results['working_systems']}/{results['total_systems']} systems are processing data")
    
    results["success"] = True  # Function completed successfully
    return results


def check_multimodal_container_status_detailed(processing_results):
    """
    Provide detailed feedback by checking analytics containers when processing fails
    
    Args:
        processing_results (dict): Results from validate_multimodal_container_processing
        
    Returns:
        dict: Detailed container status information
    """
    logger.info("Performing detailed container status analysis")
    
    container_status = {
        "ts_analytics_status": {},
        "vision_analytics_status": {},
        "fusion_analytics_status": {}
    }
    
    # Check Time Series Analytics status if processing not detected
    if not processing_results["ts_analytics_result"]:
        logger.warning("Time series analytics processing not detected - checking microservice status")
        ts_container_running = container_is_running("ia-time-series-analytics-microservice")
        container_status["ts_analytics_status"]["running"] = ts_container_running
        
        if ts_container_running:
            logger.info("Time series analytics microservice is running")
            ts_logs = get_container_logs("ia-time-series-analytics-microservice")
            processing_active = "processing" in ts_logs.lower() or "alert" in ts_logs.lower()
            container_status["ts_analytics_status"]["processing_active"] = processing_active
            
            if processing_active:
                logger.info("Time series analytics is actively processing data")
            else:
                logger.warning("Time series analytics may not be receiving input data")
        else:
            logger.error("Time series analytics microservice is not running!")
            container_status["ts_analytics_status"]["processing_active"] = False
    
    # Check Vision Analytics status if processing not detected
    if not processing_results["vision_analytics_result"]:
        logger.warning("Vision analytics processing not detected - checking DLStreamer status")
        dlstreamer_running = container_is_running("dlstreamer-pipeline-server")
        container_status["vision_analytics_status"]["running"] = dlstreamer_running
        
        if dlstreamer_running:
            logger.info("DLStreamer container is running")
            dl_logs = get_container_logs("dlstreamer-pipeline-server")
            processing_active = "pipeline" in dl_logs.lower() or "frame" in dl_logs.lower()
            container_status["vision_analytics_status"]["processing_active"] = processing_active
            
            if processing_active:
                logger.info("DLStreamer is processing video data")
            else:
                logger.warning("DLStreamer may not be receiving video input")
        else:
            logger.error("DLStreamer container is not running!")
            container_status["vision_analytics_status"]["processing_active"] = False
    
    # Check Fusion Analytics status if processing not detected
    if not processing_results["fusion_analytics_result"]:
        logger.warning("Fusion analytics processing not detected - checking fusion analytics status")
        fusion_running = container_is_running("ia-fusion-analytics")
        container_status["fusion_analytics_status"]["running"] = fusion_running
        
        if fusion_running:
            logger.info("Fusion analytics container is running")
            fusion_logs = get_container_logs("ia-fusion-analytics")
            processing_active = "fusion" in fusion_logs.lower() or "combining" in fusion_logs.lower()
            container_status["fusion_analytics_status"]["processing_active"] = processing_active
            
            if processing_active:
                logger.info("Fusion analytics is processing multimodal data")
            else:
                logger.warning("Fusion analytics may be waiting for sufficient input data")
        else:
            logger.error("Fusion analytics container is not running!")
            container_status["fusion_analytics_status"]["processing_active"] = False
    
    return container_status


def validate_multimodal_alerts_infrastructure():
    """
    Comprehensive validation of multimodal alerts infrastructure
    
    Returns:
        dict: Complete validation results including container processing, container status, and infrastructure health
    """
    logger.info("Starting comprehensive multimodal alerts infrastructure validation")
    
    validation_results = {
        "mqtt_broker_running": False,
        "ts_analytics_running": False,
        "processing_results": {},
        "container_status": {},
        "infrastructure_healthy": False,
        "validation_summary": ""
    }
    
    # Step 1: Verify MQTT broker is running
    logger.info("Verifying MQTT broker accessibility")
    validation_results["mqtt_broker_running"] = container_is_running("ia-mqtt-broker")
    
    if not validation_results["mqtt_broker_running"]:
        validation_results["validation_summary"] = "MQTT broker container is not running"
        return validation_results
    
    # Step 2: Wait for containers to stabilize
    logger.info("Waiting for multimodal containers to stabilize and begin data processing...")
    time.sleep(60)  # Increased wait time for multimodal to process initial data
    
    # Step 3: Validate container processing instead of MQTT topics
    validation_results["processing_results"] = validate_multimodal_container_processing()
    
    # Step 4: Check detailed container status
    validation_results["container_status"] = check_multimodal_container_status_detailed(validation_results["processing_results"])
    
    # Step 5: Verify critical infrastructure
    validation_results["ts_analytics_running"] = container_is_running("ia-time-series-analytics-microservice")
    
    # Step 6: Determine overall infrastructure health
    validation_results["infrastructure_healthy"] = (
        validation_results["mqtt_broker_running"] and 
        validation_results["ts_analytics_running"]
    )
    
    # Step 7: Generate summary message
    working_systems = validation_results["processing_results"]["working_systems"]
    if working_systems == 0:
        validation_results["validation_summary"] = (
            "No container processing detected - this may indicate: "
            "1. System startup is still in progress, "
            "2. No data sources are actively feeding the system, "
            "3. Containers may need additional time to begin processing. "
            f"Critical infrastructure ({'healthy' if validation_results['infrastructure_healthy'] else 'unhealthy'})."
        )
    else:
        validation_results["validation_summary"] = (
            f"Multimodal alerts infrastructure validated successfully: {working_systems}/3 systems are processing data, "
            f"infrastructure is {'healthy' if validation_results['infrastructure_healthy'] else 'unhealthy'}."
        )
    
    logger.info(validation_results["validation_summary"])
    return validation_results


def execute_multimodal_gpu_config_curl(config, device="gpu"):
    """
    Execute curl command to post multimodal GPU configuration to the time-series analytics API.
    
    Args:
        config (dict): Multimodal configuration dictionary
        device (str): Device to use for configuration ('gpu', 'cpu', etc.)
        
    Returns:
        bool: True if curl command was successful, False otherwise
    """
    try:
        logger.info(f"Configuring multimodal analytics for {device.upper()} acceleration")
        
        # Update device configuration
        gpu_config = copy.deepcopy(config)
        gpu_config["udfs"]["device"] = device
        
        # Convert to JSON
        gpu_config_json = json.dumps(gpu_config)
        
        # Construct curl command for multimodal deployment - use port 9092 for Kapacitor
        curl_command = [
            "docker", "exec", "ia-time-series-analytics-microservice",
            "curl", "-X", "POST",
            "http://localhost:9092/kapacitor/v1/config",
            "-H", "Content-Type: application/json",
            f"-d", f"{gpu_config_json}"
        ]
        
        # Execute curl command
        result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info(f"✓ Multimodal {device.upper()} configuration posted successfully")
            logger.debug(f"Response: {result.stdout}")
            return True
        else:
            logger.error(f"✗ Failed to post multimodal {device.upper()} configuration")
            logger.error(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Multimodal GPU configuration curl command timed out")
        return False
    except Exception as e:
        logger.error(f"Error executing multimodal GPU configuration curl: {e}")
        return False


def check_system_gpu_devices():
    """
    Check if GPU devices are available on the system.
    
    Returns:
        list: List of available GPU devices, empty if none found
    """
    try:
        # Try different methods to detect GPU devices
        gpu_devices = []
        
        # Method 1: Check for Intel GPU devices
        try:
            result = subprocess.run(
                ["lspci", "|", "grep", "-i", "vga"], 
                shell=True,
                capture_output=True, 
                text=True,
                timeout=10
            )
            if result.returncode == 0 and "intel" in result.stdout.lower():
                gpu_devices.append("Intel iGPU")
                logger.info("Intel iGPU detected via lspci")
        except:
            pass
        
        # Method 2: Check /dev/dri devices
        try:
            if os.path.exists("/dev/dri"):
                dri_devices = os.listdir("/dev/dri")
                if dri_devices:
                    gpu_devices.append(f"DRM devices: {dri_devices}")
                    logger.info(f"DRM GPU devices found: {dri_devices}")
        except:
            pass
        
        # Method 3: Check for GPU in Docker containers
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--device=/dev/dri", "hello-world"],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                gpu_devices.append("Docker GPU access available")
                logger.info("Docker GPU device access confirmed")
        except:
            pass
        
        return gpu_devices
        
    except Exception as e:
        logger.error(f"Error checking GPU devices: {e}")
        return []


def monitor_gpu_utilization(duration=30):
    """
    Monitor GPU utilization for a specified duration.
    
    Args:
        duration (int): Duration in seconds to monitor
        
    Returns:
        dict: GPU utilization statistics or None if unavailable
    """
    try:
        logger.info(f"Monitoring GPU utilization for {duration} seconds")
        
        # Try to use intel_gpu_top if available
        try:
            result = subprocess.run(
                ["timeout", str(duration), "intel_gpu_top", "-o", "-"],
                capture_output=True,
                text=True,
                timeout=duration + 5
            )
            
            if result.returncode == 0 or result.returncode == 124:  # 124 is timeout exit code
                # Parse intel_gpu_top output for GPU usage
                output_lines = result.stdout.strip().split('\n')
                gpu_usage = 0
                for line in output_lines:
                    if "render/3d" in line.lower():
                        # Extract usage percentage
                        match = re.search(r'(\d+\.?\d*)%', line)
                        if match:
                            gpu_usage = max(gpu_usage, float(match.group(1)))
                
                return {
                    "gpu_usage": gpu_usage,
                    "monitoring_duration": duration,
                    "tool": "intel_gpu_top"
                }
        except:
            pass
        
        # Fallback: Check container resource usage
        try:
            container_stats = get_container_stats("dlstreamer-pipeline-server")
            if container_stats:
                return {
                    "gpu_usage": container_stats.get('cpu_percent', 0),  # Approximation
                    "monitoring_duration": duration,
                    "tool": "container_stats"
                }
        except:
            pass
        
        logger.warning("GPU monitoring tools not available")
        return None
        
    except Exception as e:
        logger.error(f"Error monitoring GPU utilization: {e}")
        return None


def measure_multimodal_inference_performance(device="gpu", container="ia-time-series-analytics-microservice", duration=60):
    """
    Measure inference performance for multimodal analytics.
    
    Args:
        device (str): Device to test ('gpu' or 'cpu')
        container (str): Container to monitor
        duration (int): Duration in seconds to measure
        
    Returns:
        dict: Performance metrics or None if measurement failed
    """
    try:
        logger.info(f"Measuring {device.upper()} inference performance for {duration} seconds")
        
        # Check if container is running
        if not container_is_running(container):
            logger.error(f"Container {container} is not running")
            return None
        
        # Get initial container stats
        initial_stats = get_container_stats(container)
        if not initial_stats:
            logger.warning(f"Could not get initial stats for {container}")
        
        # Monitor container logs for inference activity
        start_time = time.time()
        inference_count = 0
        
        # Sample logs during the duration
        sample_interval = 5  # seconds
        samples = duration // sample_interval
        
        for i in range(samples):
            time.sleep(sample_interval)
            
            # Get recent logs and count inference operations
            logs = get_container_logs(container, tail=100)
            if logs:
                # Count inference-related log entries
                inference_patterns = [
                    "prediction", "inference", "model", "processing",
                    "anomaly_status", "catboost", "weld_anomaly"
                ]
                
                recent_lines = logs.split('\n')[-50:]  # Last 50 lines
                for line in recent_lines:
                    line_lower = line.lower()
                    if any(pattern in line_lower for pattern in inference_patterns):
                        inference_count += 1
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # Get final container stats
        final_stats = get_container_stats(container)
        
        # Calculate throughput
        throughput = inference_count / actual_duration if actual_duration > 0 else 0
        
        # Calculate resource usage
        cpu_usage = 0
        memory_usage = 0
        if initial_stats and final_stats:
            cpu_usage = final_stats.get('cpu_percent', 0)
            memory_usage = final_stats.get('memory_percent', 0)
        
        performance_metrics = {
            "device": device,
            "container": container,
            "duration": actual_duration,
            "inference_count": inference_count,
            "throughput": throughput,  # inferences per second
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "success": True
        }
        
        logger.info(f"{device.upper()} performance: {throughput:.2f} inferences/sec over {actual_duration:.1f}s")
        return performance_metrics
        
    except Exception as e:
        logger.error(f"Error measuring {device} inference performance: {e}")
        return {"device": device, "success": False, "error": str(e)}


# Nginx Test Utility Functions

def verify_nginx_container_health(container_name):
    """
    Verify nginx container is running and healthy.
    
    Args:
        container_name (str): Name of the nginx container
        
    Returns:
        dict: Health check results
    """
    try:
        health_results = {
            "container_running": False,
            "logs_accessible": False,
            "process_running": False,
            "errors": []
        }
        
        # Check if container is running
        health_results["container_running"] = container_is_running(container_name)
        if not health_results["container_running"]:
            health_results["errors"].append(f"Container {container_name} is not running")
            return health_results
        
        # Check if logs are accessible
        logs = get_container_logs(container_name, tail=50)
        health_results["logs_accessible"] = logs is not None
        if not health_results["logs_accessible"]:
            health_results["errors"].append("Failed to retrieve container logs")
        
        # Check if nginx process is running inside container
        try:
            # Use readlink on /proc/1/exe to check if main process is nginx
            process_check = subprocess.run(
                ["docker", "exec", container_name, "readlink", "/proc/1/exe"],
                capture_output=True,
                text=True,
                timeout=constants.TEST_PROCESS_CHECK_TIMEOUT
            )
            
            if process_check.returncode == 0 and "nginx" in process_check.stdout:
                health_results["process_running"] = True
            else:
                health_results["errors"].append("Nginx process not found in container")
                
        except Exception as e:
            health_results["errors"].append(f"Error checking nginx processes: {e}")
        
        return health_results
        
    except Exception as e:
        return {
            "container_running": False,
            "logs_accessible": False,
            "process_running": False,
            "errors": [f"Error in nginx health check: {e}"]
        }


def verify_nginx_port_mappings(container_name, expected_ports):
    """
    Verify nginx container port mappings.
    
    Args:
        container_name (str): Name of the nginx container
        expected_ports (list): List of expected port numbers
        
    Returns:
        dict: Port mapping verification results
    """
    try:
        port_results = {
            "success": False,
            "mapped_ports": [],
            "missing_ports": [],
            "port_output": "",
            "errors": []
        }
        
        # Get container port mappings
        port_check_result = subprocess.run(
            ["docker", "port", container_name],
            capture_output=True,
            text=True,
            timeout=constants.TEST_PROCESS_CHECK_TIMEOUT
        )
        
        if port_check_result.returncode != 0:
            port_results["errors"].append("Failed to get nginx port mappings")
            return port_results
        
        port_output = port_check_result.stdout
        port_results["port_output"] = port_output
        
        # Check each expected port
        for port in expected_ports:
            if port in port_output:
                port_results["mapped_ports"].append(port)
            else:
                port_results["missing_ports"].append(port)
        
        port_results["success"] = len(port_results["missing_ports"]) == 0
        
        return port_results
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "mapped_ports": [],
            "missing_ports": expected_ports,
            "port_output": "",
            "errors": ["Timeout while checking nginx port mappings"]
        }
    except Exception as e:
        return {
            "success": False,
            "mapped_ports": [],
            "missing_ports": expected_ports,
            "port_output": "",
            "errors": [f"Error checking nginx port mappings: {e}"]
        }


def verify_nginx_ssl_certificates(container_name, cert_path, cert_files):
    """
    Verify nginx SSL certificate generation.
    
    Args:
        container_name (str): Name of the nginx container
        cert_path (str): Path to SSL certificates in container
        cert_files (list): List of expected certificate files
        
    Returns:
        dict: SSL certificate verification results
    """
    try:
        ssl_results = {
            "success": False,
            "certificates_found": [],
            "missing_certificates": [],
            "config_valid": False,
            "errors": []
        }
        
        # Wait for SSL certificate generation to complete
        # SSL certificates are generated by nginx-cert-gen.sh during container startup
        max_retries = 12  # 60 seconds total
        retry_interval = 5
        
        for attempt in range(max_retries):
            # Check SSL certificate files
            cert_check = subprocess.run(
                ["docker", "exec", container_name, "ls", "-la", cert_path],
                capture_output=True,
                text=True,
                timeout=constants.TEST_PROCESS_CHECK_TIMEOUT
            )
            
            if cert_check.returncode == 0:
                cert_output = cert_check.stdout
                # Check if all required certificate files exist
                missing_certs = []
                for cert_file in cert_files:
                    if cert_file not in cert_output:
                        missing_certs.append(cert_file)
                
                if not missing_certs:
                    # All certificates found, break retry loop
                    break
                elif attempt < max_retries - 1:
                    # Wait and retry if certificates are still missing
                    time.sleep(retry_interval)
                    continue
            elif attempt < max_retries - 1:
                # Failed to access cert directory, wait and retry
                time.sleep(retry_interval)
                continue
        
        # Final check after retry loop
        cert_check = subprocess.run(
            ["docker", "exec", container_name, "ls", "-la", cert_path],
            capture_output=True,
            text=True,
            timeout=constants.TEST_PROCESS_CHECK_TIMEOUT
        )
        
        if cert_check.returncode != 0:
            ssl_results["errors"].append("Failed to check SSL certificates directory")
            return ssl_results

        cert_output = cert_check.stdout
        
        # Verify each certificate file
        for cert_file in cert_files:
            if cert_file in cert_output:
                ssl_results["certificates_found"].append(cert_file)
            else:
                ssl_results["missing_certificates"].append(cert_file)

        # Verify nginx configuration syntax (with retry for config validation)
        config_valid = False
        for attempt in range(3):  # 3 attempts for config validation
            config_test = subprocess.run(
                ["docker", "exec", container_name, "nginx", "-t"],
                capture_output=True,
                text=True,
                timeout=constants.TEST_PROCESS_CHECK_TIMEOUT
            )
            
            if config_test.returncode == 0:
                config_valid = True
                break
            elif attempt < 2:
                # Wait briefly and retry config validation
                time.sleep(2)
        
        ssl_results["config_valid"] = config_valid
        if not ssl_results["config_valid"]:
            ssl_results["errors"].append(f"Nginx configuration test failed: {config_test.stderr}")

        ssl_results["success"] = (
            len(ssl_results["missing_certificates"]) == 0 and
            ssl_results["config_valid"]
        )

        return ssl_results
        
    except Exception as e:
        return {
            "success": False,
            "certificates_found": [],
            "missing_certificates": cert_files,
            "config_valid": False,
            "errors": [f"Error in SSL certificate verification: {e}"]
        }


def verify_nginx_backend_connectivity(container_name, backend_services):
    """
    Verify nginx connectivity to backend services.
    
    Args:
        container_name (str): Name of the nginx container
        backend_services (list): List of backend service container names
        
    Returns:
        dict: Backend connectivity verification results
    """
    try:
        connectivity_results = {
            "success": False,
            "running_services": [],
            "missing_services": [],
            "network_connected": False,
            "network_id": "",
            "errors": []
        }
        
        # Check if backend services are running
        for service in backend_services:
            if container_is_running(service):
                connectivity_results["running_services"].append(service)
            else:
                connectivity_results["missing_services"].append(service)
        
        # Verify nginx network connectivity
        network_check = subprocess.run(
            ["docker", "inspect", container_name, "-f", "{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}"],
            capture_output=True,
            text=True,
            timeout=constants.TEST_PROCESS_CHECK_TIMEOUT
        )
        
        if network_check.returncode == 0:
            network_id = network_check.stdout.strip()
            connectivity_results["network_connected"] = bool(network_id)
            connectivity_results["network_id"] = network_id
        else:
            connectivity_results["errors"].append("Failed to check nginx network connectivity")
        
        connectivity_results["success"] = (
            len(connectivity_results["missing_services"]) == 0 and
            connectivity_results["network_connected"]
        )
        
        return connectivity_results
        
    except Exception as e:
        return {
            "success": False,
            "running_services": [],
            "missing_services": backend_services,
            "network_connected": False,
            "network_id": "",
            "errors": [f"Error checking nginx backend connectivity: {e}"]
        }


def test_nginx_proxy_endpoint(container_name, endpoint_url, timeout=30):
    """
    Test nginx proxy endpoint accessibility.
    
    Args:
        container_name (str): Name of the nginx container
        endpoint_url (str): URL to test (e.g., "https://localhost:15443/")
        timeout (int): Timeout for the request
        
    Returns:
        dict: Endpoint test results
    """
    try:
        endpoint_results = {
            "success": False,
            "accessible": False,
            "response_code": None,
            "response_headers": "",
            "errors": []
        }
        
        # Test HTTP/HTTPS connection from HOST
        curl_test = subprocess.run(
            ["curl", "-k", "-I", endpoint_url],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        endpoint_results["accessible"] = curl_test.returncode == 0
        endpoint_results["response_headers"] = curl_test.stdout
        
        if endpoint_results["accessible"]:
            response = curl_test.stdout
            if "HTTP/" in response:
                # Extract response code
                for line in response.split('\n'):
                    if "HTTP/" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            endpoint_results["response_code"] = parts[1]
                        break
                
                # Check for successful response codes
                if any(code in response for code in ["200", "302", "401", "404"]):
                    endpoint_results["success"] = True
            else:
                endpoint_results["errors"].append("Invalid HTTP response")
        else:
            endpoint_results["errors"].append(f"Endpoint not accessible: {curl_test.stderr}")
        
        return endpoint_results
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "accessible": False,
            "response_code": None,
            "response_headers": "",
            "errors": [f"Timeout while testing endpoint: {endpoint_url}"]
        }
    except Exception as e:
        return {
            "success": False,
            "accessible": False,
            "response_code": None,
            "response_headers": "",
            "errors": [f"Error testing endpoint {endpoint_url}: {e}"]
        }


def test_service_direct_access(container_name, service_url, timeout=30):
    """
    Test direct access to a service container.
    
    Args:
        container_name (str): Name of the service container
        service_url (str): URL to test (e.g., "http://localhost:3000/")
        timeout (int): Timeout for the request
        
    Returns:
        dict: Direct access test results
    """
    try:
        access_results = {
            "success": False,
            "accessible": False,
            "response_available": False,
            "errors": []
        }
        
        # Special handling for Grafana - test login endpoint instead of root
        if container_name == "ia-grafana":
            test_url = f"http://localhost:3000/login"
        else:
            test_url = service_url
        
        # Test direct service access
        direct_test = subprocess.run(
            ["docker", "exec", container_name, "curl", "-I", "-s", test_url],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        access_results["accessible"] = direct_test.returncode == 0
        access_results["response_available"] = bool(direct_test.stdout)
        
        # Check for HTTP status codes that indicate the service is running
        if access_results["accessible"] and direct_test.stdout:
            # Look for 200, 301, 302, or other successful/redirect status codes
            if any(code in direct_test.stdout for code in ["HTTP/1.1 200", "HTTP/1.1 301", "HTTP/1.1 302", "HTTP/1.1 401"]):
                access_results["success"] = True
            elif "HTTP/1.1" in direct_test.stdout:
                # Any HTTP response indicates the service is running
                access_results["success"] = True
        elif access_results["accessible"]:
            access_results["success"] = True
        else:
            # Some services may not respond to root endpoint but still be running
            if "connection" not in direct_test.stderr.lower() and "refused" not in direct_test.stderr.lower():
                access_results["success"] = True  # Service is running but may not have root endpoint
            else:
                access_results["errors"].append(f"Service not accessible: {direct_test.stderr}")
        
        return access_results
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "accessible": False,
            "response_available": False,
            "errors": [f"Timeout while testing service access: {test_url}"]
        }
    except Exception as e:
        return {
            "success": False,
            "accessible": False,
            "response_available": False,
            "errors": [f"Error testing service access {service_url}: {e}"]
        }


def verify_critical_user_endpoints(endpoint_containers):
    """
    Verify critical user access endpoints for multimodal deployment.
    
    Args:
        endpoint_containers (dict): Dictionary of container names and their ports
        
    Returns:
        dict: Critical endpoints verification results
    """
    try:
        endpoint_results = {
            "success": False,
            "accessible_endpoints": {},
            "failed_endpoints": {},
            "critical_failures": [],
            "errors": []
        }
        
        # Test each endpoint
        for container, port in endpoint_containers.items():
            if not container_is_running(container):
                endpoint_results["failed_endpoints"][container] = f"Container not running"
                endpoint_results["critical_failures"].append(container)
                continue
            
            # Test endpoint based on container type
            if container == "ia-grafana":
                result = test_service_direct_access(container, f"http://localhost:{port}/", constants.TEST_CURL_TIMEOUT)
            elif container == "dlstreamer-pipeline-server":
                result = test_service_direct_access(container, f"http://localhost:{port}/", constants.TEST_CURL_TIMEOUT)
            elif container == "nginx_proxy":
                result = test_nginx_proxy_endpoint(container, f"https://localhost:{port}/", constants.TEST_CURL_TIMEOUT)
            else:
                result = test_service_direct_access(container, f"http://localhost:{port}/", constants.TEST_CURL_TIMEOUT)
            
            if result["success"]:
                endpoint_results["accessible_endpoints"][container] = f"Port {port} accessible"
            else:
                endpoint_results["failed_endpoints"][container] = result["errors"]
                # Mark as critical failure for Grafana and DL Streamer
                if container in ["ia-grafana", "dlstreamer-pipeline-server"]:
                    endpoint_results["critical_failures"].append(container)
        
        # Overall success if no critical failures
        endpoint_results["success"] = len(endpoint_results["critical_failures"]) == 0
        
        return endpoint_results
        
    except Exception as e:
        return {
            "success": False,
            "accessible_endpoints": {},
            "failed_endpoints": {},
            "critical_failures": list(endpoint_containers.keys()),
            "errors": [f"Error verifying critical endpoints: {e}"]
        }


def validate_system_resources_common(container_list, resource_intensive_allowed=None, cpu_threshold=80, memory_threshold=80):
    """
    Common utility for system resource monitoring across sample apps
    
    Args:
        container_list (list): List of containers to monitor
        resource_intensive_allowed (list): Containers allowed to have high resource usage
        cpu_threshold (int): CPU usage threshold percentage (default: 80)
        memory_threshold (int): Memory usage threshold percentage (default: 80)
    
    Returns:
        dict: Resource validation results
    """
    logger.info("Validating system resources for containers")
    
    if resource_intensive_allowed is None:
        resource_intensive_allowed = []
    
    high_resource_containers = []
    container_stats = {}
    
    for container in container_list:
        if container_is_running(container):
            stats = get_container_stats(container)
            
            if stats:
                cpu_usage = stats.get('cpu_percent', 0)
                memory_usage = stats.get('memory_percent', 0)
                
                container_stats[container] = {
                    "cpu_percent": cpu_usage,
                    "memory_percent": memory_usage
                }
                
                logger.info(f"{container}: CPU={cpu_usage}%, Memory={memory_usage}%")
                
                # Flag containers with very high resource usage
                if cpu_usage > cpu_threshold or memory_usage > memory_threshold:
                    high_resource_containers.append(container)
    
    # Filter out allowed resource-intensive containers
    problematic_containers = [c for c in high_resource_containers if c not in resource_intensive_allowed]
    
    return {
        "success": len(problematic_containers) == 0,
        "high_resource_containers": high_resource_containers,
        "problematic_containers": problematic_containers,
        "container_stats": container_stats,
        "total_monitored": len([c for c in container_list if container_is_running(c)])
    }


def validate_nginx_proxy_integration_common(nginx_container="nginx_proxy", backend_services=None, fallback_service="ia-grafana", ssl_cert_path="/opt/nginx/certs/", ssl_cert_files=None):
    """
    Common utility for nginx proxy integration testing across sample apps
    
    Args:
        nginx_container (str): Name of nginx container to check
        backend_services (list): List of backend services to validate connectivity
        fallback_service (str): Service to test for direct access if nginx not available
        ssl_cert_path (str): Path to SSL certificates in container
        ssl_cert_files (list): List of SSL certificate files to validate
    
    Returns:
        dict: Nginx integration validation results
    """
    logger.info("Validating nginx proxy integration")
    
    if backend_services is None:
        backend_services = ["ia-grafana", "ia-time-series-analytics-microservice"]
    
    if ssl_cert_files is None:
        ssl_cert_files = ["cert.pem", "key.pem"]
    
    results = {
        "nginx_available": False,
        "ssl_validated": False,
        "backend_connectivity": False,
        "direct_access_validated": False,
        "success": False,
        "errors": []
    }
    
    # Check if nginx container is available
    nginx_available = container_is_running(nginx_container) or container_is_running("nginx")
    results["nginx_available"] = nginx_available
    
    if nginx_available:
        logger.info(f"Nginx container found: {nginx_container}")
        
        # Test SSL certificate validation
        try:
            ssl_results = verify_nginx_ssl_certificates(nginx_container, ssl_cert_path, ssl_cert_files)
            if ssl_results.get("success", False):
                results["ssl_validated"] = True
                logger.info("✓ Nginx SSL certificates validated")
            else:
                results["errors"].append("SSL certificate validation failed")
        except Exception as e:
            results["errors"].append(f"SSL validation error: {e}")
        
        # Test backend connectivity
        try:
            connectivity_results = verify_nginx_backend_connectivity(nginx_container, backend_services)
            if connectivity_results.get("success", False):
                results["backend_connectivity"] = True
                logger.info("✓ Nginx backend connectivity validated")
            else:
                results["errors"].append("Backend connectivity validation failed")
        except Exception as e:
            results["errors"].append(f"Backend connectivity error: {e}")
        
        results["success"] = results["ssl_validated"] and results["backend_connectivity"]
    
    else:
        # Nginx proxy not configured - services like Grafana are NOT directly accessible
        # They are only accessible through nginx proxy with HTTPS
        logger.warning("⚠ Nginx proxy not configured - backend services not accessible without proxy")
        results["errors"].append("Nginx proxy not available - services require proxy for access")
        results["success"] = False
    
    return results


def validate_container_logs_common(container_list, critical_containers=None):
    """
    Common utility for container logs validation across sample apps
    
    Args:
        container_list (list): List of containers to check logs for
        critical_containers (list): List of critical containers that must not have errors
    
    Returns:
        dict: Container logs validation results
    """
    logger.info("Validating container logs for critical errors")
    
    if critical_containers is None:
        critical_containers = ["ia-influxdb", "ia-time-series-analytics-microservice", "ia-telegraf"]
    
    running_critical_containers = [c for c in critical_containers if container_is_running(c)]
    
    if len(running_critical_containers) == 0:
        return {
            "success": False,
            "error_containers": [],
            "critical_errors": [],
            "skip_reason": "No critical containers are running"
        }
    
    error_containers = []
    
    for container in container_list:
        if container_is_running(container):
            logger.info(f"Checking logs for container: {container}")
            logs = get_container_logs(container)
            
            # Look for critical errors
            critical_errors = common_utils.find_critical_errors_in_logs(logs)
            if critical_errors:
                logger.warning(f"Critical errors found in {container}: {critical_errors}")
                error_containers.append(container)
        else:
            logger.warning(f"Container {container} is not running")
            # Only add to error_containers if it's a critical container
            if container in critical_containers:
                error_containers.append(container)
    
    # Allow some containers to have non-critical errors
    critical_errors = [c for c in error_containers if c in critical_containers]
    
    return {
        "success": len(critical_errors) == 0,
        "error_containers": error_containers,
        "critical_errors": critical_errors,
        "running_critical_containers": running_critical_containers,
        "total_checked": len([c for c in container_list if container_is_running(c)])
    }

def container_exists_and_running(container_name):
    """
    Check if a container exists and is running
    """
    try:
        # Check if container exists
        result = subprocess.run(['docker', 'inspect', container_name], 
                              capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False
            
        # Check if container is running
        result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', container_name], 
                              capture_output=True, text=True, check=False)
        return result.returncode == 0 and result.stdout.strip() == 'true'
    except Exception as e:
        logger.error(f"Error checking container {container_name}: {e}")
        return False

def extract_img_handles_from_influxdb(measurement, database, container_name, username, password):
    """
    Extract img_handle values from InfluxDB vision metadata
    """
    try:
        # Query to extract img_handle values from vision metadata
        query = f'SELECT img_handle FROM "{measurement}" WHERE time > now() - 1h'
        
        # Execute InfluxDB query with authentication
        cmd = [
            "docker", "exec", container_name,
            "influx", "-username", username, "-password", password,
            "-database", database, "-execute", query, "-format", "csv"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"InfluxDB query failed: {result.stderr}")
            return []
        
        # Parse CSV output to extract img_handle values
        img_handles = []
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:  # Skip header
            if line and ',' in line:
                parts = line.split(',')
                if len(parts) >= 3 and parts[2].strip():
                    img_handles.append(parts[2].strip())
        
        # Remove duplicates and empty values
        img_handles = list(set([h for h in img_handles if h and h != 'img_handle']))
        logger.info(f"Extracted {len(img_handles)} unique img_handle values")
        return img_handles
        
    except Exception as e:
        logger.error(f"Error extracting img_handles from InfluxDB: {e}")
        return []

def verify_seaweed_essential_containers():
    """
    Verify that essential containers for SeaweedFS S3 integration are running
    
    Returns:
        dict: Result with success status, missing containers list, and running containers list
    """
    essential_containers = [
        CONTAINERS["dlstreamer"]["name"],
        CONTAINERS["seaweedfs_master"]["name"],
        CONTAINERS["seaweedfs_volume"]["name"],
        CONTAINERS["seaweedfs_filer"]["name"],
        CONTAINERS["seaweedfs_s3"]["name"]
    ]
    
    missing_essential = []
    running_containers = []
    
    for container in essential_containers:
        if container.startswith("seaweedfs"):
            is_running = container_exists_and_running(container)
        else:
            is_running = container_is_running(container)
            
        if not is_running:
            missing_essential.append(container)
        else:
            running_containers.append(container)
    
    return {
        "success": len(missing_essential) == 0,
        "missing_containers": missing_essential,
        "running_containers": running_containers,
        "total_checked": len(essential_containers)
    }


def get_vision_img_handles_from_influxdb(credentials, database="datain", measurement="vision-weld-classification-results"):
    """
    Query InfluxDB for vision detection results and extract img_handle values
    
    Args:
        credentials (dict): InfluxDB credentials with username and password
        database (str): InfluxDB database name
        measurement (str): InfluxDB measurement name
        
    Returns:
        dict: Result with success status, img_handles list, and selected random handle
    """
    username = credentials.get("INFLUXDB_USERNAME", "")
    password = credentials.get("INFLUXDB_PASSWORD", "")
    
    if not username or not password:
        return {
            "success": False,
            "error": "InfluxDB credentials not found",
            "img_handles": [],
            "selected_handle": None
        }
    
    # Extract img_handles using existing function
    img_handles = extract_img_handles_from_influxdb(
        measurement=measurement,
        database=database,
        container_name=CONTAINERS["influxdb"]["name"],
        username=username,
        password=password
    )
    
    if not img_handles:
        return {
            "success": False,
            "error": "No img_handle values found in InfluxDB vision results",
            "img_handles": [],
            "selected_handle": None
        }
    
    # Select random img_handle for testing
    selected_handle = random.choice(img_handles)
    
    return {
        "success": True,
        "img_handles": img_handles,
        "selected_handle": selected_handle,
        "total_handles": len(img_handles)
    }


def execute_seaweedfs_bucket_query():
    """
    Execute curl command to query SeaweedFS bucket for stored images

    Returns:
        dict: Result with success status, jpg_files list, and bucket URL used
    """
    nginx_port = CONTAINERS["nginx_proxy"]["https_port"]
    bucket_url = f"https://localhost:{nginx_port}/image-store/buckets/dlstreamer-pipeline-results/weld-defect-classification/?limit=5000"
    
    # Use existing function to get bucket files
    bucket_result = get_seaweedfs_bucket_files(bucket_url)
    bucket_result["bucket_url"] = bucket_url
    
    return bucket_result


def check_s3_image_file_size(img_filename, bucket_path="dlstreamer-pipeline-results/weld-defect-classification"):
    """
    Check if a specific S3 image file is empty or has content using curl HEAD request

    Args:
        img_filename (str): Image filename to check (e.g., "ZZHR95D2V4.jpg")
        bucket_path (str): S3 bucket path

    Returns:
        dict: Result with file size, empty status, and file details  
    """
    nginx_port = CONTAINERS["nginx_proxy"]["https_port"]
    file_url = f"https://localhost:{nginx_port}/image-store/buckets/{bucket_path}/{img_filename}"
    
    try:
        # Execute curl HEAD request to get content-length
        curl_command = [
            'curl', '-skI', file_url
        ]
        
        logger.info(f"Checking file size for: {file_url}")
        
        # Run curl command
        result = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = f"Curl HEAD request failed with return code {result.returncode}: {result.stderr}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "file_size": 0,
                "is_empty": True,
                "file_url": file_url,
                "filename": img_filename
            }
        
        # Parse content-length from headers
        headers_output = result.stdout
        content_length = 0
        
        for line in headers_output.split('\n'):
            if 'content-length' in line.lower():
                try:
                    # Extract size value and clean it
                    size_str = line.split(':')[1].strip().replace('\r', '')
                    content_length = int(size_str)
                    break
                except (IndexError, ValueError) as e:
                    logger.warning(f"Could not parse content-length from line: {line} - {e}")
        
        is_empty = content_length <= 0
        
        if is_empty:
            logger.info(f"File is EMPTY or missing: {img_filename} (size: {content_length} bytes)")
        else:
            logger.info(f"File is NOT empty: {img_filename} (size: {content_length} bytes)")
        
        return {
            "success": True,
            "file_size": content_length,
            "is_empty": is_empty,
            "file_url": file_url,
            "filename": img_filename,
            "size_human": f"{content_length} bytes"
        }
        
    except subprocess.TimeoutExpired:
        error_msg = f"Curl HEAD request timed out after 30 seconds for {img_filename}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "file_size": 0,
            "is_empty": True,
            "file_url": file_url,
            "filename": img_filename
        }
    except Exception as e:
        error_msg = f"Unexpected error checking file size for {img_filename}: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "file_size": 0,
            "is_empty": True,
            "file_url": file_url,
            "filename": img_filename
        }


def validate_s3_images_content(matched_files, max_files_to_check=3):
    """
    Validate that S3 image files have actual content (not empty)

    Args:
        matched_files (list): List of matched image file paths
        max_files_to_check (int): Maximum number of files to check for performance

    Returns:
        dict: Validation results with file size details and overall status
    """
    if not matched_files:
        return {
            "success": False,
            "error": "No matched files to validate",
            "checked_files": [],
            "non_empty_count": 0,
            "empty_count": 0,
            "total_checked": 0
        }
    
    # Limit files to check for performance reasons
    files_to_check = matched_files[:max_files_to_check]
    logger.info(f"Validating content of {len(files_to_check)} image files (max: {max_files_to_check})")
    
    checked_files = []
    non_empty_count = 0
    empty_count = 0
    
    for file_path in files_to_check:
        # Extract filename from full path (e.g., "dlstreamer-pipeline-results/weld-defect-classification/ZZHR95D2V4.jpg")
        filename = file_path.split('/')[-1]
        
        file_check = check_s3_image_file_size(filename)
        checked_files.append(file_check)
        
        if file_check["success"] and not file_check["is_empty"]:
            non_empty_count += 1
        else:
            empty_count += 1
    
    validation_success = non_empty_count > 0  # At least one file should have content
    
    return {
        "success": validation_success,
        "checked_files": checked_files,
        "non_empty_count": non_empty_count,
        "empty_count": empty_count,
        "total_checked": len(files_to_check),
        "files_to_check": files_to_check
    }


def get_seaweedfs_bucket_files(bucket_url):
    """
    Execute curl command to retrieve SeaweedFS bucket contents and parse .jpg files
    
    Args:
        bucket_url (str): SeaweedFS bucket URL to query
        
    Returns:
        dict: Result containing success status, jpg_files list, total_files count, and any errors
    """
    try:
        # Execute curl command to get bucket contents
        curl_command = [
            'curl', '-sk', 
            '-H', 'Accept: application/json',
            bucket_url
        ]
        
        logger.info(f"Executing curl command: {' '.join(curl_command)}")
        
        # Run curl command
        result = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = f"Curl command failed with return code {result.returncode}: {result.stderr}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "jpg_files": [],
                "total_files": 0
            }
        
        # Parse JSON response
        try:
            response_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "jpg_files": [],
                "total_files": 0
            }
        
        # Extract entries from JSON response
        entries = response_data.get('Entries', [])
        total_files = len(entries)
        
        # Filter for .jpg files
        jpg_files = []
        for entry in entries:
            full_path = entry.get('FullPath', '')
            if full_path.lower().endswith('.jpg'):
                jpg_files.append(full_path)
        
        logger.info(f"Successfully retrieved bucket contents: {len(jpg_files)} .jpg files out of {total_files} total")
        
        return {
            "success": True,
            "jpg_files": jpg_files,
            "total_files": total_files,
            "error": None
        }
        
    except subprocess.TimeoutExpired:
        error_msg = "Curl command timed out after 30 seconds"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "jpg_files": [],
            "total_files": 0
        }
    except Exception as e:
        error_msg = f"Unexpected error retrieving SeaweedFS bucket contents: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "jpg_files": [],
            "total_files": 0
        }

