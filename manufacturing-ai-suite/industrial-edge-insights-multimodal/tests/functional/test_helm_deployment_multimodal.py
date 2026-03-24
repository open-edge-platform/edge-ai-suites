#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import pytest
import sys
import os
from utils import helm_utils
from utils import constants
from utils import common_utils
import time
import logging

logger = logging.getLogger(__name__)  # Get a logger for this module specifically

# Import the fixture directly from conftest_helm.py
pytest_plugins = ["conftest_helm"]

# Retrieve multimodal-specific environment variables so generic Helm tests remain untouched
(
    FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE,
    release_name_multi,
    release_name_weld_multi,
    chart_path_multi,
    namespace_multi,
    grafana_url_multi,
    wait_time_multi,
    target,
    PROXY_URL,
) = helm_utils.get_multimodal_env_values()

def test_gen_chart():
    logger.info("TC001: Generating helm chart for multimodal.")
    # Use generic chart path - the function will determine the correct path
    result = helm_utils.generate_helm_chart(chart_path_multi, constants.MULTIMODAL_SAMPLE_APP)
    assert result != False, "Failed to generate helm chart."
    logger.info(f"Helm Chart is generated at: {result}")
    logger.info("Current directory1 %s", os.getcwd())
    os.chdir(constants.PYTEST_DIR)
    logger.info("Current directory2 %s", os.getcwd())
    
