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

    # Wait for pods from the previous release to fully terminate before installing
    logger.debug(f"Waiting for pods in namespace '{namespace}' to terminate...")
    cleanup_ok = helm_utils.check_pods(namespace, timeout=constants.POD_TERMINATION_TIMEOUT)
    if not cleanup_ok:
        logger.warning("Some pods are still present after the standard wait. Triggering forced cleanup before installation.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_pods(namespace, timeout=constants.POD_CLEANUP_TIMEOUT) == True, "Failed to clean up lingering pods before Helm install."

    # Wait for services (especially NodePort) to be fully deleted to avoid port allocation conflicts
    logger.debug(f"Waiting for services in namespace '{namespace}' to be deleted...")
    services_cleanup_ok = helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT)
    if not services_cleanup_ok:
        logger.warning("Some services are still present after the standard wait. Triggering forced cleanup before installation.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT) == True, "Failed to clean up lingering services before Helm install."

    case = helm_utils.password_test_cases["test_case_4"]
    # Resolve relative path from pytest.ini to absolute path
    values_yaml_path = os.path.abspath(os.path.expandvars(os.path.join(os.path.dirname(__file__), chart_path, 'values.yaml')))
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
    install_result = helm_utils.helm_install(release_name, chart_path, namespace, telegraf_input_plugin, sample_app=sample_app)
    if not install_result:
        logger.error(f"Helm install failed for release '{release_name}'")
        helm_utils.dump_pod_diagnostics(namespace)
        assert False, f"Failed to install Helm release '{release_name}'. Check logs for details."
    
    # Wait for pods to be ready before yielding to tests
    logger.debug(f"Waiting for pods to be ready in namespace '{namespace}'...")
    pods_ready = helm_utils.verify_pods(namespace, timeout=constants.PODS_VERIFY_TIMEOUT)
    if not pods_ready:
        logger.error(f"Pods failed to become ready in namespace '{namespace}' within {constants.PODS_VERIFY_TIMEOUT}s")
        helm_utils.dump_pod_diagnostics(namespace)
        assert False, f"Failed to verify pods are running after installation in namespace '{namespace}'. Check logs for diagnostics."
    
    yield
    # Stop helm releases
    assert helm_utils.uninstall_helm_charts(release_name, namespace) == True, "Failed to uninstall Helm release if exists."
    cleanup_result = helm_utils.check_pods(namespace, timeout=constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT)
    if not cleanup_result:
        logger.warning("Pods still present after standard cleanup wait. Triggering forced cleanup before failing.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_pods(namespace, timeout=constants.POD_CLEANUP_TIMEOUT) == True, "Pods are still running after teardown cleanup."

    services_cleanup_result = helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT)
    if not services_cleanup_result:
        logger.warning("Services still present after teardown wait. Triggering forced cleanup before failing.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT) == True, "Services are still present after teardown cleanup."

@pytest.fixture(scope="function")
def setup_helm_weld_environment(request):
    """Setup Helm environment before running tests."""
    logger.debug("Checking if Helm release exists...")
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release if exists."
    assert helm_utils.uninstall_helm_charts(release_name, namespace) == True, "Failed to uninstall Helm release if exists."

    # Wait for pods from the previous release to fully terminate before installing
    logger.debug(f"Waiting for pods in namespace '{namespace}' to terminate...")
    cleanup_ok = helm_utils.check_pods(namespace, timeout=constants.POD_TERMINATION_TIMEOUT)
    if not cleanup_ok:
        logger.warning("Some pods are still present after the standard wait. Triggering forced cleanup before installation.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_pods(namespace, timeout=constants.POD_CLEANUP_TIMEOUT) == True, "Failed to clean up lingering pods before Helm install."

    # Wait for services (especially NodePort) to be fully deleted to avoid port allocation conflicts
    logger.debug(f"Waiting for services in namespace '{namespace}' to be deleted...")
    services_cleanup_ok = helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT)
    if not services_cleanup_ok:
        logger.warning("Some services are still present after the standard wait. Triggering forced cleanup before installation.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT) == True, "Failed to clean up lingering services before Helm install."

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
    install_result = helm_utils.helm_install(release_name_weld, chart_path, namespace, telegraf_input_plugin, sample_app=sample_app)
    if not install_result:
        logger.error(f"Helm install failed for release '{release_name_weld}'")
        helm_utils.dump_pod_diagnostics(namespace)
        assert False, f"Failed to install Helm release '{release_name_weld}'. Check logs for details."
    
    # Wait for pods to be ready before yielding to tests
    logger.debug(f"Waiting for pods to be ready in namespace '{namespace}'...")
    pods_ready = helm_utils.verify_pods(namespace, timeout=constants.PODS_VERIFY_TIMEOUT)
    if not pods_ready:
        logger.error(f"Pods failed to become ready in namespace '{namespace}' within {constants.PODS_VERIFY_TIMEOUT}s")
        helm_utils.dump_pod_diagnostics(namespace)
        assert False, f"Failed to verify pods are running after installation in namespace '{namespace}'. Check logs for diagnostics."
    
    yield
    # Stop helm releases
    assert helm_utils.uninstall_helm_charts(release_name_weld, namespace) == True, "Failed to uninstall Helm release if exists."
    cleanup_result = helm_utils.check_pods(namespace, timeout=constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT)
    if not cleanup_result:
        logger.warning("Pods still present after standard cleanup wait. Triggering forced cleanup before failing.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_pods(namespace, timeout=constants.POD_CLEANUP_TIMEOUT) == True, "Pods are still running after teardown cleanup."

    services_cleanup_result = helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT)
    if not services_cleanup_result:
        logger.warning("Services still present after teardown wait. Triggering forced cleanup before failing.")
        helm_utils.force_cleanup_namespace(namespace)
        assert helm_utils.check_services(namespace, timeout=constants.SERVICE_TERMINATION_TIMEOUT) == True, "Services are still present after teardown cleanup."

@pytest.fixture(scope="function")
def setup_multimodal_helm_environment():
    """Install and tear down the multimodal Helm chart for tests that require it."""
    logger.debug("Ensuring multimodal Helm release is not present before installation...")
    assert helm_utils.uninstall_helm_charts(release_name_multi, namespace_multi) == True, "Failed to uninstall multimodal Helm release if exists."

    # Wait for pods from previous release to fully terminate before installing
    logger.debug(f"Waiting for pods in namespace '{namespace_multi}' to terminate...")
    cleanup_ok = helm_utils.check_pods(namespace_multi, timeout=constants.POD_TERMINATION_TIMEOUT)
    if not cleanup_ok:
        logger.warning("Some pods are still present after the standard wait. Triggering forced cleanup before installation.")
        helm_utils.force_cleanup_namespace(namespace_multi)
        assert helm_utils.check_pods(namespace_multi, timeout=constants.POD_CLEANUP_TIMEOUT) == True, "Failed to clean up lingering pods before Helm install."

    # Wait for services (especially NodePort) to be fully deleted to avoid port allocation conflicts
    logger.debug(f"Waiting for services in namespace '{namespace_multi}' to be deleted...")
    services_cleanup_ok = helm_utils.check_services(namespace_multi, timeout=constants.SERVICE_TERMINATION_TIMEOUT)
    if not services_cleanup_ok:
        logger.warning("Some services are still present after the standard wait. Triggering forced cleanup before installation.")
        helm_utils.force_cleanup_namespace(namespace_multi)
        assert helm_utils.check_services(namespace_multi, timeout=constants.SERVICE_TERMINATION_TIMEOUT) == True, "Failed to clean up lingering services before Helm install."

    case = helm_utils.password_test_cases["test_case_3"]
    values_yaml_path = os.path.expandvars(chart_path_multi + '/values.yaml')
    assert helm_utils.update_values_yaml(values_yaml_path, case) == True, "Failed to update multimodal values.yaml."

    logger.debug(
        f"Installing multimodal Helm release... Release Name: {release_name_multi}, Chart Path: {chart_path_multi}, Namespace: {namespace_multi}"
    )
    install_result = helm_utils.helm_install(release_name_multi, chart_path_multi, namespace_multi, constants.TELEGRAF_MQTT_PLUGIN)
    if not install_result:
        logger.error(f"Helm install failed for multimodal release '{release_name_multi}'")
        helm_utils.dump_pod_diagnostics(namespace_multi)
        assert False, f"Failed to install multimodal Helm release '{release_name_multi}'. Check logs for details."
    
    # Wait for pods to be ready
    logger.debug(f"Waiting for pods to be ready in namespace '{namespace_multi}'...")
    time.sleep(3)  # Initial delay for k8s to register pods
    pods_ready = helm_utils.verify_pods(namespace_multi, timeout=constants.PODS_VERIFY_TIMEOUT)
    if not pods_ready:
        logger.error(f"Pods failed to become ready in namespace '{namespace_multi}' within {constants.PODS_VERIFY_TIMEOUT}s")
        helm_utils.dump_pod_diagnostics(namespace_multi)
        assert False, f"Failed to verify multimodal pods are running after installation. Check logs for diagnostics."
    
    yield
    assert helm_utils.uninstall_helm_charts(release_name_multi, namespace_multi) == True, "Failed to uninstall multimodal Helm release if exists."
    cleanup_result = helm_utils.check_pods(namespace_multi, timeout=constants.PODS_HEALTHY_CHECK_STATUS_TIMEOUT_MULTI)
    if not cleanup_result:
        logger.warning("Pods still present after standard cleanup wait. Triggering forced cleanup before failing.")
        helm_utils.force_cleanup_namespace(namespace_multi)
        assert helm_utils.check_pods(namespace_multi, timeout=constants.POD_CLEANUP_TIMEOUT) == True, "Pods are still running after teardown cleanup."

    services_cleanup_result = helm_utils.check_services(namespace_multi, timeout=constants.SERVICE_TERMINATION_TIMEOUT)
    if not services_cleanup_result:
        logger.warning("Services still present after teardown wait. Triggering forced cleanup before failing.")
        helm_utils.force_cleanup_namespace(namespace_multi)
        assert helm_utils.check_services(namespace_multi, timeout=constants.SERVICE_TERMINATION_TIMEOUT) == True, "Services are still present after teardown cleanup."