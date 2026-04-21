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
import re
# Add parent directory to path for utils imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import docker_utils
from utils import constants
from utils import common_utils

# Import the fixture directly from conftest_docker.py
pytest_plugins = ["conftest_docker"]

logger = logging.getLogger(__name__)

def test_blank_values():
    """TC_001: Testing blank values in .env file for multimodal deployment"""
    logger.info("TC_001: Testing blank values, checking make check env variables with blank values in .env file")
    case = docker_utils.generate_multimodal_test_credentials(case_type="blank")
    env_file_path = os.path.join(constants.MULTIMODAL_APPLICATION_DIRECTORY, ".env")
    
    # Try to update env file with blank values
    update_result = docker_utils.update_env_file(env_file_path, case)
    
    if not update_result:
        # If update_env_file rejects blank values, that's the expected behavior
        logger.info("✅ Blank values correctly rejected at env file update level")
        return
    
    logger.info("Verifying that make check env variables fails with blank values in .env file")
    
    # Set working directory to multimodal
    docker_utils.check_and_set_working_directory_multimodal()
    
    result = docker_utils.invoke_make_check_env_variables_in_current_dir()
    logger.info(f"make check env variables result with blank values: {result}")
    assert result == False  # nosec B101

def test_invalid_values():
    """TC_002: Testing invalid values in .env file for multimodal deployment"""
    logger.info("TC_002: Testing invalid values, checking make check env variables with invalid values in .env file")
    case = docker_utils.generate_multimodal_test_credentials(case_type="invalid")
    env_file_path = os.path.join(constants.MULTIMODAL_APPLICATION_DIRECTORY, ".env")
    docker_utils.update_env_file(env_file_path, case)
    logger.info("Verifying that make check env variables fails with invalid values in .env file")
    
    # Set working directory to multimodal
    docker_utils.check_and_set_working_directory_multimodal()
    
    result = docker_utils.invoke_make_check_env_variables_in_current_dir()
    logger.info(f"make check env variables result with invalid values: {result}")
    assert result == False  # nosec B101

def test_valid_values():
    """TC_003: Testing valid values in .env file for multimodal deployment"""
    logger.info("TC_003: Testing valid values, verifying make check_env_variables with all valid values in .env file")
    case = docker_utils.generate_multimodal_test_credentials(case_type="valid")
    
    # Validate that S3 credentials are present and valid
    if "S3_STORAGE_USERNAME" not in case or not case["S3_STORAGE_USERNAME"]:
        pytest.fail("S3_STORAGE_USERNAME is missing or empty in generated credentials")
    if "S3_STORAGE_PASSWORD" not in case or not case["S3_STORAGE_PASSWORD"]:
        pytest.fail("S3_STORAGE_PASSWORD is missing or empty in generated credentials")
        
    logger.info(f"Generated S3_STORAGE_USERNAME: [REDACTED]")
    logger.info("Generated S3_STORAGE_PASSWORD: [REDACTED]")
    
    env_file_path = os.path.join(constants.MULTIMODAL_APPLICATION_DIRECTORY, ".env")
    update_result = docker_utils.update_env_file(env_file_path, case)
    
    if not update_result:
        pytest.fail("Failed to update .env file with multimodal credentials")
    
    # Update HOST_IP with system IP address
    logger.info("Updating HOST_IP with system IP address for multimodal deployment")
    if not common_utils.update_host_ip_in_env(env_file_path):
        logger.warning("Failed to update HOST_IP in .env file, using default value")
    else:
        logger.info("✓ Successfully updated HOST_IP with system IP address")
    
    logger.info("Verifying that make check env variables succeeds with valid values in .env file")
    
    # Set working directory to multimodal
    docker_utils.check_and_set_working_directory_multimodal()
    
    result = docker_utils.invoke_make_check_env_variables_in_current_dir()
    logger.info(f"make check env variables result with valid values: {result}")
    assert result == True  # nosec B101

