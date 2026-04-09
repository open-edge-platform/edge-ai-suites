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
import constants
import time
import logging
import subprocess
import json

logger = logging.getLogger(__name__)  # Get a logger for this module specifically

# Import the fixture directly from conftest_helm.py
pytest_plugins = ["conftest_helm"]

FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL = helm_utils.get_env_values()

def test_gen_chart():
    logger.info("TC001: Generating helm chart.")
    assert helm_utils.generate_helm_chart(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to generate helm chart."
    logger.info("Helm Chart is generated")
    logger.info("Current directory1 %s", os.getcwd())
    os.chdir(constants.PYTEST_DIR)
    logger.info("Current directory2 %s", os.getcwd())
    
def test_blank_values():
    logger.info("TC_002: Testing blank values, checking helm install and uninstall with blank values in values.yaml")
    # Access the test cases dictionary
    case = helm_utils.password_test_cases["test_case_1"]
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release if exists."
    logger.info("Helm release is uninstalled if it exists")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."  
    logger.info(f"Case 1 - Release Name: {release_name_weld}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_install(release_name_weld, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN) == False
    logger.info("Helm is not installed for Case 1: blank yaml values")
    
def test_invalid_values():
    logger.info("TC_003: Testing invalid values, checking helm install and uninstall with invalid values in values.yaml")
    # Access the test cases dictionary
    case = helm_utils.password_test_cases["test_case_2"]
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."

    logger.info(f"Case 2 - Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_install(release_name_weld, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN, sample_app=constants.WELD_SAMPLE_APP) == False
    logger.info("Helm is not installed for Case 2: invalid yaml values")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN]) 
def test_valid_values(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_004: Testing valid values, checking helm install and uninstall with valid values in values.yaml")
    # Access the test cases dictionary

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_helm_install_mqtt(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_006: Testing MQTT input plugin, checking helm install and uninstall with valid values in values.yaml")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_verify_pods_stability_after_udf_activation(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_007: Testing pods stability after UDF activation for MQTT input plugin, checking helm install, pod logs and uninstall with valid values in values.yaml")
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    time.sleep(60)  # Wait for the pods to stabilize
    # Verify basic logging is working (aligned with wind turbine test expectations)
    assert helm_utils.verify_ts_logs(namespace, "INFO") == True, "Failed to verify INFO logs in pod logs"
    logger.info("Pod logs show INFO messages as expected")

    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace, "DEBUG") is True, "Failed to verify pod logs for mqtt input plugin."
    logger.info("Pod logs are verified for mqtt input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_verify_pods_stability_after_influxdb_restart(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_008: Testing pods stability after InfluxDB restart for MQTT input plugin, checking helm install, pod logs and uninstall with valid values in values.yaml")

    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace, "DEBUG") is True, "Failed to verify pod logs for mqtt input plugin."
    logger.info("Pod logs are verified for mqtt input plugin")

    assert helm_utils.pod_restart(namespace) == True, "Failed to restart pod for mqtt input plugin."
    logger.info("Pod is restarted for mqtt input plugin")
    time.sleep(1)
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for mqtt input plugin."
    logger.info("All pods are running for mqtt input plugin")
    assert helm_utils.verify_ts_logs(namespace, "DEBUG") is True, "Failed to verify pod logs for mqtt input plugin."
    logger.info("Pod logs are verified for mqtt input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_mqtt_alerts(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_009: Testing MQTT alerts, checking helm install and uninstall with valid values in values.yaml")
    # Set up MQTT alerts
    assert helm_utils.setup_mqtt_alerts(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to set up MQTT alerts."
    logger.info("MQTT alerts are set up successfully")
    time.sleep(3)
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    # Get the current system time
    logger.info(f"Wait for the application to run for {wait_time} seconds...")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    logger.info("Verifying pod logs for alerts...")
    assert helm_utils.verify_ts_logs_alerts(namespace, "mqtt_weld") == True, "Failed to verify pod logs for mqtt input plugin."
    logger.info("Pods logs are working for mqtt input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_verify_pods_mqtt_for_5mins(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_010: Testing MQTT input plugin for 5 minutes, checking helm install, pod logs and uninstall with valid values in values.yaml") 
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    # Get the current system time
    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    logger.info("UDF deployment package is activated")

    logger.info("Wait for the application to run for 5 minutes...")
    time.sleep(300)  # Wait for the pods to stabilize

    assert helm_utils.verify_ts_logs(namespace, "DEBUG") is True, "Failed to verify pod logs for MQTT input plugin."
    logger.info("Pods logs are working for mqtt input plugin")

def test_verify_pods_logs_with_respect_to_log_level():
    logger.info("TC_011: Validating pod logs with respect to log level like error, debug, info")
    case = helm_utils.password_test_cases["test_case_4"]
    logger.info("Validating pod logs with respect to log level : error")
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release."
    logger.info("Helm release is uninstalled if it exists")
    assert helm_utils.check_pods(namespace) == True, "Pods are still running after cleanup."
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    logger.info(f"Case 4 - Release Name: {release_name_weld}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_install(release_name_weld, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN, sample_app=constants.WELD_SAMPLE_APP) == True, "Failed to install Helm release."
    logger.info("Helm is installed for Case 4: Error log level")
    
    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for Case 4."
    logger.info("All pods are running")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace, "ERROR") == False, "Failed to verify pod logs for ERROR log level."
    logger.info("Pod logs for Error log level are verified for Case 4: Valid yaml values")
    case = helm_utils.password_test_cases["test_case_3"]
    logger.info("Validating pod logs with respect to log level : debug")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    logger.info(f"Case 3 - Release Name: {release_name_weld}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_upgrade(release_name_weld, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN) == True, "Failed to upgrade Helm release."
    logger.info("Helm is updated for Case 3: DEBUG log level")

    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for Case 3."
    logger.info("All pods are running")

    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and Wait for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace, "DEBUG") == True, "Failed to verify pod logs for DEBUG log level."
    logger.info("Pod logs for DEBUG log level are verified for Case 3: Valid yaml values")
    case = helm_utils.password_test_cases["test_case_5"]
    logger.info("Validating pod logs with respect to log level : info")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    logger.info(f"Case 5 - Release Name: {release_name_weld}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_upgrade(release_name_weld, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN) == True, "Failed to upgrade Helm release."
    logger.info("Helm is updated for Case 5: INFO log level")
    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for Case 5."
    logger.info("All pods are running")
    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace, "INFO") == True, "Failed to verify pod logs for INFO log level."
    logger.info("Pod logs for INFO log level are verified")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_influxdb_data_with_mqtt(setup_helm_weld_environment, telegraf_input_plugin):
    logger.info("TC_012: Testing InfluxDB data with mqtt input plugin, checking helm install and uninstall with valid values in values.yaml")
    # Define the path to the config.json file     
    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.verify_pods(namespace) is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    # Get the current system time  
    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path, constants.WELD_SAMPLE_APP) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace, "DEBUG") is True, "Failed to verify pod logs for MQTT input plugin."
    # InfluxDB connectivity test (simplified approach aligned with 08Weekly)
    logger.info("Verifying basic InfluxDB connectivity for weld mqtt input plugin")
    assert helm_utils.verify_influxdb_connectivity(namespace, chart_path) is True, "Failed to verify InfluxDB connectivity for MQTT input plugin."
    logger.info("InfluxDB connectivity verified successfully for weld mqtt input plugin")
   
