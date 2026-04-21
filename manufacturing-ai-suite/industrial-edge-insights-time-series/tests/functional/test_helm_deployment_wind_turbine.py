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
import constants
#import subprocess
import time
import logging

logger = logging.getLogger(__name__)  # Get a logger for this module specifically

# Import the fixture directly from conftest_helm.py
pytest_plugins = ["conftest_helm"]

FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL = helm_utils.get_env_values()

def test_gen_chart():
    logger.info("TC001: Generating helm chart.")
    result = helm_utils.generate_helm_chart(chart_path)
    logger.info(f"generate_helm_chart result: {result}")
    assert result == True, "Failed to generate helm chart."
    logger.info("Helm Chart is generated")
    logger.info("Current directory1 %s", os.getcwd())
    os.chdir(constants.PYTEST_DIR)
    logger.info("Current directory2 %s", os.getcwd())
    
def test_blank_values():
    logger.info("TC_002: Testing blank values, checking helm install and uninstall with blank values in values.yaml")
    # Access the test cases dictionary
    case = helm_utils.password_test_cases["test_case_1"]
    result = helm_utils.uninstall_helm_charts(release_name, namespace)
    logger.info(f"uninstall_helm_charts result: {result}")
    assert result == True, "Failed to uninstall Helm release if exists."
    logger.info("Helm release is uninstalled if it exists")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {result}")
    assert result == True, "Failed to update values.yaml."  
    logger.info(f"Case 1 - Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin opcua: {constants.TELEGRAF_OPCUA_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    result = helm_utils.helm_install(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN)
    logger.info(f"helm_install result: {result}")
    assert result == False
    logger.info("Helm is not installed for Case 1: blank yaml values")
    
def test_invalid_values():
    logger.info("TC_003: Testing invalid values, checking helm install and uninstall with invalid values in values.yaml")
    # Access the test cases dictionary
    case = helm_utils.password_test_cases["test_case_2"]
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {result}")
    assert result == True, "Failed to update values.yaml."

    logger.info(f"Case 2 - Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin opcua: {constants.TELEGRAF_OPCUA_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    result = helm_utils.helm_install(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN)
    logger.info(f"helm_install result: {result}")
    assert result == False
    logger.info("Helm is not installed for Case 2: invalid yaml values")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN]) 