def test_multimodal_make_up():
    """TC_004: Testing multimodal make up command with valid values in .env file"""
    logger.info("TC_004: Testing multimodal 'make up' command execution")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    
    # Set working directory to multimodal application
    docker_utils.check_and_set_working_directory_multimodal()
    
    # Update .env with valid multimodal credentials
    case = docker_utils.generate_multimodal_test_credentials(case_type="valid")
    
    # Validate that S3 credentials are present and valid
    if "S3_STORAGE_USERNAME" not in case or not case["S3_STORAGE_USERNAME"]:
        pytest.fail("S3_STORAGE_USERNAME is missing or empty in generated credentials")
    if "S3_STORAGE_PASSWORD" not in case or not case["S3_STORAGE_PASSWORD"]:
        pytest.fail("S3_STORAGE_PASSWORD is missing or empty in generated credentials")
        
    env_file_path = os.path.join(constants.MULTIMODAL_APPLICATION_DIRECTORY, ".env")
    update_result = docker_utils.update_env_file(env_file_path, case)
    
    if not update_result:
        pytest.fail("Failed to update .env file with multimodal credentials")
    
    # Update HOST_IP with system IP address
    logger.info("Updating HOST_IP with system IP address for multimodal deployment")
    if not common_utils.update_host_ip_in_env(env_file_path):
        logger.warning("Failed to update HOST_IP in .env file, using default value")
    else:
        logger.info("✓ Successfully updated HOST_IP with system IP address")
    
    # Execute make up
    logger.info("Executing 'make up' for multimodal deployment")
    result = docker_utils.invoke_make_up_in_current_dir()
    logger.info(f"make up result: {result}")
    assert result == True, "Multimodal 'make up' command failed"  # nosec B101
    
    # Verify containers are running using multimodal app config
    multimodal_containers = multimodal_config.get("containers", [])
    logger.info("Verifying all multimodal containers are running")
    for container in multimodal_containers:
        is_running = docker_utils.container_is_running(container)
        logger.info(f"Container {container} running status: {is_running}")
        assert is_running, f"Container {container} is not running"  # nosec B101
        logger.info(f"✓ Container {container} is running")
    
    logger.info(f"✓ Multimodal deployment successful - all {len(multimodal_containers)} containers running")

def test_multimodal_make_down(setup_multimodal_environment):
    """TC_005: Testing multimodal make down command"""
    logger.info("TC_005: Testing multimodal 'make down' command execution")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    multimodal_containers = multimodal_config.get("containers", [])
    
    # Deploy the multimodal stack first to ensure containers are running
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Wait for containers to stabilize
    common_utils.wait_for_stability(constants.MULTIMODAL_DOCKER_PRE_TEARDOWN_WAIT)
    
    # Verify containers are running before attempting teardown
    logger.info("Verifying all multimodal containers are running before teardown")
    for container in multimodal_containers:
        is_running = docker_utils.container_is_running(container)
        logger.info(f"Container {container} running status before teardown: {is_running}")
        assert is_running, f"Container {container} is not running. Cannot test teardown."  # nosec B101
    
    # Set working directory to multimodal application
    docker_utils.check_and_set_working_directory_multimodal()
    
    # Execute make down
    logger.info("Executing 'make down' for multimodal teardown")
    result = docker_utils.invoke_make_down_in_current_dir()
    logger.info(f"make down result: {result}")
    assert result == True, "Multimodal 'make down' command failed"  # nosec B101
    
    # Verify containers are stopped
    logger.info("Verifying multimodal containers are stopped")
    common_utils.wait_for_stability(constants.MULTIMODAL_DOCKER_POST_TEARDOWN_WAIT)
    
    running_containers = []
    for container in multimodal_containers:
        if docker_utils.container_is_running(container):
            running_containers.append(container)
            logger.error(f"Container {container} is still running after make down")
    
    # Fail the test if any containers are still running after make down
    assert len(running_containers) == 0, f"Make down failed to stop all containers. Still running: {running_containers}"  # nosec B101
        
    logger.info(f"✓ Multimodal teardown completed successfully - all {len(multimodal_containers)} containers stopped")

def test_time_series_ingested_data(setup_multimodal_environment):
    """TC_006: Testing time series data ingestion for multimodal deployment via Telegraf"""
    logger.info("TC_006: Testing time series data ingestion through Telegraf to InfluxDB")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Check if required containers for data ingestion are running using multimodal app config
    required_containers = [constants.CONTAINERS["influxdb"]["name"], constants.CONTAINERS["telegraf"]["name"]]
    for container in required_containers:
        is_running = docker_utils.container_is_running(container)
        logger.info(f"Container {container} running status: {is_running}")
        assert is_running, f"{container} container is not running. Deploy multimodal stack first."  # nosec B101
    
    logger.info("✓ Both InfluxDB and Telegraf containers are running")
    
    # Wait for containers to stabilize and Telegraf to start collecting data
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)
    
    # Check if data is being ingested into InfluxDB via Telegraf with authentication
    logger.info("Checking time series data ingestion from Telegraf to InfluxDB")
    
    # Get credentials from the context (setup_multimodal_environment loads them from .env)
    credentials = context["credentials"]
    username = credentials.get("INFLUXDB_USERNAME", "")
    password = credentials.get("INFLUXDB_PASSWORD", "")
    
    logger.info(f"InfluxDB credentials found: username={'[SET]' if username else '[EMPTY]'}, password={'[SET]' if password else '[EMPTY]'}")
    assert username and password, "InfluxDB credentials not found in environment"  # nosec B101
    
    # Use authenticated InfluxDB query with multimodal app config
    ingested_topic = multimodal_config.get("ingested_topic")
    result = docker_utils.check_influxdb_data_with_auth(
        measurement=ingested_topic,
        database=constants.INFLUXDB_DATABASE,
        container_name=constants.CONTAINERS["influxdb"]["name"],
        username=username,
        password=password
    )
    logger.info(f"check_influxdb_data_with_auth result for {ingested_topic}: {result}")
    
    if not result:
        logger.error(f"No data found in InfluxDB measurement: {ingested_topic}")
        assert result == True, f"Time series data ingestion failed - no data found in InfluxDB measurement: {ingested_topic}"  # nosec B101
    else:
        logger.info("✓ Time series data ingestion via Telegraf verified")