def test_blank_values():
    logger.info("TC_002: Testing blank values, checking helm install and uninstall with blank values in values.yaml for multimodal")
    # Use multimodal-specific configuration
    multimodal_release_name = release_name_multi
    multimodal_chart_path = chart_path_multi
    multimodal_namespace = namespace_multi
    
    # Access the test cases dictionary
    case = helm_utils.password_test_cases["test_case_1"]
    assert helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace) == True, "Failed to uninstall Helm release if exists."
    logger.info("Helm release is uninstalled if it exists")
    values_yaml_path = os.path.expandvars(multimodal_chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    logger.info(f"Case 1 - Release Name: {multimodal_release_name}, Chart Path: {multimodal_chart_path}, Namespace: {multimodal_namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_install(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) == False
    logger.info("Helm is not installed for Case 1: blank yaml values")
    
def test_invalid_values():
    logger.info("TC_003: Testing invalid values, checking helm install and uninstall with invalid values in values.yaml for multimodal")
    # Use multimodal-specific configuration
    multimodal_release_name = release_name_multi
    multimodal_chart_path = chart_path_multi
    multimodal_namespace = namespace_multi
    
    # Access the test cases dictionary
    case = helm_utils.password_test_cases["test_case_2"]
    values_yaml_path = os.path.expandvars(multimodal_chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    
    logger.info(f"Case 2 - Release Name: {multimodal_release_name}, Chart Path: {multimodal_chart_path}, Namespace: {multimodal_namespace}, Telegraf Input Plugin mqtt: {constants.TELEGRAF_MQTT_PLUGIN}")
    assert helm_utils.helm_install(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) == False
    logger.info("Helm is not installed for Case 2: invalid yaml values")

def test_valid_values(setup_multimodal_helm_environment, request):
    logger.info("TC_004: Testing valid values, checking helm install and uninstall with valid values in values.yaml for multimodal")
    assert helm_utils.verify_pods(namespace_multi) is True, "Failed to verify pods for valid values test."
    logger.info("All pods are running for multimodal valid values test")

def test_helm_install(setup_multimodal_helm_environment, request):
    logger.info("TC_005: Testing helm install for multimodal, checking helm install and uninstall with valid values in values.yaml")
    assert helm_utils.verify_pods(namespace_multi) is True, "Failed to verify pods."
    logger.info("All pods are running for multimodal")
    
def test_multimodal_helm_install_uninstall():
    logger.info("TC_007: Testing multimodal helm install and uninstall functionality, checking helm install and uninstall with valid values in values.yaml")
    # Use multimodal-specific configuration
    multimodal_release_name = release_name_multi
    multimodal_chart_path = chart_path_multi
    multimodal_namespace = namespace_multi
    
    assert helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace) == True, "Failed to uninstall Helm release."
    logger.info("Helm release is uninstalled if it exists")
    assert helm_utils.check_pods(multimodal_namespace) == True, "Pods are still running after cleanup."
    
    case = helm_utils.password_test_cases["test_case_3"]
    values_yaml_path = os.path.expandvars(multimodal_chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    assert helm_utils.helm_install(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) == True, "Failed to install Helm release."
    logger.info("Helm is installed for multimodal")
    assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods."
    logger.info("All pods are running for multimodal")
    assert helm_utils.helm_uninstall(multimodal_release_name, multimodal_namespace) == True, "Failed to uninstall Helm release."
    logger.info("Helm is uninstalled for multimodal")
    assert helm_utils.check_pods(multimodal_namespace) == True, "Pods are still running after cleanup."

def test_verify_pods_stability_after_udf_activation(setup_multimodal_helm_environment, request):
    logger.info("TC_009: Testing pods stability after UDF activation for multimodal, checking helm install, pod logs and uninstall with valid values in values.yaml")
    assert helm_utils.verify_pods(namespace_multi) is True, "Failed to verify pods."
    logger.info("All pods are running")
    time.sleep(60)  # Wait for the pods to stabilize
    # Verify basic logging is working (aligned with wind turbine test expectations)
    assert helm_utils.verify_ts_logs(namespace_multi, "INFO") == True, "Failed to verify INFO logs in pod logs"
    logger.info("Pod logs show INFO messages as expected")

    assert helm_utils.setup_multimodal_udf_deployment_package(chart_path_multi, namespace_multi) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time_multi} seconds for pods to stabilize")
    time.sleep(wait_time_multi)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace_multi, "DEBUG") is True, "Failed to verify pod logs."
    logger.info("Pod logs are verified")

def test_verify_pods_stability_after_influxdb_restart(setup_multimodal_helm_environment, request):
    logger.info("TC_010: Testing pods stability after InfluxDB restart for multimodal, checking helm install, pod logs and uninstall with valid values in values.yaml")
    
    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.verify_pods(namespace_multi) is True, "Failed to verify pods."
    logger.info("All pods are running")
    time.sleep(3)  # Wait for the pods to stabilize
    assert helm_utils.setup_multimodal_udf_deployment_package(chart_path_multi, namespace_multi) == True, "Failed to activate UDF deployment package."
    logger.info(f"UDF deployment package is activated and waiting for {wait_time_multi} seconds for pods to stabilize")
    time.sleep(wait_time_multi)  # Wait for the pods to stabilize
    assert helm_utils.verify_ts_logs(namespace_multi, "DEBUG") is True, "Failed to verify pod logs."
    logger.info("Pod logs are verified")
    
    assert helm_utils.pod_restart(namespace_multi) == True, "Failed to restart pod."
    logger.info("Pod is restarted")
    time.sleep(1)
    assert helm_utils.verify_pods(namespace_multi) is True, "Failed to verify pods."
    logger.info("All pods are running")
    assert helm_utils.verify_ts_logs(namespace_multi, "DEBUG") is True, "Failed to verify pod logs."
    logger.info("Pod logs are verified")

def test_verify_pods_logs_with_respect_to_log_level_multimodal():
    logger.info("TC_011: Validating multimodal pod logs with respect to log level like error, debug, info")
    # Use multimodal-specific configuration derived from pytest env
    multimodal_release_name = release_name_weld_multi or release_name_multi
    multimodal_chart_path = chart_path_multi
    multimodal_namespace = namespace_multi

    values_yaml_path = os.path.expandvars(os.path.join(multimodal_chart_path, "values.yaml"))
    try:
        case = helm_utils.password_test_cases["test_case_4"]
        logger.info("Validating multimodal pod logs with respect to log level : error")
        assert helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace) is True, "Failed to uninstall Helm release."
        logger.info("Helm release is uninstalled if it exists")
        assert helm_utils.check_pods(multimodal_namespace) is True, "Pods are still running after cleanup."
        assert helm_utils.update_values_yaml(values_yaml_path, case) is True, "Failed to update values.yaml."
        logger.info(
            "Case 4 - Release Name: %s, Chart Path: %s, Namespace: %s, Telegraf Input Plugin mqtt: %s",
            multimodal_release_name,
            multimodal_chart_path,
            multimodal_namespace,
            constants.TELEGRAF_MQTT_PLUGIN,
        )
        assert helm_utils.helm_install(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) is True, "Failed to install Helm release."
        logger.info("Helm is installed for Case 4: Error log level")

        time.sleep(3)  # Wait for the pods to stabilize
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods for Case 4."
        logger.info("All pods are running")
        time.sleep(wait_time_multi)  # Wait for the pods to stabilize
        assert helm_utils.verify_ts_logs(multimodal_namespace, "ERROR") is False, "Found unexpected ERROR logs in pod logs (should be no errors with valid configuration)."
        logger.info("Pod logs verified - no ERROR logs found as expected for Case 4: Valid yaml values")

        case = helm_utils.password_test_cases["test_case_3"]
        logger.info("Validating multimodal pod logs with respect to log level : debug")
        assert helm_utils.update_values_yaml(values_yaml_path, case) is True, "Failed to update values.yaml."
        logger.info(
            "Case 3 - Release Name: %s, Chart Path: %s, Namespace: %s, Telegraf Input Plugin mqtt: %s",
            multimodal_release_name,
            multimodal_chart_path,
            multimodal_namespace,
            constants.TELEGRAF_MQTT_PLUGIN,
        )
        assert helm_utils.helm_upgrade(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) is True, "Failed to upgrade Helm release."
        logger.info("Helm is updated for Case 3: DEBUG log level")

        time.sleep(3)  # Wait for the pods to stabilize
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods for Case 3."
        logger.info("All pods are running")

        assert helm_utils.setup_multimodal_udf_deployment_package(multimodal_chart_path, multimodal_namespace) is True, "Failed to activate UDF deployment package."
        logger.info(f"UDF deployment package is activated and Wait for {wait_time_multi} seconds for pods to stabilize")
        time.sleep(wait_time_multi)  # Wait for the pods to stabilize
        assert helm_utils.verify_ts_logs(multimodal_namespace, "DEBUG") is True, "Failed to verify pod logs for DEBUG log level."
        logger.info("Pod logs for DEBUG log level are verified for Case 3: Valid yaml values")

        case = helm_utils.password_test_cases["test_case_5"]
        logger.info("Validating multimodal pod logs with respect to log level : info")
        assert helm_utils.update_values_yaml(values_yaml_path, case) is True, "Failed to update values.yaml."
        logger.info(
            "Case 5 - Release Name: %s, Chart Path: %s, Namespace: %s, Telegraf Input Plugin mqtt: %s",
            multimodal_release_name,
            multimodal_chart_path,
            multimodal_namespace,
            constants.TELEGRAF_MQTT_PLUGIN,
        )
        assert helm_utils.helm_upgrade(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) is True, "Failed to upgrade Helm release."
        logger.info("Helm is updated for Case 5: INFO log level")

        time.sleep(3)  # Wait for the pods to stabilize
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods for Case 5."
        logger.info("All pods are running")
        assert helm_utils.setup_multimodal_udf_deployment_package(multimodal_chart_path, multimodal_namespace) is True, "Failed to activate UDF deployment package."
        logger.info(f"UDF deployment package is activated and waiting for {wait_time_multi} seconds for pods to stabilize")
        time.sleep(wait_time_multi)  # Wait for the pods to stabilize
        assert helm_utils.verify_ts_logs(multimodal_namespace, "INFO") is True, "Failed to verify pod logs for INFO log level."
        logger.info("Pod logs for INFO log level are verified")
    finally:
        logger.info("Cleaning up multimodal Helm release after TC_011 execution")
        assert helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace) is True, "Failed to uninstall Helm release during cleanup."
        assert helm_utils.check_pods(multimodal_namespace) is True, "Pods are still running after TC_011 cleanup."

