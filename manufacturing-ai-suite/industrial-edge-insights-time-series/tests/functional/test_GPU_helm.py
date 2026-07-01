#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""GPU device configuration tests for the Wind Turbine sample app (Helm)."""

import os
import sys
import time
import logging

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
import helm_utils
import docker_utils
import constants

pytest_plugins = ["conftest_helm"]

logger = logging.getLogger(__name__)

(_FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld,
 chart_path, namespace, grafana_url, wait_time, target,
 PROXY_URL) = helm_utils.get_env_values()


def _run_gpu_helm_test(request):
    """Shared body: verify pods, install UDF, settle, POST GPU config."""
    result = helm_utils.verify_pods(namespace)
    logger.info(f"verify_pods result: {result}")
    assert result is True, "Failed to verify pods."
    logger.info("All pods are running")

    actual_chart_path = getattr(request.node, 'actual_chart_path', chart_path)

    result = helm_utils.setup_sample_app_udf_deployment_package(
        actual_chart_path, sample_app=constants.WIND_SAMPLE_APP
    )
    logger.info(f"setup_sample_app_udf_deployment_package result: {result}")
    assert result is True, "Failed to activate UDF deployment package."
    logger.info("UDF deployment package is activated")

    logger.info("Waiting for containers to stabilize and data to be generated...")
    time.sleep(wait_time)

    curl_result = helm_utils.execute_gpu_config_curl_helm(
        device="gpu", namespace=namespace
    )
    logger.info(f"curl_result: {curl_result}")
    assert curl_result, "GPU configuration test via REST API failed"


@pytest.mark.gpu
@pytest.mark.opcua
@pytest.mark.skipif(
    not docker_utils.check_system_gpu_devices(),
    reason="No GPU devices detected on this system",
)
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_gpu_opcua_helm(setup_helm_environment, request, telegraf_input_plugin):
    """TC_GPU_HELM_01: GPU device configuration with OPC-UA (Helm)."""
    logger.info("TC_GPU_HELM_01: GPU device configuration with OPC-UA (Helm)")
    _run_gpu_helm_test(request)


@pytest.mark.gpu
@pytest.mark.mqtt
@pytest.mark.skipif(
    not docker_utils.check_system_gpu_devices(),
    reason="No GPU devices detected on this system",
)
@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_MQTT_PLUGIN])
def test_gpu_mqtt_helm(setup_helm_environment, request, telegraf_input_plugin):
    """TC_GPU_HELM_02: GPU device configuration with MQTT (Helm)."""
    logger.info("TC_GPU_HELM_02: GPU device configuration with MQTT (Helm)")
    _run_gpu_helm_test(request)