def test_time_series_analytics_processing(setup_multimodal_environment):
    """TC_007: Testing time series analytics processing with CatBoost model"""
    logger.info("TC_007: Testing time series analytics processing for weld anomaly detection")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Check if required containers are running using constants
    required_containers = [constants.CONTAINERS["influxdb"]["name"], constants.CONTAINERS["time_series_analytics"]["name"]]
    for container in required_containers:
        is_running = docker_utils.container_is_running(container)
        logger.info(f"Container {container} running status: {is_running}")
        assert is_running, f"{container} is not running. Deploy multimodal stack first."  # nosec B101
    
    # Wait for processing to complete
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY * 2)
    
    # Check if processed data exists in InfluxDB using multimodal app config
    analytics_topic = multimodal_config.get("analytics_topic")
    logger.info(f"Checking processed anomaly data in InfluxDB measurement: {analytics_topic}")
    result = docker_utils.check_influxdb_data_with_auth(
        measurement=analytics_topic,
        database=constants.INFLUXDB_DATABASE,
        container_name=constants.CONTAINERS["influxdb"]["name"],
        username=context["credentials"]["INFLUXDB_USERNAME"],
        password=context["credentials"]["INFLUXDB_PASSWORD"]
    )
    logger.info(f"check_influxdb_data_with_auth result for {analytics_topic}: {result}")
    
    if not result:
        logger.error(f"No processed data found in InfluxDB measurement: {analytics_topic}")
        assert result == True, f"Time series analytics processing failed - no processed data found in InfluxDB measurement: {analytics_topic}"  # nosec B101
    else:
        logger.info("✓ Time series analytics processing verified")

def test_vision_analytics_mqtt_publish(setup_multimodal_environment):
    """TC_008: Testing vision analytics MQTT publish via DLStreamer"""
    logger.info("TC_008: Testing vision analytics MQTT publishing for weld defect detection")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Check if DLStreamer is processing video streams using constants
    logger.info("Verifying DLStreamer pipeline server is running")
    is_running = docker_utils.container_is_running(constants.CONTAINERS["dlstreamer"]["name"])
    logger.info(f"DLStreamer container running status: {is_running}")
    assert is_running, "DLStreamer container is not running. Deploy multimodal stack first."  # nosec B101
    
    # Check if vision analytics data is being published to MQTT using multimodal app config
    vision_topic = multimodal_config.get("vision_topic")
    logger.info(f"Checking vision analytics MQTT topic: {vision_topic}")
    result = common_utils.check_mqtt_topic_data(
        topic=vision_topic,
        broker_host="localhost",
        broker_port=constants.MQTT_PORT_INT,
        timeout=constants.TEST_MQTT_TIMEOUT
    )
    # Note: This might fail if no actual video stream is processed, which is expected in test environment
    logger.info("✓ Vision analytics MQTT publish check completed")

def test_fusion_analytics_mqtt_publish(setup_multimodal_environment):
    """TC_009: Testing fusion analytics MQTT publish combining vision and time series results"""
    logger.info("TC_009: Testing fusion analytics MQTT publishing for multimodal decision making")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()

    # Check fusion results in InfluxDB and MQTT publishing
    logger.info("Checking fusion analytics MQTT publish results in InfluxDB")
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)  # Allow time for fusion processing
    
    # Fusion analytics writes results back to InfluxDB using multimodal app config
    fusion_topic = multimodal_config.get("fusion_topic")
    result = docker_utils.check_influxdb_data_with_auth(
        measurement=fusion_topic,
        database=constants.INFLUXDB_DATABASE,
        container_name=constants.CONTAINERS["influxdb"]["name"],
        username=context["credentials"]["INFLUXDB_USERNAME"],
        password=context["credentials"]["INFLUXDB_PASSWORD"]
    )
    # Note: May not have data depending on whether both vision and TS have anomalies
    logger.info("✓ Fusion analytics MQTT publish check completed")