def test_system_resources_multimodal_helm(setup_multimodal_helm_environment, request):
    """TC_012: Testing overall system resource usage for multimodal Helm deployment"""
    logger.info("TC_012: Testing overall system resource usage for multimodal Helm deployment")
    logger.info("Waiting %s seconds for multimodal pods to stabilize before collecting resource metrics", wait_time_multi)
    time.sleep(wait_time_multi)
    
    # Validate overall deployment resources  
    resource_results = helm_utils.validate_helm_deployment_resources(
        namespace=namespace_multi,
        cpu_threshold_millicores=2000,  # Allow up to 2 CPU cores (2000 millicores)  
        memory_threshold_gb=8  # Allow up to 8 GB memory
    )

    if resource_results.get("error"):
        logger.warning(
            "Resource metrics unavailable for namespace '%s': %s. Falling back to multimodal component health validation.",
            namespace_multi,
            resource_results["error"],
        )
        component_status = helm_utils.verify_multimodal_core_components(namespace_multi)
        assert component_status["success"], (
            f"Fallback component validation failed. Missing: {component_status.get('missing_components')}, "
            f"Unhealthy: {component_status.get('unhealthy_components')}, Error: {component_status.get('error')}"
        )
        logger.info("Fallback validation succeeded. Core multimodal components are running.")
        return
    
    # Print summary results
    print("\n" + "="*80)
    print("HELM DEPLOYMENT RESOURCE VALIDATION RESULTS")
    print("="*80)
    print(f"Overall Success: {resource_results['success']}")
    print(f"Total Pods Monitored: {resource_results['pod_count']}")
    
    # Handle case where no pods are running (keys might not exist)
    if resource_results.get('total_cpu_millicores') is not None:
        print(f"Total CPU Usage: {resource_results['total_cpu_millicores']:.1f}m")
        print(f"Total Memory Usage: {resource_results['total_memory_mb']:.1f} MB")
        print(f"CPU Threshold: {resource_results['cpu_threshold_millicores']}m")
        print(f"Memory Threshold: {resource_results['memory_threshold_gb']} GB ({resource_results['memory_threshold_gb'] * 1024} MB)")
        
        if resource_results.get('cpu_exceeded'):
            print("CPU usage exceeded threshold")
        else:
            print("CPU usage within acceptable limits")
            
        if resource_results.get('memory_exceeded'):
            print("Memory usage exceeded threshold")
        else:
            print("Memory usage within acceptable limits")
    else:
        print(f"No resource data available: {resource_results.get('error', 'Unknown error')}")
        
    print("="*80)
    
    # Assert the actual test result - only check if pods are actually running
    if resource_results['pod_count'] > 0:
        assert resource_results["success"], f"Helm deployment exceeded resource thresholds: CPU={resource_results['total_cpu_millicores']:.1f}m, Memory={resource_results['total_memory_mb']:.1f}MB"
    else:
        error_message = resource_results.get('error', 'Unknown error')
        pytest.fail(f"Resource metrics unavailable after successful query: {error_message}")
    
    logger.info("✓ Overall system resource usage is within acceptable limits for multimodal Helm deployment")