def test_mqtt_time_kpi():
    logger.info("TC_013: Testing deployment of helm setup with mqtt- KPI")
    # Measure build time using our helper function
    success_rate, avg_time, min_time, max_time, times = helm_utils.measure_deployment_time("mqtt", release_name_weld,
        iterations=constants.KPI_TEST_ITERATIONS
    )
    # Verify KPIs are met
    assert success_rate == constants.KPI_REQUIRED_SUCCESS_RATE, \
        f"Build success rate {success_rate}% below required {constants.KPI_REQUIRED_SUCCESS_RATE}%"
    assert avg_time <= constants.KPI_BUILD_TIME_THRESHOLD, \
        f"Average build time {avg_time:.2f}s exceeds threshold of {constants.KPI_BUILD_TIME_THRESHOLD}s"
    
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_helm_upgrade(setup_helm_weld_environment, telegraf_input_plugin):
    """TC_014: Verify Helm upgrade preserves data and maintains service continuity"""
    logger.info("TC_014: Testing Helm upgrade")
    
    # Step 1: Verify initial deployment is running
    logger.info("Step 1: Verifying initial deployment")
    assert helm_utils.verify_pods(namespace) is True, "Initial deployment failed"
    logger.info("✓ Initial deployment successful")
    
    # Step 2: Get initial pod count as baseline
    logger.info("Step 2: Recording baseline metrics")
    initial_pods = helm_utils.get_pod_names(namespace)
    initial_pod_count = len([p for p in initial_pods if 'deployment-' in p])
    logger.info(f"✓ Baseline: {initial_pod_count} pods running")
    
    # Step 3: Perform Helm upgrade (same version to test upgrade process)
    logger.info("Step 3: Performing Helm upgrade")
    assert helm_utils.helm_upgrade(release_name_weld, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN) is True, \
        "Helm upgrade failed"
    logger.info("✓ Helm upgrade command successful")
    
    # Step 4: Wait for rollout to complete
    logger.info("Step 4: Waiting for upgrade rollout to complete")
    time.sleep(30)  # Allow time for rolling update
    assert helm_utils.verify_pods(namespace) is True, "Pods not healthy after upgrade"
    logger.info("✓ All pods healthy after upgrade")
    
    # Step 5: Verify pod count remains the same
    logger.info("Step 5: Verifying pod count consistency")
    upgraded_pods = helm_utils.get_pod_names(namespace)
    upgraded_pod_count = len([p for p in upgraded_pods if 'deployment-' in p])
    assert upgraded_pod_count == initial_pod_count, \
        f"Pod count mismatch: expected {initial_pod_count}, got {upgraded_pod_count}"
    logger.info(f"✓ Pod count preserved: {upgraded_pod_count} pods")
    
    # Step 6: Verify all expected services still present
    logger.info("Step 6: Verifying all services remain available")
    expected_services = ['grafana', 'influxdb', 'mqtt-broker', 'mqtt-publisher', 
                         'nginx', 'telegraf', 'time-series-analytics-microservice']
    for service in expected_services:
        found = any(service in pod for pod in upgraded_pods)
        assert found, f"Service '{service}' missing after upgrade"
    logger.info("✓ All services remain available after upgrade")
    
    logger.info("TC_014 PASSED: Helm upgrade test")