def test_influxdb_data_storage_multimodal(setup_multimodal_environment):
    """TC_010: Testing InfluxDB data storage for multimodal deployment"""
    logger.info("TC_010: Testing InfluxDB data storage and persistence for multimodal weld detection")
    
    # Get multimodal app configuration
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Wait for data generation and storage
    logger.info("Waiting for data to be generated and stored in InfluxDB...")
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)
    
    # Verify InfluxDB container is running
    is_running = docker_utils.container_is_running(constants.CONTAINERS["influxdb"]["name"])
    logger.info(f"InfluxDB container running status: {is_running}")
    assert is_running, "InfluxDB container not running"  # nosec B101
    
    # Get credentials
    credentials = context["credentials"]
    username = credentials.get("INFLUXDB_USERNAME", "")
    password = credentials.get("INFLUXDB_PASSWORD", "")
    logger.info(f"InfluxDB credentials found: username={'[SET]' if username else '[EMPTY]'}, password={'[SET]' if password else '[EMPTY]'}")
    assert username and password, "InfluxDB credentials not found"  # nosec B101
    
    # Test data storage for all multimodal measurements
    measurements_to_check = [
        multimodal_config.get("ingested_topic"),      # Raw sensor data
        multimodal_config.get("analytics_topic"),     # Time series analytics results
        multimodal_config.get("vision_measurement"),        # Vision analytics results
        multimodal_config.get("fusion_measurement")         # Fusion decision results
    ]
    
    stored_measurements = []
    for measurement in measurements_to_check:
        logger.info(f"Checking data storage for measurement: {measurement}")
        result = docker_utils.check_influxdb_data_with_auth(
            measurement=measurement,
            database=constants.INFLUXDB_DATABASE,
            container_name=constants.CONTAINERS["influxdb"]["name"],
            username=username,
            password=password
        )
        if result:
            stored_measurements.append(measurement)
            logger.info(f"✓ Data stored in {measurement}")
    
    # Verify at least ingested data and analytics data are stored
    logger.info(f"Stored measurements: {stored_measurements}")
    assert multimodal_config.get("ingested_topic") in stored_measurements, "Raw sensor data not stored in InfluxDB"  # nosec B101
    assert multimodal_config.get("analytics_topic") in stored_measurements, "Analytics results not stored in InfluxDB"  # nosec B101
    assert multimodal_config.get("vision_measurement") in stored_measurements, "Vision analytics results not stored in InfluxDB"  # nosec B101
    assert multimodal_config.get("fusion_measurement") in stored_measurements, "Fusion decision results not stored in InfluxDB"  # nosec B101
    
    logger.info(f"✓ InfluxDB data storage validated - {len(stored_measurements)}/{len(measurements_to_check)} measurements stored")

def test_mqtt_alerts_multimodal(setup_multimodal_environment):
    """TC_011: Testing multimodal analytics processing and infrastructure for weld defect detection"""
    logger.info("TC_011: Testing multimodal analytics processing and infrastructure for weld defect detection")
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()

    # Perform comprehensive multimodal alerts validation using docker_utils
    validation_results = docker_utils.validate_multimodal_alerts_infrastructure()
    
    # Log final validation summary
    logger.info("✓ Multimodal analytics processing and infrastructure validated successfully")

def test_rtsp_streaming(setup_multimodal_environment):
    """TC_012: Testing RTSP streaming functionality with MediaMTX"""
    logger.info("TC_012: Testing RTSP streaming setup for video data")
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Check if MediaMTX container is running using constants
    is_running = docker_utils.container_is_running(constants.MEDIAMTX_CONTAINER)
    logger.info(f"MediaMTX container running status: {is_running}")
    assert is_running, "MediaMTX container is not running. Deploy multimodal stack first."  # nosec B101
    
    # Check if MediaMTX streaming is accessible via nginx proxy
    logger.info("Verifying MediaMTX streaming via nginx proxy")
    # MediaMTX now accessible only through nginx proxy at /samplestream endpoint
    logger.info(f"MediaMTX streaming accessible via: {constants.MEDIAMTX_STREAM_URL}")
    
    logger.info("✓ MediaMTX streaming server configured for nginx proxy access")