def test_verify_multimodal_influxdb_data(setup_multimodal_helm_environment, request):
    """TC_013: Verify vision and time series data in InfluxDB for multimodal deployment"""
    logger.info("TC_013: Verifying vision and time series data in InfluxDB for multimodal deployment")
    
    # Wait for data to be generated and ingested
    logger.info("Waiting %s seconds for data pipeline to generate data...", wait_time_multi)
    time.sleep(wait_time_multi)
    
    # Run the common verification helper to keep InfluxDB checks centralized
    multimodal_chart_path = chart_path_multi
    result = helm_utils.verify_multimodal_influxdb_data(multimodal_chart_path, namespace=namespace_multi)

    # Print detailed results for easier triage when running manually
    print("\n" + "="*80)
    print("MULTIMODAL INFLUXDB DATA VERIFICATION RESULTS (TC_013)")
    print("="*80)
    print(f"InfluxDB Pod: {result.get('pod_name', 'N/A')}")
    print("Database: datain")
    print(f"Connectivity: {'✅ Success' if result['connectivity'] else '❌ Failed'}")
    print()
    print(f"Measurements Found: {'✅ Yes' if result['measurements_found'] else '⚠ None'}")
    print(f"Data Records Found: {'✅ Yes' if result['data_found'] else '⚠ None'}")
    print(f"Vision Data Count: {result.get('vision_data_count', 0)}")
    print(f"Sensor Data Count: {result.get('sensor_data_count', 0)}")
    print(f"Total Data Points: {result.get('total_measurements', 0)}")
    print("\nInfluxDB Measurements:")
    print("-" * 40)
    measurements_output = result.get('measurements_output', '')
    if measurements_output:
        print(measurements_output)
    else:
        print("No measurements found")
    print("="*80)

    # Log highlights so CI output stays concise
    if result["success"] and result["connectivity"]:
        logger.info("✅ InfluxDB connectivity and database access verified")
        if result["data_found"]:
            logger.info(f"✅ Found {result.get('total_measurements', 0)} data records in InfluxDB")
        if result.get("vision_data_count", 0) > 0:
            logger.info(f"✅ Vision pipeline data verified: {result['vision_data_count']} records")
        if result.get("sensor_data_count", 0) > 0:
            logger.info(f"✅ Time series data verified: {result['sensor_data_count']} records")
        if not result["data_found"]:
            logger.info("ℹ️ InfluxDB ready but no data generated yet (simulators may need activation)")

    # Assert based on helper output
    assert result["success"], f"InfluxDB verification failed: {result.get('error', 'Unknown error')}"
    logger.info("✅ Multimodal InfluxDB data pipeline verification completed")

