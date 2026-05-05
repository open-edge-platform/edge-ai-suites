#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
import helm_utils
import docker_utils
import security_utils
import constants
import subprocess
import time
import logging
import asyncio

# Set up logger
logger = logging.getLogger(__name__)

pytest_plugins = ["conftest_helm", "conftest_docker"]

# Helm environment variables
FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL = helm_utils.get_env_values()

# Docker environment variables
docker_wait_time, docker_target, docker_grafana_port, docker_mqtt_port, docker_opcua_port = docker_utils.get_docker_env_values()
DOCKER_PROXY_URL = os.getenv("DOCKER_PROXY_URL", None)

# Check if Helm environment variables are set
if not all([release_name, chart_path, namespace, grafana_url, target]):
    raise EnvironmentError("One or more Helm environment variables are not set.")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])    
def test_authentication_influx_grafana(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_001: Verify influxdb authentication and grafana authentication w.r.t. username password provided in values.yaml")
    pods_result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {pods_result}")
    assert pods_result == True, "Failed to verify pods in the namespace."
    # Access the test cases dictionary
    setup_result = helm_utils.setup_sample_app_udf_deployment_package(chart_path)
    logger.info(f"setup_sample_app_udf_deployment_package result: {setup_result}")
    assert setup_result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    ts_logs_result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {ts_logs_result}")
    assert ts_logs_result is True, "Failed to verify pod logs for OPC-UA input plugin."
    # Access the test cases dictionary
    influxdb_username, influxdb_password = security_utils.fetch_credentials(chart_path, "influxdb")
    logger.info(f"INFLUXDB_USERNAME: {influxdb_username}, INFLUXDB_PASSWORD: {influxdb_password}")
    influxdb_login_result = security_utils.influxdb_login(namespace, chart_path)
    logger.info(f"influxdb_login result: {influxdb_login_result}")
    assert influxdb_login_result == True, "Failed to login to InfluxDB with provided credentials."
    grafana_username, grafana_password = security_utils.fetch_credentials(chart_path, "grafana")
    logger.info("Successfully retrieved Grafana credentials.")
    grafana_login_result = asyncio.run(security_utils.login_to_grafana(grafana_url, grafana_username, grafana_password))
    logger.info(f"login_to_grafana result: {grafana_login_result}")
    assert grafana_login_result == True, "Failed to login to Grafana with provided credentials."

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])    
def test_nmap_open_ports_opcua(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_002: Verify nmap open ports functionality with opcua.")
    pods_result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {pods_result}")
    assert pods_result == True, "Failed to verify pods in the namespace."
    setup_result = helm_utils.setup_sample_app_udf_deployment_package(chart_path)
    logger.info(f"setup_sample_app_udf_deployment_package result: {setup_result}")
    assert setup_result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    ts_logs_result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {ts_logs_result}")
    assert ts_logs_result is True, "Failed to verify pod logs for OPC-UA input plugin."
    exposed_ports = security_utils.find_exposed_ports_helm(namespace)
    nmap_result = security_utils.check_nmap(target, exposed_ports)
    logger.info(f"check_nmap result: {nmap_result}")
    assert nmap_result == True, "Failed to find open ports on the target."

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])    
def test_nmap_open_ports_mqtt(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_003: Verify nmap open ports functionality with mqtt.")
    pods_result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {pods_result}")
    assert pods_result == True, "Failed to verify pods in the namespace."
    setup_result = helm_utils.setup_sample_app_udf_deployment_package(chart_path)
    logger.info(f"setup_sample_app_udf_deployment_package result: {setup_result}")
    assert setup_result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    ts_logs_result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {ts_logs_result}")
    assert ts_logs_result is True, "Failed to verify pod logs for MQTT input plugin."
    exposed_ports = security_utils.find_exposed_ports_helm(namespace)
    nmap_result = security_utils.check_nmap(target, exposed_ports)
    logger.info(f"check_nmap result: {nmap_result}")
    assert nmap_result == True, "Failed to find open ports on the target."

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_creds_in_pod_logs(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_004: Verify that credentials are not present in pod logs.")
    pods_result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {pods_result}")
    assert pods_result == True, "Failed to verify pods in the namespace."
    setup_result = helm_utils.setup_sample_app_udf_deployment_package(chart_path)
    logger.info(f"setup_sample_app_udf_deployment_package result: {setup_result}")
    assert setup_result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    ts_logs_result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {ts_logs_result}")
    assert ts_logs_result is True, "Failed to verify pod logs for OPC-UA input plugin."
    influxdb_creds = security_utils.fetch_credentials(chart_path, "influxdb")
    grafana_creds = security_utils.fetch_credentials(chart_path, "grafana")
    pods_creds_result = security_utils.verify_pods_creds(namespace, influxdb_creds, grafana_creds)
    logger.info(f"verify_pods_creds result: {pods_creds_result}")
    assert pods_creds_result == True, "Credentials found in pod logs."

def test_data_integrity():
    logger.info("TC_005: Verify data integrity in the system.")
    docker_file_integrity_result = security_utils.verify_docker_file_integrity()
    logger.info(f"verify_docker_file_integrity result: {docker_file_integrity_result}")
    assert docker_file_integrity_result == True, "Docker-compose file integrity verification failed."
    helm_file_integrity_result = security_utils.verify_helm_file_integrity()
    logger.info(f"verify_helm_file_integrity result: {helm_file_integrity_result}")
    assert helm_file_integrity_result == True, "Helm files integrity verification failed."
    uninstall_result = helm_utils.uninstall_helm_charts(release_name, namespace)
    logger.info(f"uninstall_helm_charts result: {uninstall_result}")
    assert uninstall_result == True, "Failed to uninstall Helm release."
    check_pods_result = helm_utils.check_pods(namespace)
    logger.info(f"check_pods result: {check_pods_result}")
    assert check_pods_result == True, "Pods are still running after cleanup."
    logger.info("Helm release is uninstalled if it exists")
    case = helm_utils.password_test_cases["test_case_3"]
    logger.info("Validating pod logs with respect to log level : debug")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    update_yaml_result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {update_yaml_result}")
    assert update_yaml_result == True, "Failed to update values.yaml."
    logger.info(f"Helm will be installed with, Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    helm_install_result = helm_utils.helm_install(release_name, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN, continuous_simulator_ingestion="false")
    logger.info(f"helm_install result: {helm_install_result}")
    assert helm_install_result == True, "Failed to install Helm release."
    time.sleep(5)  # Wait for the pods to stabilize
    pods_result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {pods_result}")
    assert pods_result is True, "Failed to verify pods."
    logger.info("All pods are running")
    setup_result = helm_utils.setup_sample_app_udf_deployment_package(chart_path)
    logger.info(f"setup_sample_app_udf_deployment_package result: {setup_result}")
    assert setup_result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and Wait for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    pods_result_2 = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result (case 3): {pods_result_2}")
    assert pods_result_2 is True, "Failed to verify pods for Case 3."
    ts_logs_result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {ts_logs_result}")
    assert ts_logs_result is True, "Failed to verify pod logs for MQTT input plugin."
    first_wind_speed, last_wind_speed, total_records = security_utils.fetch_wind_turbine_data()
    assert first_wind_speed is not None or last_wind_speed is not None or total_records is not None, "Failed to fetch wind turbine data."
    logger.info(f"First wind speed: {first_wind_speed}, Last wind speed: {last_wind_speed}, Total records: {total_records} and wait for few {wait_time + 300} seconds to finish 1st set of ingestion data")
    time.sleep(wait_time + 300)
    influxdb_login_result = security_utils.influxdb_login(namespace, chart_path)
    logger.info(f"influxdb_login result: {influxdb_login_result}")
    assert influxdb_login_result == True, "Failed to login to InfluxDB with provided credentials."
    logger.info("Verifying data integrity in InfluxDB.")
    data_integrity_result = security_utils.verify_data_integrity_influxdb(chart_path, namespace, first_wind_speed, last_wind_speed, total_records)
    logger.info(f"verify_data_integrity_influxdb result: {data_integrity_result}")
    assert data_integrity_result == True, "Data integrity verification failed in InfluxDB."
    time.sleep(5)
    uninstall_result_2 = helm_utils.uninstall_helm_charts(release_name, namespace)
    logger.info(f"uninstall_helm_charts result: {uninstall_result_2}")
    assert uninstall_result_2 == True, "Failed to uninstall Helm release after data integrity test."
    check_pods_result_2 = helm_utils.check_pods(namespace)
    logger.info(f"check_pods result: {check_pods_result_2}")
    assert check_pods_result_2 == True, "Pods are still running after cleanup."

@pytest.mark.docker_security   
def test_nmap_open_ports_opcua_docker(setup_docker_environment):
    logger.info("TC_006: Verify nmap open ports functionality with opcua using Docker.")
    
    # Access the context from setup_docker_environment fixture
    context = setup_docker_environment
    
    # Deploy and verify Docker containers with OPC-UA ingestion (includes nmap scan)
    results = docker_utils.deploy_and_verify(context, deploy_type="opcua", include_nmap=True)
    
    logger.info("Successfully completed nmap scan on Docker exposed ports.")

@pytest.mark.docker_security   
def test_nmap_open_ports_mqtt_docker(setup_docker_environment):
    logger.info("TC_007: Verify nmap open ports functionality with mqtt using Docker.")
    
    # Access the context from setup_docker_environment fixture
    context = setup_docker_environment
    
    # Deploy and verify Docker containers with MQTT ingestion (includes nmap scan)
    results = docker_utils.deploy_and_verify(context, deploy_type="mqtt", include_nmap=True)
    
    logger.info("Successfully completed nmap scan on Docker exposed ports.")
  
@pytest.mark.docker_security
def test_authentication_influx_grafana_docker(setup_docker_environment):
    logger.info("TC_008: Verify influxdb authentication and grafana authentication for Docker deployment.")
    
    # Access the context from setup_docker_environment fixture
    context = setup_docker_environment
    
    # Deploy and verify Docker containers with OPC-UA ingestion (without nmap scan)
    results = docker_utils.deploy_and_verify(context, deploy_type="opcua", include_nmap=False)
    
    # Test InfluxDB authentication using Docker-specific function
    influxdb_username, influxdb_password = security_utils.fetch_docker_credentials("influxdb")
    logger.info("Successfully retrieved InfluxDB credentials.")
    influxdb_login_result = security_utils.influxdb_login_docker()
    logger.info(f"influxdb_login_docker result: {influxdb_login_result}")
    assert influxdb_login_result == True, "Failed to login to InfluxDB with provided credentials."
    
    # Test Grafana authentication using Docker-specific function
    grafana_username, grafana_password = security_utils.fetch_docker_credentials("grafana")
    logger.info("Successfully retrieved Grafana credentials.")
    grafana_login_result = asyncio.run(security_utils.login_to_grafana_docker(port=context["docker_grafana_port"]))
    logger.info(f"login_to_grafana_docker result: {grafana_login_result}")
    assert grafana_login_result == True, "Failed to login to Grafana with provided credentials."
    
    logger.info("Successfully completed authentication tests for Docker deployment.")


@pytest.mark.docker_security
def test_verify_sensitive_data_in_mqtt_logs(setup_docker_environment):
    """
    TC_009: Test credentials verification in MQTT deployment
    
    Verify that:
    1. Environment variables can be read from .env file (set by fixture)
    2. MQTT deployment can be started with those credentials
    3. Containers are running properly
    4. Credentials are present in container logs
    """
    logger.info("TC_009: Testing MQTT deployment with credentials verification in logs")
    
    # Use the setup fixture to get the environment ready
    context = setup_docker_environment
    
    # Read the current values from .env file that were set by the fixture
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    logger.info("Reading credentials from .env file that were set by the fixture")
    
    # Use the function we created to read environment variables from .env file
    env_vars = docker_utils.read_env_file(env_file_path)
    
    # Log the credential fields we'll be checking (without exposing the actual values)
    credential_fields = docker_utils.get_credential_fields()
    found_credentials = [field for field in credential_fields if field in env_vars]
    logger.info(f"Found credential fields in .env: {found_credentials}")
    
    # Verify the deployment with credentials set by the fixture
    results = docker_utils.verify_deployment_with_credentials(ingestion_type="mqtt")
    
    # Log detailed results (without exposing credential values)
    safe_results = results.copy()
    if "env_vars" in safe_results:
        credential_count = len([k for k in safe_results["env_vars"] if k in credential_fields])
        safe_results["env_vars"] = f"{credential_count} credential variables found"
    logger.info(f"Verification results: {safe_results}")
    
    # Check if verification was successful
    logger.info(f"Credential verification results: success={results['success']}, env_read={results.get('env_variables_read')}, deploy={results.get('deployment_success')}, containers_up={results.get('containers_up')}, creds_in_logs={results.get('credentials_in_logs')}")
    assert results["success"], f"Credential verification failed at step: {results.get('failed_step', 'unknown')}"
    
    logger.info("Successfully verified MQTT deployment with credentials in logs")
    
    # Individual assertions for better test reporting
    assert results["env_variables_read"], "Failed to read environment variables"
    assert results["deployment_success"], "Failed to deploy containers"
    assert results["containers_up"], "Containers are not running"
    assert results["credentials_in_logs"], "Credentials not found in container logs"
    
    # Cleanup handled by fixture

@pytest.mark.docker_security
def test_verify_sensitive_data_in_opcua_logs(setup_docker_environment):
    """
    TC_009: Test credentials verification in OPCUA deployment
    
    Verify that:
    1. Environment variables can be read from .env file (set by fixture)
    2. OPCUA deployment can be started with those credentials
    3. Containers are running properly
    4. Credentials are present in container logs
    """
    logger.info("TC_009: Testing OPCUA deployment with credentials verification in logs")
    
    # Use the setup fixture to get the environment ready
    context = setup_docker_environment
    
    # Read the current values from .env file that were set by the fixture
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    logger.info("Reading credentials from .env file that were set by the fixture")
    
    # Use the function we created to read environment variables from .env file
    env_vars = docker_utils.read_env_file(env_file_path)
    
    # Log the credential fields we'll be checking (without exposing the actual values)
    credential_fields = docker_utils.get_credential_fields()
    found_credentials = [field for field in credential_fields if field in env_vars]
    logger.info(f"Found credential fields in .env: {found_credentials}")
    
    # Verify the deployment with credentials set by the fixture
    results = docker_utils.verify_deployment_with_credentials(ingestion_type="opcua")
    
    # Log detailed results (without exposing credential values)
    safe_results = results.copy()
    if "env_vars" in safe_results:
        credential_count = len([k for k in safe_results["env_vars"] if k in credential_fields])
        safe_results["env_vars"] = f"{credential_count} credential variables found"
    logger.info(f"Verification results: {safe_results}")
    
    # Check if verification was successful
    logger.info(f"Credential verification results: success={results['success']}, env_read={results.get('env_variables_read')}, deploy={results.get('deployment_success')}, containers_up={results.get('containers_up')}, creds_in_logs={results.get('credentials_in_logs')}")
    assert results["success"], f"Credential verification failed at step: {results.get('failed_step', 'unknown')}"
    
    logger.info("Successfully verified OPCUA deployment with credentials in logs")
    
    # Individual assertions for better test reporting
    assert results["env_variables_read"], "Failed to read environment variables"
    assert results["deployment_success"], "Failed to deploy containers"
    assert results["containers_up"], "Containers are not running"
    assert results["credentials_in_logs"], "Credentials not found in container logs"
    
    # Cleanup handled by fixture