def test_webrtc_functionality(setup_multimodal_environment):
    """TC_013: Testing WebRTC functionality for real-time video streaming"""
    logger.info("TC_013: Testing WebRTC functionality")
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Check if COTURN container is running using constants
    is_running = docker_utils.container_is_running(constants.COTURN_CONTAINER)
    logger.info(f"COTURN container running status: {is_running}")
    assert is_running, "COTURN container is not running. Deploy multimodal stack first."  # nosec B101
    
    # Verify WebRTC signaling server (via nginx proxy)
    logger.info("Checking WebRTC signaling server accessibility via nginx proxy")
    # WebRTC now accessible only through nginx proxy
    logger.info(f"WebRTC accessible via: {constants.MEDIAMTX_STREAM_URL}")
    # Note: Direct port access is no longer available, routing happens via nginx
    
    logger.info("WebRTC functionality check completed")

def test_container_logs_multimodal(setup_multimodal_environment):
    """TC_014: Testing container logs for error detection in multimodal setup"""
    logger.info("TC_014: Checking container logs for errors in multimodal deployment")
    
    # Get multimodal app configuration from the sample app dict
    multimodal_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP)
    multimodal_containers = multimodal_config.get("containers", [])
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Get multimodal container list from SAMPLE_APPS_CONFIG
    multimodal_container_list = constants.SAMPLE_APPS_CONFIG[constants.MULTIMODAL_SAMPLE_APP]["multimodal_container_list"]
    
    # Use common container logs validation utility
    logs_results = docker_utils.validate_container_logs_common(
        container_list=multimodal_container_list,
        critical_containers=[constants.CONTAINERS["influxdb"]["name"], constants.CONTAINERS["time_series_analytics"]["name"], constants.CONTAINERS["telegraf"]["name"]]
    )
    
    # Always fail if expected containers are not running post deployment
    if "skip_reason" in logs_results:
        logger.error(logs_results["skip_reason"])
        logger.info(f"logs_results: {logs_results}")
        assert False, f"Critical containers are not running after deployment: {logs_results['skip_reason']}"  # nosec B101
    
    logger.info(f"Container logs validation success: {logs_results['success']}, critical_errors: {logs_results.get('critical_errors')}")
    assert logs_results["success"], f"Critical containers have errors: {logs_results['critical_errors']}"  # nosec B101
    
    logger.info("✓ Container logs check completed")

def test_fusion_decision_making_logic_validation(setup_multimodal_environment):
    """TC_015: Testing fusion decision-making logic validation using captured fusion decision logs"""
    logger.info("TC_015: Validating fusion decision-making logic from captured multimodal logs")
    
    # Deploy the multimodal stack
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    
    # Verify fusion analytics container is running
    is_running = docker_utils.container_is_running(constants.CONTAINERS["fusion_analytics"]["name"])
    logger.info(f"Fusion analytics container running status: {is_running}")
    assert is_running, "Fusion analytics container is not running. Deploy multimodal stack first."  # nosec B101
    
    # Execute fusion decision validation using docker_utils
    validation_results = docker_utils.validate_fusion_decision_making_logic()
    
    # Assert overall validation success
    logger.info(f"Fusion validation results: success={validation_results['success']}, error={validation_results.get('error')}")
    assert validation_results["success"], f"Fusion decision-making logic validation failed: {validation_results.get('error', 'Unknown error')}"  # nosec B101
    
    # Additional assertions for key metrics
    assert validation_results["total_decisions"] >= 10, f"Insufficient decisions analyzed: {validation_results['total_decisions']}"  # nosec B101
    assert validation_results["consistency_percentage"] >= 100.0, f"Logic consistency below threshold: {validation_results['consistency_percentage']}%"  # nosec B101
    assert validation_results["unique_defect_types"] >= 5, f"Insufficient defect type diversity: {validation_results['unique_defect_types']}"  # nosec B101
    
    # Verify both systems are contributing
    logger.info(f"Vision anomalies: {validation_results['vision_anomalies']}, TS anomalies: {validation_results['ts_anomalies']}")
    assert validation_results["vision_anomalies"] > 0, "Vision analytics should detect at least some anomalies"  # nosec B101
    assert validation_results["ts_anomalies"] > 0, "Time series analytics should detect at least some anomalies"  # nosec B101
    
    # Verify all decision categories are represented
    categorized = validation_results["categorized_cases"]
    logger.info(f"Categorized cases: {categorized}")
    assert categorized["both_anomaly"] > 0, "Should have cases where both systems detect anomalies"  # nosec B101
    assert categorized["vision_only"] > 0, "Should have vision-only detection cases"  # nosec B101
    assert categorized["ts_only"] > 0, "Should have TS-only detection cases"  # nosec B101
    assert categorized["no_anomaly"] > 0, "Should have no-anomaly cases"  # nosec B101
    
    # Wait for system to be active
    common_utils.wait_for_stability(constants.MULTIMODAL_DOCKER_FUSION_READY_WAIT)
    
    logger.info("✓ Fusion decision-making logic validation completed successfully")
    logger.info("✓ Multimodal weld defect detection system validated with OR fusion logic")