def test_valid_values(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_004: Testing valid values, checking helm install and uninstall with valid values in values.yaml")
    # Access the test cases dictionary

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])   
def test_helm_install_opcua(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_005: Testing OPC UA input plugin, checking helm install and uninstall with valid values in values.yaml")
    # Define the path to the config.json file
    
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_helm_install_mqtt(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_006: Testing MQTT input plugin, checking helm install and uninstall with valid values in values.yaml")


def test_verify_pods_all_running_opcua_switch_to_mqtt(setup_helm_environment):
    logger.info("TC_007: Testing switch from OPC UA to MQTT input plugin, checking helm install and uninstall with valid values in values.yaml")
    # Cleanup before starting
    result = helm_utils.uninstall_helm_charts(release_name, namespace)
    logger.info(f"uninstall_helm_charts result: {result}")
    assert result == True, "Failed to uninstall Helm release."
    logger.info("Helm release is uninstalled if it exists")
    result = helm_utils.check_pods(namespace)
    logger.info(f"check_pods result: {result}")
    assert result == True, "Pods are still running after cleanup."
    case = helm_utils.password_test_cases["test_case_3"]
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {result}")
    assert result == True, "Failed to update values.yaml."
    # Determine SAMPLE_APP based on release name to match UDF package directory
    sample_app = "wind-turbine-anomaly-detection" if "wind" in release_name.lower() else "weld-defect-detection"
    result = helm_utils.helm_install(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN, sample_app=sample_app)
    logger.info(f"helm_install result: {result}")
    assert result == True, "Failed to install Helm release."
    logger.info("Helm is installed for opcua input plugin")
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")
    result = helm_utils.helm_uninstall(release_name, namespace)
    logger.info(f"helm_uninstall result: {result}")
    assert result == True, "Failed to uninstall Helm release."
    logger.info("Helm is uninstalled for opcua input plugin")
    result = helm_utils.helm_install(release_name, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN)
    logger.info(f"helm_install result: {result}")
    assert result == True, "Failed to install Helm release."
    logger.info("Helm is installed for mqtt input plugin")
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    result = helm_utils.helm_uninstall(release_name, namespace)
    logger.info(f"helm_uninstall result: {result}")
    assert result == True, "Failed to uninstall Helm release."
    logger.info("Helm is uninstalled for mqtt input plugin")
    result = helm_utils.check_pods(namespace)
    logger.info(f"check_pods result: {result}")
    assert result == True, "Pods are still running after cleanup."
    
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_verify_pods_opcua_for_5mins(setup_helm_environment, telegraf_input_plugin):
    
    logger.info("TC_008: Testing OPC UA input plugin for 5 minutes, checking helm install, pod logs and uninstall with valid values in values.yaml")
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF deployment package is activated")
    # Get the current system time
    logger.info("Wait for the application to run for 5 minutes...")
    time.sleep(300)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods_logs(namespace, "DEBUG")
    logger.info(f"verify_pods_logs result: {result}")
    assert result is True, "Failed to verify pod logs for OPC UA input plugin."
    logger.info("Pods logs are working for opcua input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_verify_pods_stability_after_udf_activation(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_009: Testing pods stability after UDF activation for OPC UA input plugin, checking helm install, pod logs and uninstall with valid values in values.yaml")
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods_logs(namespace, "error")
    logger.info(f"verify_pods_logs result: {result}")
    assert result == False, "Pod logs didn't show error type logs when udf package is not activated"
    logger.info("Pod logs shows error message as udf package is not activated")

    # Step 1: Configure OPC UA alert in TICK script
    logger.info("Step 1: Configuring OPC UA alert in TICK script...")
    result = helm_utils.setup_opcua_alerts(chart_path)
    logger.info(f"setup_opcua_alerts result: {result}")
    assert result == True, "Failed to configure OPC UA alert in TICK script."
    logger.info("OPC UA alert configured in TICK script successfully")

    # Step 2: Upload UDF deployment package
    logger.info("Step 2: Uploading UDF deployment package...")
    result = helm_utils.upload_udf_tar_package(chart_path, constants.WIND_SAMPLE_APP)
    logger.info(f"upload_udf_tar_package result: {result}")
    assert result == True, "Failed to upload UDF deployment package."
    logger.info("UDF deployment package uploaded successfully")

    # Step 3: Configure OPC UA alert in config.json and activate
    logger.info("Step 3: Configuring OPC UA alert in config.json and activating...")
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP, alert_mode="opcua")
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods_logs(namespace, "DEBUG")
    logger.info(f"verify_pods_logs result: {result}")
    assert result is True, "Failed to verify pod logs for opcua input plugin."
    logger.info("Pod logs are verified for opcua input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_verify_pods_stability_after_influxdb_restart(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_010: Testing pods stability after InfluxDB restart for OPC UA input plugin, checking helm install, pod logs and uninstall with valid values in values.yaml")
    
    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")
    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods_logs(namespace, "DEBUG")
    logger.info(f"verify_pods_logs result: {result}")
    assert result is True, "Failed to verify pod logs for opcua input plugin."
    logger.info("Pod logs are verified for opcua input plugin")
    
    result = helm_utils.pod_restart(namespace)
    logger.info(f"pod_restart result: {result}")
    assert result == True, "Failed to restart pod for opcua input plugin."
    logger.info("Pod is restarted for opcua input plugin")
    time.sleep(1)
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for opcua input plugin."
    logger.info("All pods are running for opcua input plugin")
    result = helm_utils.verify_pods_logs(namespace, "DEBUG")
    logger.info(f"verify_pods_logs result: {result}")
    assert result is True, "Failed to verify pod logs for opcua input plugin."
    logger.info("Pod logs are verified for opcua input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_mqtt_alerts(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_011: Testing MQTT alerts, checking helm install and uninstall with valid values in values.yaml")
    # Set up MQTT alerts
    result = helm_utils.setup_mqtt_alerts(chart_path)
    logger.info(f"setup_mqtt_alerts result: {result}")
    assert result == True, "Failed to set up MQTT alerts."
    logger.info("MQTT alerts are set up successfully")
    time.sleep(3)
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    # Get the current system time
    logger.info(f"Wait for the application to run for {wait_time} seconds...")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    logger.info("Verifying pod logs for alerts...")
    result = helm_utils.verify_ts_logs_alerts(namespace, "mqtt")
    logger.info(f"verify_ts_logs_alerts result: {result}")
    assert result == True, "Failed to verify pod logs for mqtt input plugin."
    logger.info("Pods logs are working for mqtt input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_verify_pods_mqtt_for_5mins(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_012: Testing MQTT input plugin for 5 minutes, checking helm install, pod logs and uninstall with valid values in values.yaml") 
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    
    # Copy UDF package and activate
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF package copied and activated successfully")
    
    # Wait for Kapacitor to fully start after UDF installation (includes pip install with PyPI timeouts)
    max_wait_seconds = 420
    poll_interval_seconds = 10
    logger.info(
        "Waiting up to %ss for Kapacitor to install UDF packages and restart pods...",
        max_wait_seconds,
    )
    start_time = time.time()
    while True:
        if helm_utils.verify_pods(namespace):
            logger.info("Kapacitor and related pods are running after UDF deployment.")
            break

        elapsed = time.time() - start_time
        if elapsed >= max_wait_seconds:
            pytest.fail(
                f"Timed out after {max_wait_seconds}s waiting for Kapacitor pods to become ready after UDF deployment."
            )

        time.sleep(poll_interval_seconds)

    logger.info("Wait for the application to run for 5 minutes...")
    time.sleep(300)  # Wait for the pods to stabilize

    result = helm_utils.verify_pods_logs(namespace, "DEBUG")
    logger.info(f"verify_pods_logs result: {result}")
    assert result is True, "Failed to verify pod logs for MQTT input plugin."
    logger.info("Pods logs are working for mqtt input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_opcua_alerts(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_013: Testing OPCUA alerts, checking helm install and uninstall with valid values in values.yaml")
    
    time.sleep(3)
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")

    # Step 1: Configure OPC UA alert in TICK script
    logger.info("Step 1: Configuring OPC UA alert in TICK script...")
    result = helm_utils.setup_opcua_alerts(chart_path)
    logger.info(f"setup_opcua_alerts result: {result}")
    assert result == True, "Failed to set up OPC UA alerts."
    logger.info("OPC UA alert configured in TICK script successfully")

    # Step 2: Upload UDF deployment package
    logger.info("Step 2: Uploading UDF deployment package...")
    result = helm_utils.upload_udf_tar_package(chart_path, constants.WIND_SAMPLE_APP)
    logger.info(f"upload_udf_tar_package result: {result}")
    assert result == True, "Failed to upload UDF deployment package."
    logger.info("UDF deployment package uploaded successfully")

    # Step 3: Configure OPC UA alert in config.json and activate
    logger.info("Step 3: Configuring OPC UA alert in config.json and activating...")
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, alert_mode="opcua")
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF package configured and activated successfully")
    
    # Wait for Kapacitor to fully start after UDF installation (includes pip install with PyPI timeouts)
    max_wait_seconds = 420
    poll_interval_seconds = 10
    logger.info(
        "Waiting up to %ss for Kapacitor to install UDF packages and restart pods...",
        max_wait_seconds,
    )
    start_time = time.time()
    while True:
        if helm_utils.verify_pods(namespace):
            logger.info("Kapacitor and related pods are running after UDF deployment.")
            break

        elapsed = time.time() - start_time
        if elapsed >= max_wait_seconds:
            pytest.fail(
                f"Timed out after {max_wait_seconds}s waiting for Kapacitor pods to become ready after UDF deployment."
            )

        time.sleep(poll_interval_seconds)
    
    result = helm_utils.restart_deployment(namespace, "opcua-server")
    logger.info(f"restart_deployment result: {result}")
    assert result is True, "Failed to restart OPC UA server deployment."
    logger.info("OPC UA server deployment is restarted successfully")
    logger.info(f"Waiting {wait_time}s for OPC UA data processing and alert generation...")
    time.sleep(wait_time)
    result = helm_utils.verify_ts_logs_alerts(namespace, "opcua")
    logger.info(f"verify_ts_logs_alerts result: {result}")
    assert result is True, "Failed to verify pod logs for opcua input plugin."
    logger.info("Pods logs are working for opcua input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_verify_pods_logs_with_respect_to_log_level(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_014: Validating pod logs with respect to log level like error, debug, info")
    case = helm_utils.password_test_cases["test_case_4"]
    logger.info("Validating pod logs with respect to log level : error")
    result = helm_utils.uninstall_helm_charts(release_name, namespace)
    logger.info(f"uninstall_helm_charts result: {result}")
    assert result == True, "Failed to uninstall Helm release."
    logger.info("Helm release is uninstalled if it exists")
    result = helm_utils.check_pods(namespace)
    logger.info(f"check_pods result: {result}")
    assert result == True, "Pods are still running after cleanup."
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {result}")
    assert result == True, "Failed to update values.yaml."
    logger.info(f"Case 4 - Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin opcua: {constants.TELEGRAF_OPCUA_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    # Determine SAMPLE_APP based on release name to match UDF package directory
    sample_app = "wind-turbine-anomaly-detection" if "wind" in release_name.lower() else "weld-defect-detection"
    result = helm_utils.helm_install(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN, sample_app=sample_app)
    logger.info(f"helm_install result: {result}")
    assert result == True, "Failed to install Helm release."
    logger.info("Helm is installed for Case 4: Error log level")
    
    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for Case 4."
    logger.info("All pods are running")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    result = helm_utils.verify_ts_logs(namespace, "ERROR")
    logger.info(f"verify_ts_logs result: {result}")
    assert result == False, "Failed to verify pod logs for ERROR log level."
    logger.info("Pod logs for Error log level are verified for Case 4: Valid yaml values")
    case = helm_utils.password_test_cases["test_case_3"]
    logger.info("Validating pod logs with respect to log level : debug")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {result}")
    assert result == True, "Failed to update values.yaml."
    logger.info(f"Case 3 - Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin opcua: {constants.TELEGRAF_OPCUA_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    result = helm_utils.helm_upgrade(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN)
    logger.info(f"helm_upgrade result: {result}")
    assert result == True, "Failed to upgrade Helm release."
    logger.info("Helm is updated for Case 3: DEBUG log level")

    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for Case 3."
    logger.info("All pods are running")

    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and Wait for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {result}")
    assert result == True, "Failed to verify pod logs for DEBUG log level."
    logger.info("Pod logs for DEBUG log level are verified for Case 3: Valid yaml values")
    case = helm_utils.password_test_cases["test_case_5"]
    logger.info("Validating pod logs with respect to log level : info")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    result = helm_utils.update_values_yaml(values_yaml_path, case)
    logger.info(f"update_values_yaml result: {result}")
    assert result == True, "Failed to update values.yaml."
    logger.info(f"Case 5 - Release Name: {release_name}, Chart Path: {chart_path}, Namespace: {namespace}, Telegraf Input Plugin opcua: {constants.TELEGRAF_OPCUA_PLUGIN}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    result = helm_utils.helm_upgrade(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN)
    logger.info(f"helm_upgrade result: {result}")
    assert result == True, "Failed to upgrade Helm release."
    logger.info("Helm is updated for Case 5: INFO log level")
    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for Case 5."
    logger.info("All pods are running")
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time} seconds for pods to stabilize")
    time.sleep(wait_time)  # Wait for the pods to stabilize
    result = helm_utils.verify_ts_logs(namespace, "INFO")
    logger.info(f"verify_ts_logs result: {result}")
    assert result == True, "Failed to verify pod logs for INFO log level."
    logger.info("Pod logs for INFO log level are verified")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_influxdb_data_with_opcua(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_015: Testing InfluxDB data with opcua input plugin, checking helm install and uninstall with valid values in values.yaml")
    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")
    
    # Copy UDF package and activate - ConfigMap was already patched during helm_install
    # The API restart endpoint will stop Kapacitor, install UDF pip packages, then start Kapacitor
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, alert_mode="opcua")
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF package copied and activated successfully")
    
    # Wait for Kapacitor to fully start after UDF installation (includes pip install with PyPI timeouts)
    # This is required because the MQTT/OPC UA publisher waits for Kapacitor port 9092 to be accessible
    logger.info(f'Waiting {constants.UDF_DEPLOYMENT_TIMEOUT}s (3min) for Kapacitor to install UDF packages and start...')
    time.sleep(constants.UDF_DEPLOYMENT_TIMEOUT)
    
    # Restart OPC UA server to start publishing data after Kapacitor is ready
    result = helm_utils.restart_deployment(namespace, "opcua-server")
    logger.info(f"restart_deployment result: {result}")
    assert result is True, "Failed to restart OPC UA server deployment."
    logger.info("OPC UA server deployment is restarted successfully")
    
    # Wait for data to flow through the pipeline: OPC UA → Telegraf → InfluxDB
    logger.info(f"Waiting {wait_time}s for OPC UA data to flow to InfluxDB...")
    time.sleep(wait_time)
    
    result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {result}")
    assert result is True, "Failed to verify pod logs for OPC UA input plugin."
    # InfluxDB connectivity test (simplified approach aligned with 08Weekly)
    logger.info("Verifying basic InfluxDB connectivity for opcua input plugin")
    result = helm_utils.verify_influxdb_connectivity(namespace, chart_path)
    logger.info(f"verify_influxdb_connectivity result: {result}")
    assert result is True, "Failed to verify InfluxDB connectivity for OPC UA input plugin."
    logger.info("InfluxDB connectivity verified successfully for opcua input plugin")

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_influxdb_data_with_mqtt(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_016: Testing InfluxDB data with mqtt input plugin, checking helm install and uninstall with valid values in values.yaml")
    time.sleep(3)  # Wait for the pods to stabilize
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")
    
    # Copy UDF package and activate - ConfigMap was already patched during helm_install
    # The API restart endpoint will stop Kapacitor, install UDF pip packages, then start Kapacitor
    result = helm_utils.setup_sample_app_udf_deployment_package(chart_path, alert_mode="mqtt")
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF package copied and activated successfully")
    
    # Wait for Kapacitor to fully start after UDF installation (includes pip install with PyPI timeouts)
    # This is required because the MQTT publisher waits for Kapacitor port 9092 to be accessible
    logger.info(f"Waiting {constants.UDF_DEPLOYMENT_TIMEOUT}s (3min) for Kapacitor to install UDF packages and start...")
    time.sleep(constants.UDF_DEPLOYMENT_TIMEOUT)
    
    # Verify MQTT data is being published before checking InfluxDB
    logger.info("Verifying MQTT data ingestion from publisher pod...")
    result = helm_utils.wait_for_mqtt_sample(namespace, constants.WIND_TURBINE_INGESTED_TOPIC, timeout=120)
    logger.info(f"wait_for_mqtt_sample result: {result}")
    assert result == True, "Failed to observe MQTT data before InfluxDB verification."
    logger.info(f"MQTT data confirmed. Waiting additional {wait_time}s for data to flow to InfluxDB...")
    time.sleep(wait_time)
    
    result = helm_utils.verify_ts_logs(namespace, "DEBUG")
    logger.info(f"verify_ts_logs result: {result}")
    assert result is True, "Failed to verify pod logs for MQTT input plugin."
    # InfluxDB connectivity test (simplified approach aligned with 08Weekly)
    logger.info("Verifying basic InfluxDB connectivity for mqtt input plugin")
    result = helm_utils.verify_influxdb_connectivity(namespace, chart_path)
    logger.info(f"verify_influxdb_connectivity result: {result}")
    assert result is True, "Failed to verify InfluxDB connectivity for MQTT input plugin."
    logger.info("InfluxDB connectivity verified successfully for mqtt input plugin")
   
def test_mqtt_time_kpi():
    logger.info("TC_017: Testing deployment of helm setup with mqtt- KPI")
    # Measure build time using our helper function
    success_rate, avg_time, min_time, max_time, times = helm_utils.measure_deployment_time("mqtt", release_name,
        iterations=constants.KPI_TEST_ITERATIONS
    )
    # Verify KPIs are met
    assert success_rate == constants.KPI_REQUIRED_SUCCESS_RATE, \
        f"Build success rate {success_rate}% below required {constants.KPI_REQUIRED_SUCCESS_RATE}%"
    assert avg_time <= constants.KPI_BUILD_TIME_THRESHOLD, \
        f"Average build time {avg_time:.2f}s exceeds threshold of {constants.KPI_BUILD_TIME_THRESHOLD}s"

def test_opcua_time_kpi():
    logger.info("TC_018: Testing deployment of helm setup with opcua- KPI")
    # Measure build time using our helper function
    success_rate, avg_time, min_time, max_time, times = helm_utils.measure_deployment_time("opcua", release_name,
        iterations=constants.KPI_TEST_ITERATIONS
    )
    # Verify KPIs are met
    assert success_rate == constants.KPI_REQUIRED_SUCCESS_RATE, \
        f"Build success rate {success_rate}% below required {constants.KPI_REQUIRED_SUCCESS_RATE}%"
    assert avg_time <= constants.KPI_BUILD_TIME_THRESHOLD, \
        f"Average build time {avg_time:.2f}s exceeds threshold of {constants.KPI_BUILD_TIME_THRESHOLD}s"
    
@pytest.mark.skipif(not docker_utils.check_system_gpu_devices(), reason="No GPU devices detected on this system")
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_gpu_opcua_helm(setup_helm_environment, request, telegraf_input_plugin):
    """TC_019: Testing GPU device configuration in time-series analytics helm config with OPC-UA"""
    logger.info("TC_019: Testing GPU device configuration in time-series analytics helm config with OPC-UA")
    
    # Verify pods are running
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for OPC UA input plugin."
    logger.info("All pods are running for opcua input plugin")

    # Get the corrected chart path from the setup fixture
    actual_chart_path = getattr(request.node, 'actual_chart_path', chart_path)
    
    # Set up UDF deployment package
    result = helm_utils.setup_sample_app_udf_deployment_package(actual_chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF deployment package is activated")

    # Wait for containers to stabilize and data to be generated
    logger.info("Waiting for containers to stabilize and data to be generated...")
    time.sleep(wait_time)
    
    # Execute curl command to post GPU configuration to the API using REST API approach
    curl_result = helm_utils.execute_gpu_config_curl_helm(device="gpu", namespace=namespace)
    
    # Verify the curl command was successful
    logger.info("Verifying GPU configuration test completed successfully")
    logger.info(f"curl_result: {curl_result}")
    assert curl_result, "GPU configuration test via REST API failed"

@pytest.mark.skipif(not docker_utils.check_system_gpu_devices(), reason="No GPU devices detected on this system")
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_gpu_mqtt_helm(setup_helm_environment, request, telegraf_input_plugin):
    """TC_020: Testing GPU device configuration in time-series analytics helm config with MQTT"""
    logger.info("TC_020: Testing GPU device configuration in time-series analytics helm config with MQTT")
    
    # Verify pods are running
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods for MQTT input plugin."
    logger.info("All pods are running for mqtt input plugin")

    # Get the corrected chart path from the setup fixture
    actual_chart_path = getattr(request.node, 'actual_chart_path', chart_path)
    
    # Set up UDF deployment package
    result = helm_utils.setup_sample_app_udf_deployment_package(actual_chart_path, sample_app=constants.WIND_SAMPLE_APP)
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result == True, "Failed to activate UDF deployment package."
    logger.info("UDF deployment package is activated")

    # Wait for containers to stabilize and data to be generated
    logger.info("Waiting for containers to stabilize and data to be generated...")
    time.sleep(wait_time)
    
    # Execute curl command to post GPU configuration to the API using REST API approach
    curl_result = helm_utils.execute_gpu_config_curl_helm(device="gpu", namespace=namespace)
    
    # Verify the curl command was successful
    logger.info("Verifying GPU configuration test completed successfully")
    logger.info(f"curl_result: {curl_result}")
    assert curl_result, "GPU configuration test via REST API failed"
