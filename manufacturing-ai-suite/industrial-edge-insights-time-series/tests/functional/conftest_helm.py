#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import pytest
import logging
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import helm_utils
from utils import constants
import time

# Set up logger
logger = logging.getLogger(__name__)

# Retrieve environment variables
FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL = helm_utils.get_env_values()
(_functional_multi_path,
    release_name_multi,
    release_name_weld_multi,
    chart_path_multi,
    namespace_multi,
    _grafana_url_multi,
    _wait_time_multi,
    _target_multi,
    _proxy_url_multi,
) = helm_utils.get_multimodal_env_values()

@pytest.fixture(scope="function")
def setup_helm_environment(request):
    """Setup Helm environment before running tests."""
    logger.debug("Checking if Helm release exists...")
    assert helm_utils.uninstall_helm_charts(release_name, namespace) == True, "Failed to uninstall Helm release if exists."
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release if exists."
    case = helm_utils.password_test_cases["test_case_4"]
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."

    # Get telegraf_input_plugin from test parameters if available
    telegraf_input_plugin = getattr(request, 'param', None) or "opcua"  # default to opcua
    if hasattr(request.node, 'callspec') and 'telegraf_input_plugin' in request.node.callspec.params:
        telegraf_input_plugin = request.node.callspec.params['telegraf_input_plugin']

    # Determine SAMPLE_APP based on release name to match UDF package directory
    sample_app = "wind-turbine-anomaly-detection" if "wind" in release_name.lower() else "weld-defect-detection"

    logger.debug(
        f"Installing Helm release... "
        f"Release Name: {release_name}, "
        f"Chart Path: {chart_path}, "
        f"Namespace: {namespace}, "
        f"Telegraf Input Plugin: {telegraf_input_plugin}"
    )
    assert helm_utils.helm_install(release_name, chart_path, namespace, telegraf_input_plugin, sample_app=sample_app) == True, "Failed to install Helm release."
    
    # Wait for pods to be ready before yielding to tests
    logger.debug(f"Waiting for pods to be ready in namespace '{namespace}'...")
    assert helm_utils.verify_pods(namespace, timeout=constants.PODS_VERIFY_TIMEOUT) == True, "Failed to verify pods are running after installation."
    
    yield
    # Stop helm releases
    assert helm_utils.uninstall_helm_charts(release_name, namespace) == True, "Failed to uninstall Helm release if exists."
    cleanup_result = helm_utils.check_pods(namespace, timeout=constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT)
    if not cleanup_result:
        logger.warning(f"Pods still running after {constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT}s cleanup timeout - continuing anyway for CI/CD compatibility")

@pytest.fixture(scope="function")
def setup_helm_weld_environment(request):
    """Setup Helm environment before running tests."""
    logger.debug("Checking if Helm release exists...")
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release if exists."
    assert helm_utils.uninstall_helm_charts(release_name, namespace) == True, "Failed to uninstall Helm release if exists."

    case = helm_utils.password_test_cases["test_case_4"]
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."

    # Get telegraf_input_plugin from test parameters if available
    telegraf_input_plugin = getattr(request, 'param', None) or "opcua"  # default to opcua
    if hasattr(request.node, 'callspec') and 'telegraf_input_plugin' in request.node.callspec.params:
        telegraf_input_plugin = request.node.callspec.params['telegraf_input_plugin']

    # Determine SAMPLE_APP based on release name to match UDF package directory
    sample_app = "wind-turbine-anomaly-detection" if "wind" in release_name_weld.lower() else "weld-defect-detection"

    logger.debug(
        f"Installing Helm release... "
        f"Release Name: {release_name_weld}, "
        f"Chart Path: {chart_path}, "
        f"Namespace: {namespace}, "
        f"Telegraf Input Plugin: {telegraf_input_plugin}"
    )
    assert helm_utils.helm_install(release_name_weld, chart_path, namespace, telegraf_input_plugin, sample_app=sample_app) == True, "Failed to install Helm release."
    
    # Wait for pods to be ready before yielding to tests
    logger.debug(f"Waiting for pods to be ready in namespace '{namespace}'...")
    assert helm_utils.verify_pods(namespace, timeout=constants.PODS_VERIFY_TIMEOUT) == True, "Failed to verify pods are running after installation."
    
    yield
    # Stop helm releases
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release if exists."
    cleanup_result = helm_utils.check_pods(namespace, timeout=constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT)
    if not cleanup_result:
        logger.warning(f"Pods still running after {constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT}s cleanup timeout - continuing anyway for CI/CD compatibility")

@pytest.fixture(scope="function")
def setup_multimodal_helm_environment():
    """Install and tear down the multimodal Helm chart for tests that require it."""
    logger.debug("Ensuring multimodal Helm release is not present before installation...")
    assert helm_utils.uninstall_helm_charts(release_name_multi, namespace_multi) == True, "Failed to uninstall multimodal Helm release if exists."

    case = helm_utils.password_test_cases["test_case_3"]
    values_yaml_path = os.path.expandvars(chart_path_multi + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update multimodal values.yaml."

    logger.debug(
        f"Installing multimodal Helm release... Release Name: {release_name_multi}, Chart Path: {chart_path_multi}, Namespace: {namespace_multi}"
    )
    assert helm_utils.helm_install(release_name_multi, chart_path_multi, namespace_multi, constants.TELEGRAF_MQTT_PLUGIN) == True, "Failed to install multimodal Helm release."
    time.sleep(3)
    yield
    assert helm_utils.uninstall_helm_charts(release_name_multi, namespace_multi) == True, "Failed to uninstall multimodal Helm release if exists."
    cleanup_result = helm_utils.check_pods(namespace_multi, timeout=constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT_MULTI)
    if not cleanup_result:
        logger.warning(f"Pods still running after {constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT_MULTI}s cleanup timeout - continuing anyway for CI/CD compatibility")