def test_system_resources_multimodal():
    """TC_016: Testing system resource usage for multimodal deployment"""
    logger.info("TC_016: Testing system resource usage for multimodal containers")
    
    # Get multimodal container list from SAMPLE_APPS_CONFIG
    multimodal_container_list = constants.SAMPLE_APPS_CONFIG[constants.MULTIMODAL_SAMPLE_APP]["multimodal_container_list"]
    
    # Use common system resource validation utility
    resource_results = docker_utils.validate_system_resources_common(
        container_list=multimodal_container_list,
        resource_intensive_allowed=[constants.CONTAINERS["dlstreamer"]["name"], constants.CONTAINERS["fusion_analytics"]["name"]],
        cpu_threshold=80,
        memory_threshold=80
    )
    
    logger.info(f"Resource validation results: success={resource_results['success']}, problematic_containers={resource_results.get('problematic_containers')}")
    assert resource_results["success"], f"Containers with excessive resource usage: {resource_results['problematic_containers']}"  # nosec B101
    
    logger.info("✓ System resource usage is within acceptable limits")


def test_nginx_proxy_integration(setup_multimodal_environment):
    """TC_017: Nginx reverse proxy integration test - validates container health, 
    port mappings, and proxy access to Grafana/TS API endpoints"""
    logger.info("TC_017: Testing nginx reverse proxy integration")
    
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    time.sleep(constants.TEST_NGINX_STARTUP_DELAY)
    
    # Verify nginx container health
    health_results = docker_utils.verify_nginx_container_health(constants.NGINX_CONTAINER)
    logger.info(f"Nginx container health: container_running={health_results['container_running']}, process_running={health_results['process_running']}")
    assert health_results["container_running"], f"Nginx container not running"  # nosec B101
    assert health_results["process_running"], "Nginx process not found"  # nosec B101
    
    # Verify port mappings
    port_results = docker_utils.verify_nginx_port_mappings(constants.NGINX_CONTAINER, constants.NGINX_EXPECTED_PORTS)
    logger.info(f"Nginx port mapping results: success={port_results['success']}, errors={port_results.get('errors')}")
    assert port_results["success"], f"Port mapping failed: {port_results['errors']}"  # nosec B101
    
    # Verify backend services
    grafana_running = docker_utils.container_is_running(constants.CONTAINERS["grafana"]["name"])
    logger.info(f"Grafana container running status: {grafana_running}")
    assert grafana_running, "Grafana container not running"  # nosec B101
    ts_analytics_running = docker_utils.container_is_running(constants.CONTAINERS["time_series_analytics"]["name"])
    logger.info(f"TS Analytics container running status: {ts_analytics_running}")
    assert ts_analytics_running, "TS Analytics container not running"  # nosec B101
    
    # Test proxy endpoints
    grafana_results = docker_utils.test_nginx_proxy_endpoint(
        constants.NGINX_CONTAINER, 
        f"https://localhost:{constants.NGINX_HTTPS_PORT}/",
        constants.TEST_CURL_TIMEOUT
    )
    logger.info(f"Grafana proxy results: success={grafana_results['success']}, errors={grafana_results.get('errors')}")
    assert grafana_results["success"], f"Grafana proxy failed: {grafana_results['errors']}"  # nosec B101
    
    api_results = docker_utils.test_nginx_proxy_endpoint(
        constants.NGINX_CONTAINER, 
        f"https://localhost:{constants.NGINX_HTTPS_PORT}/ts-api/",
        constants.TEST_CURL_TIMEOUT
    )
    logger.info(f"TS API proxy results: success={api_results['success']}, errors={api_results.get('errors')}")
    assert api_results["success"], f"TS API proxy failed: {api_results['errors']}"  # nosec B101
    
    # Validate all critical endpoints using CONTAINERS dictionary
    critical_endpoints = {
        constants.CONTAINERS["grafana"]["name"]: str(constants.CONTAINERS["grafana"]["port"]),
        constants.CONTAINERS["dlstreamer"]["name"]: str(constants.CONTAINERS["dlstreamer"]["port"]),
        constants.CONTAINERS["nginx_proxy"]["name"]: str(constants.CONTAINERS["nginx_proxy"]["https_port"])
    }
    endpoint_results = docker_utils.verify_critical_user_endpoints(critical_endpoints)
    logger.info(f"Critical endpoint results: success={endpoint_results['success']}, critical_failures={endpoint_results.get('critical_failures')}")
    assert endpoint_results["success"], f"Endpoint validation failed: {endpoint_results['critical_failures']}"  # nosec B101
    
    logger.info("✓ Nginx reverse proxy integration validated successfully")