def test_seaweed_s3_stored_images_access_multimodal():
    """TC_014: Validate SeaweedFS S3 image storage for multimodal Helm deployment"""
    logger.info("TC_014: Testing S3 stored images infrastructure and SeaweedFS integration for Helm deployment")

    multimodal_release_name = release_name_weld_multi or release_name_multi
    multimodal_chart_path = chart_path_multi
    multimodal_namespace = namespace_multi
    values_yaml_path = os.path.expandvars(os.path.join(multimodal_chart_path, "values.yaml"))

    try:
        # Step 1: Generate helm chart (cd + make gen_helm_charts)
        logger.info("Step 1: Generating helm chart for multimodal")
        assert helm_utils.generate_helm_chart(multimodal_chart_path, constants.MULTIMODAL_SAMPLE_APP) is True, "Failed to generate helm chart."
        logger.info("✓ Helm Chart generated successfully")

        # Step 2: Set environment variables via values.yaml update
        logger.info("Step 2: Setting environment variables via values.yaml")
        case = helm_utils.password_test_cases["test_case_3"]
        assert helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace) is True, "Failed to uninstall existing Helm release."
        assert helm_utils.check_pods(multimodal_namespace) is True, "Pods are still running after cleanup."
        assert helm_utils.update_values_yaml(values_yaml_path, case) is True, "Failed to update values.yaml."
        logger.info("✓ Environment variables set in values.yaml")

        # Step 3: helm install multimodal-weld-defect-detection
        logger.info("Step 3: Installing multimodal Helm deployment")
        assert helm_utils.helm_install(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) is True, "Failed to install multimodal Helm release."
        logger.info("✓ Multimodal Helm deployment installed successfully")

        # Wait for pods to stabilize
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods."
        logger.info("✓ All pods are running")

        # Steps 4-7: kubectl cp models, kubectl cp configs, POST request, GET request
        logger.info("Steps 4-7: Setting up UDF deployment package (kubectl cp + API calls)")
        assert helm_utils.setup_multimodal_udf_deployment_package(multimodal_chart_path, multimodal_namespace) is True, "Failed to activate UDF deployment package."
        logger.info("✓ UDF deployment package activated (Steps 4-7 completed)")

        # Wait for full microservice readiness
        logger.info(f"Waiting {wait_time_multi}s for full microservice readiness...")
        time.sleep(wait_time_multi)
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods after UDF activation."
        assert helm_utils.verify_ts_logs(multimodal_namespace, "DEBUG") is True, "Failed to verify DEBUG logs."
        logger.info("✓ All microservices are active and ready")

        influx_username = case.get("INFLUXDB_USERNAME", "admin")
        influx_password = case.get("INFLUXDB_PASSWORD", "admin123")
        credentials = {
            "INFLUXDB_USERNAME": influx_username,
            "INFLUXDB_PASSWORD": influx_password,
        }

        logger.info("=====================================================")
        logger.info("SETUP COMPLETED - STARTING SEAWEEDFS S3 VALIDATION")
        logger.info("=====================================================")

        s3_wait_time = 90  # Additional 90 seconds for S3 image writes
        logger.info("Waiting %ss for DLStreamer to process video and write images to S3 storage...", s3_wait_time)
        common_utils.wait_for_stability(s3_wait_time)

        logger.info("S3 Step 1: Verifying required pods for S3 image storage")
        pod_check = helm_utils.verify_seaweed_essential_pods(multimodal_namespace)
        if not pod_check["success"]:
            missing = pod_check["missing_pods"]
            assert False, f"Essential pods not running: {missing}"
        logger.info(f"✓ All {pod_check['total_checked']} essential pods are running")
        logger.info("Waiting %ss for pod stabilization...", constants.MULTIMODAL_SEAWEED_WAIT_POD_STABILIZATION)
        common_utils.wait_for_stability(constants.MULTIMODAL_SEAWEED_WAIT_POD_STABILIZATION)

        logger.info("S3 Step 2: Querying InfluxDB for vision detection results")
        influx_check = helm_utils.get_vision_img_handles_from_influxdb_helm(credentials, multimodal_namespace)
        if not influx_check["success"]:
            assert False, f"No img_handle data available from InfluxDB: {influx_check['error']}"
        logger.info(f"✓ Found {influx_check['total_handles']} img_handle values from vision analytics")
        logger.info(f"Selected IMG_HANDLE for testing: {influx_check['selected_handle']}")
        logger.info("Waiting %ss for InfluxDB data consistency...", constants.MULTIMODAL_SEAWEED_WAIT_INFLUX_CONSISTENCY)
        common_utils.wait_for_stability(constants.MULTIMODAL_SEAWEED_WAIT_INFLUX_CONSISTENCY)

        logger.info("S3 Step 3: Testing SeaweedFS S3 API access via curl")
        s3_check = helm_utils.execute_seaweedfs_bucket_query_helm(multimodal_namespace)
        if not s3_check["success"]:
            logger.error(f"Failed to retrieve S3 bucket contents: {s3_check['error']}")
            assert False, f"SeaweedFS S3 API not accessible: {s3_check['error']}"
        logger.info(f"✓ SeaweedFS S3 API accessible - Found {len(s3_check['jpg_files'])} .jpg files out of {s3_check['total_files']} total")
        logger.info(f"Bucket URL used: {s3_check['bucket_url']}")
        logger.info("Waiting %ss for S3 API response processing...", constants.MULTIMODAL_SEAWEED_WAIT_S3_API_RESPONSE)
        common_utils.wait_for_stability(constants.MULTIMODAL_SEAWEED_WAIT_S3_API_RESPONSE)

        logger.info("S3 Step 4: Saving S3 jpg files to list for further processing")
        jpg_files = s3_check["jpg_files"]
        if jpg_files:
            logger.info(f"✓ Saved {len(jpg_files)} .jpg files to list for processing")
            logger.info("Sample .jpg files found:")
            for i, jpg_file in enumerate(jpg_files[:5]):
                logger.info(f"  {i+1}. {jpg_file}")
        else:
            assert False, "No .jpg files found in S3 storage. Since the solution is deployed fresh per test and SeaweedFS has 30min retention, images must be present."
        logger.info("Waiting %ss for S3 storage to be fully populated...", constants.MULTIMODAL_SEAWEED_WAIT_S3_POPULATE)
        common_utils.wait_for_stability(constants.MULTIMODAL_SEAWEED_WAIT_S3_POPULATE)

        logger.info("S3 Step 5: Cross-verifying img_handle values with stored S3 images")
        cross_verify_check = helm_utils.cross_verify_img_handle_with_s3(influx_check["selected_handle"], jpg_files)
        if cross_verify_check["img_handle_found"]:
            logger.info(f"✓ Found {cross_verify_check['match_count']} matching file(s) for img_handle")
            for matched_file in cross_verify_check["matched_files"]:
                logger.info(f"  Matched file: {matched_file}")
        else:
            assert False, f"img_handle '{cross_verify_check['selected_handle']}' not found in S3 image store. Since the solution is deployed fresh per test and SeaweedFS has 30min retention, this handle must be present."
        logger.info("Waiting %ss before file content validation...", constants.MULTIMODAL_SEAWEED_WAIT_FILE_VALIDATION)
        common_utils.wait_for_stability(constants.MULTIMODAL_SEAWEED_WAIT_FILE_VALIDATION)

        logger.info("S3 Step 6: Validating that matched image files have content (not empty)")
        content_validation = helm_utils.validate_s3_images_content_helm(
            multimodal_namespace,
            cross_verify_check["matched_files"],
            max_files_to_check=3,
        )

        if content_validation["success"]:
            logger.info(f"✓ File content validation successful - {content_validation['non_empty_count']}/{content_validation['total_checked']} files have content")
            for file_check in content_validation["checked_files"]:
                if file_check["success"] and not file_check["is_empty"]:
                    logger.info(f"  ✓ {file_check['filename']}: {file_check['size_human']}")
                else:
                    assert False, f"File '{file_check['filename']}' is empty or inaccessible in S3 storage."
        else:
            assert False, f"File content validation failed - {content_validation['empty_count']} empty files found in S3 storage."

        assert pod_check["success"], f"Essential pods not running: {pod_check['missing_pods']}"
        assert s3_check["success"], f"SeaweedFS S3 API not accessible: {s3_check['error']}"

        logger.info("=====================================================")
        logger.info("✓ SEAWEEDFS S3 VALIDATION COMPLETED SUCCESSFULLY")
        logger.info("✓ SeaweedFS S3 storage integration with DLStreamer verified")
        logger.info("=====================================================")

    except Exception as exc:
        logger.error(f"Seaweed test failed: {exc}")
        raise
    finally:
        logger.info("Cleaning up multimodal Helm release after seaweed testing")
        try:
            helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace)
            helm_utils.check_pods(multimodal_namespace)
            logger.info("✓ Cleanup completed successfully")
        except Exception as cleanup_error:
            logger.warning(f"Cleanup error: {cleanup_error}")