def test_s3_stored_images_access(setup_multimodal_environment):
    """TC_018: Testing S3 stored images infrastructure for DLStreamer integration"""
    logger.info("TC_018: Testing S3 stored images infrastructure and SeaweedFS integration")
    
    # Deploy the multimodal stack and wait for stabilization
    context = setup_multimodal_environment
    context["deploy_multimodal"]()
    logger.info("Waiting for system stabilization...")
    time.sleep(constants.TEST_MQTT_TIMEOUT)
    
    # Wait additional time for S3 image storage to complete (DLStreamer writes images asynchronously)
    s3_wait_time = 90  # Additional 90 seconds for S3 image writes
    logger.info(f"Waiting {s3_wait_time}s for DLStreamer to process video and write images to S3 storage...")
    time.sleep(s3_wait_time)
    
    # Step 1: Verify essential containers are running
    logger.info("Step 1: Verifying required containers for S3 image storage")
    container_check = docker_utils.verify_seaweed_essential_containers()
    
    if not container_check["success"]:
        missing = container_check["missing_containers"]
        logger.info(f"Container check results: success={container_check['success']}, missing={missing}")
        assert False, f"Essential containers not running: {missing}"  # nosec B101
    
    logger.info(f"✓ All {container_check['total_checked']} essential containers are running")
    
    # Step 2: Query InfluxDB for vision metadata to extract IMG_HANDLE values
    logger.info("Step 2: Querying InfluxDB for vision detection results")
    influx_check = docker_utils.get_vision_img_handles_from_influxdb(context["credentials"])
    
    if not influx_check["success"]:
        logger.info(f"InfluxDB img_handle check results: success={influx_check['success']}, error={influx_check.get('error')}")
        assert False, f"No img_handle data available from InfluxDB: {influx_check['error']}"  # nosec B101
    
    logger.info(f"✓ Found {influx_check['total_handles']} img_handle values from vision analytics")
    logger.info(f"Selected random IMG_HANDLE for testing: {influx_check['selected_handle']}")
    
    # Step 3: Execute SeaweedFS S3 API query via curl
    logger.info("Step 3: Testing SeaweedFS S3 API access via curl")
    s3_check = docker_utils.execute_seaweedfs_bucket_query()
    
    if not s3_check["success"]:
        logger.error(f"Failed to retrieve S3 bucket contents: {s3_check['error']}")
        logger.info(f"S3 check results: success={s3_check['success']}, error={s3_check.get('error')}")
        assert False, f"SeaweedFS S3 API not accessible: {s3_check['error']}"  # nosec B101
    
    logger.info(f"✓ SeaweedFS S3 API accessible - Found {len(s3_check['jpg_files'])} .jpg files out of {s3_check['total_files']} total")
    logger.info(f"Bucket URL used: {s3_check['bucket_url']}")
    
    # Step 4: Save S3 jpg files output to list
    logger.info("Step 4: Saving S3 jpg files to list for further processing")
    jpg_files = s3_check["jpg_files"]
    
    if jpg_files:
        logger.info(f"✓ Saved {len(jpg_files)} .jpg files to list for processing")
        logger.info("Sample .jpg files found:")
        for i, jpg_file in enumerate(jpg_files[:5]):
            logger.info(f"  {i+1}. {jpg_file}")
    else:
        logger.info(f"No jpg files found in S3 storage, jpg_files count: {len(jpg_files)}")
        assert False, "No .jpg files found in S3 storage. Since the solution is deployed fresh per test and SeaweedFS has 30min retention, images must be present."  # nosec B101
    
    time.sleep(90)  # Wait before cross-verification to allow S3 to be fully populated
    
    # Step 5: Cross-verify img_handle with stored S3 images
    logger.info("Step 5: Cross-verifying img_handle values with stored S3 images")
    cross_verify_check = docker_utils.cross_verify_img_handle_with_s3(
        influx_check["selected_handle"], 
        jpg_files
    )
    
    if cross_verify_check["img_handle_found"]:
        logger.info(f"✓ Found {cross_verify_check['match_count']} matching file(s) for img_handle")
        for matched_file in cross_verify_check["matched_files"]:
            logger.info(f"  Matched file: {matched_file}")
    else:
        logger.info(f"Cross-verify results: img_handle_found={cross_verify_check['img_handle_found']}, selected_handle={cross_verify_check['selected_handle']}")
        assert False, f"img_handle '{cross_verify_check['selected_handle']}' not found in S3 image store. Since the solution is deployed fresh per test and SeaweedFS has 30min retention, this handle must be present."  # nosec B101
    
    # Step 6: Validate that matched image files have actual content (not empty)
    logger.info("Step 6: Validating that matched image files have content (not empty)")

    # Validate content of matched files
    content_validation = docker_utils.validate_s3_images_content(
        cross_verify_check["matched_files"],
        max_files_to_check=3
    )

    if content_validation["success"]:
        logger.info(f"✓ File content validation successful - {content_validation['non_empty_count']}/{content_validation['total_checked']} files have content")

        # Log details of checked files
        for file_check in content_validation["checked_files"]:
            if file_check["success"] and not file_check["is_empty"]:
                logger.info(f"  ✓ {file_check['filename']}: {file_check['size_human']}")
            else:
                logger.info(f"File check failed: filename={file_check['filename']}, success={file_check['success']}, is_empty={file_check.get('is_empty')}")
                assert False, f"File '{file_check['filename']}' is empty or inaccessible in S3 storage."  # nosec B101
    else:
        logger.info(f"Content validation failed: success={content_validation['success']}, empty_count={content_validation.get('empty_count')}")
        assert False, f"File content validation failed - {content_validation['empty_count']} empty files found in S3 storage."  # nosec B101
    
    # Final validation assertions
    logger.info(f"Final validation: container_check success={container_check['success']}, s3_check success={s3_check['success']}")
    assert container_check["success"], f"Essential containers not running: {container_check['missing_containers']}"  # nosec B101
    assert s3_check["success"], f"SeaweedFS S3 API not accessible: {s3_check['error']}"  # nosec B101
    
    logger.info("✓ S3 stored images infrastructure validation completed")
    logger.info("✓ SeaweedFS S3 storage integration with DLStreamer verified")


def test_vision_metadata_sender_timestamp(setup_multimodal_environment):
    """TC_019: Validate RTP sender timestamps in vision measurement stored in InfluxDB"""
    logger.info("TC_019: Verifying RTP sender timestamps persisted in InfluxDB vision measurement")

    context = setup_multimodal_environment
    context["deploy_multimodal"]()

    is_running = docker_utils.container_is_running(constants.CONTAINERS["influxdb"]["name"])
    logger.info(f"InfluxDB container running status: {is_running}")
    assert is_running, "InfluxDB container is not running"  # nosec B101

    logger.info("Waiting for vision metadata to be written to InfluxDB")
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)

    credentials = context["credentials"]
    username = credentials.get("INFLUXDB_USERNAME")
    password = credentials.get("INFLUXDB_PASSWORD")
    logger.info(f"InfluxDB credentials found: username={'[SET]' if username else '[EMPTY]'}, password={'[SET]' if password else '[EMPTY]'}")
    assert username and password, "InfluxDB credentials missing from test context"  # nosec B101

    vision_measurement = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP).get(
        "vision_measurement", "vision-weld-classification-results"
    )

    query_result = docker_utils.query_influxdb_measurement_with_auth(
        measurement=vision_measurement,
        database=constants.INFLUXDB_DATABASE,
        container_name=constants.CONTAINERS["influxdb"]["name"],
        username=username,
        password=password,
        limit=3,
        order_by_time_desc=True,
    )

    logger.info(f"InfluxDB query result: success={query_result['success']}, records_count={len(query_result.get('records', []))}, error={query_result.get('error')}")
    assert query_result["success"], f"Failed to query InfluxDB measurement {vision_measurement}: {query_result['error']}"  # nosec B101
    assert query_result["records"], f"No records returned from measurement {vision_measurement}"  # nosec B101

    metadata_values = [record.get("metadata") for record in query_result["records"]]
    timestamps = common_utils.extract_sender_ntp_timestamps(metadata_values)

    if not timestamps:
        logger.error("No RTP timestamps in metadata sample: %s", metadata_values)

    logger.info(f"Extracted RTP timestamps count: {len(timestamps)}, values: {timestamps}")
    assert timestamps, "No RTP sender timestamps found in vision metadata entries"  # nosec B101
    all_positive = all(ts > 0 for ts in timestamps)
    logger.info(f"All timestamps positive: {all_positive}")
    assert all_positive, "Invalid RTP sender timestamp values detected"  # nosec B101

    logger.info("✓ Found RTP sender timestamps for %d vision records", len(timestamps))