def test_vision_metadata_sender_timestamp_multimodal():
    """TC_015: Validate RTP sender timestamp availability in vision measurement for Helm deployment"""
    logger.info("TC_015: Validating RTP sender timestamps in InfluxDB vision measurements for Helm deployment")

    # Use multimodal-specific configuration
    multimodal_release_name = release_name_weld_multi or release_name_multi
    multimodal_chart_path = chart_path_multi
    multimodal_namespace = namespace_multi
    values_yaml_path = os.path.expandvars(os.path.join(multimodal_chart_path, "values.yaml"))

    try:
        # Step 1: Generate helm chart (cd + make gen_helm_charts)
        logger.info("Step 1: Generating helm chart for multimodal")
        assert helm_utils.generate_helm_chart(multimodal_chart_path, constants.MULTIMODAL_SAMPLE_APP) is True, "Failed to generate helm chart."
        logger.info("✓ Helm Chart generated successfully")
        logger.info("Waiting %ss after chart generation...", constants.MULTIMODAL_WAIT_AFTER_CHART_GEN)
        common_utils.wait_for_stability(constants.MULTIMODAL_WAIT_AFTER_CHART_GEN)

        # Step 2: Set environment variables via values.yaml update
        logger.info("Step 2: Setting environment variables via values.yaml")
        case = helm_utils.password_test_cases["test_case_3"]
        assert helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace) is True, "Failed to uninstall existing Helm release."
        assert helm_utils.check_pods(multimodal_namespace) is True, "Pods are still running after cleanup."
        assert helm_utils.update_values_yaml(values_yaml_path, case) is True, "Failed to update values.yaml."
        logger.info("✓ Environment variables set in values.yaml")
        logger.info("Waiting %ss after values.yaml update...", constants.MULTIMODAL_WAIT_AFTER_VALUES_UPDATE)
        common_utils.wait_for_stability(constants.MULTIMODAL_WAIT_AFTER_VALUES_UPDATE)

        # Step 3: helm install multimodal-weld-defect-detection
        logger.info("Step 3: Installing multimodal Helm deployment")
        assert helm_utils.helm_install(multimodal_release_name, multimodal_chart_path, multimodal_namespace, constants.TELEGRAF_MQTT_PLUGIN) is True, "Failed to install multimodal Helm release."
        logger.info("✓ Multimodal Helm deployment installed successfully")
        logger.info("Waiting %ss for initial pod deployment...", constants.MULTIMODAL_WAIT_AFTER_HELM_INSTALL)
        common_utils.wait_for_stability(constants.MULTIMODAL_WAIT_AFTER_HELM_INSTALL)

        # Wait for pods to stabilize
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods."
        logger.info("✓ All pods are running")
        logger.info("Waiting %ss for pods to stabilize...", constants.MULTIMODAL_WAIT_AFTER_PODS_READY)
        common_utils.wait_for_stability(constants.MULTIMODAL_WAIT_AFTER_PODS_READY)

        # Steps 4-7: kubectl cp models, kubectl cp configs, POST request, GET request
        logger.info("Steps 4-7: Setting up UDF deployment package (kubectl cp + API calls)")
        assert helm_utils.setup_multimodal_udf_deployment_package(multimodal_chart_path, multimodal_namespace) is True, "Failed to activate UDF deployment package."
        logger.info("✓ UDF deployment package activated (Steps 4-7 completed)")
        logger.info("Waiting %ss after UDF activation...", constants.MULTIMODAL_WAIT_AFTER_UDF_ACTIVATION)
        common_utils.wait_for_stability(constants.MULTIMODAL_WAIT_AFTER_UDF_ACTIVATION)

        # Wait for full microservice readiness
        logger.info(f"Waiting {wait_time_multi}s for full microservice readiness...")
        time.sleep(wait_time_multi)
        assert helm_utils.verify_pods(multimodal_namespace) is True, "Failed to verify pods after UDF activation."
        assert helm_utils.verify_ts_logs(multimodal_namespace, "DEBUG") is True, "Failed to verify DEBUG logs."
        logger.info("✓ All microservices are active and ready")
        influxdb_username, influxdb_password, _ = helm_utils.fetch_influxdb_credentials(chart_path_multi)
        assert influxdb_username and influxdb_password, "InfluxDB credentials missing from Helm values"

        logger.info("Waiting %ss for vision data to be ingested...", constants.MULTIMODAL_WAIT_FOR_VISION_DATA)
        common_utils.wait_for_stability(constants.MULTIMODAL_WAIT_FOR_VISION_DATA)

        vision_measurement = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP).get(
            "vision_measurement", "vision-weld-classification-results"
        )

        query_result = helm_utils.query_influxdb_measurement_via_kubectl(
            namespace=namespace_multi,
            measurement=vision_measurement,
            username=influxdb_username,
            password=influxdb_password,
            limit=3,
            order_by_time_desc=True,
        )

        assert query_result["success"], f"Failed to query InfluxDB measurement {vision_measurement}: {query_result['error']}"
        assert query_result["records"], f"No vision records returned from measurement {vision_measurement}"

        metadata_values = [record.get("metadata") for record in query_result["records"]]
        timestamps = common_utils.extract_sender_ntp_timestamps(metadata_values)

        assert timestamps, "RTP sender timestamps not found in vision metadata"
        assert all(ts > 0 for ts in timestamps), "Invalid RTP sender timestamp values detected"

        logger.info(
            "✅ RTP sender timestamps detected for %d Helm vision records (pod: %s)",
            len(timestamps),
            query_result.get("pod_name", "unknown"),
        )

    finally:
        # Cleanup: Uninstall Helm release
        logger.info("Cleaning up multimodal Helm deployment...")
        helm_utils.uninstall_helm_charts(multimodal_release_name, multimodal_namespace)
        helm_utils.check_pods(multimodal_namespace)
        logger.info("✓ Cleanup completed")

