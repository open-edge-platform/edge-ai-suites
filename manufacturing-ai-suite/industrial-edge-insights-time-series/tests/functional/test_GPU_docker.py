#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""GPU device configuration tests for the Wind Turbine sample app (Docker)."""

import os
import sys
import time
import logging

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import docker_utils
from utils import constants

pytest_plugins = ["conftest_docker"]

logger = logging.getLogger(__name__)


def _run_gpu_config_test(context, ingestion_type):
    """Shared body: deploy, settle, POST GPU config, wait, verify GPU log line."""
    if ingestion_type == "mqtt":
        context["deploy_mqtt"](app=constants.WIND_SAMPLE_APP)
    else:
        context["deploy_opcua"](app=constants.WIND_SAMPLE_APP)
    logger.info(f"{ingestion_type} deployment succeeded")

    logger.info("Polling until service is ready...")
    docker_utils.wait_until_service_ready(
        timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT
    )

    logger.info(f"Settle period {constants.WIND_TURBINE_POST_DEPLOY_SETTLE}s before GPU POST...")
    time.sleep(constants.WIND_TURBINE_POST_DEPLOY_SETTLE)

    curl_result = docker_utils.execute_gpu_config_curl(device="gpu")
    logger.info(f"GPU configuration curl result: {curl_result}")
    assert curl_result, "GPU configuration test via REST API failed"

    logger.info("Waiting for service to restart and apply GPU configuration...")
    docker_utils.wait_until_service_ready(
        timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT, accept_503=False
    )
    logger.info(f"Grace period {constants.WIND_TURBINE_GPU_RESTART_GRACE}s for kapacitor UDF to bind GPU...")
    time.sleep(constants.WIND_TURBINE_GPU_RESTART_GRACE)

    logger.info("Verifying if logs contain GPU keywords...")
    container_name = constants.CONTAINERS["time_series_analytics"]["name"]
    gpu_result = docker_utils.check_log_gpu(
        container_name,
        timeout=constants.WIND_TURBINE_GPU_LOG_TIMEOUT,
        interval=10,
    )
    logger.info(f"GPU log check result: {gpu_result}")
    assert gpu_result is True, "GPU keywords not found in logs"


@pytest.mark.gpu
@pytest.mark.mqtt
@pytest.mark.skipif(
    not docker_utils.check_system_gpu_devices(),
    reason="No GPU devices detected on this system",
)
def test_gpu_mqtt(setup_wind_turbine_environment):
    """TC_GPU_01: GPU device configuration with MQTT ingestion (Docker)."""
    logger.info("TC_GPU_01: GPU device configuration with MQTT ingestion (Docker)")
    _run_gpu_config_test(setup_wind_turbine_environment, "mqtt")


@pytest.mark.gpu
@pytest.mark.opcua
@pytest.mark.skipif(
    not docker_utils.check_system_gpu_devices(),
    reason="No GPU devices detected on this system",
)
def test_gpu_opcua(setup_wind_turbine_environment):
    """TC_GPU_02: GPU device configuration with OPC-UA ingestion (Docker)."""
    logger.info("TC_GPU_02: GPU device configuration with OPC-UA ingestion (Docker)")
    _run_gpu_config_test(setup_wind_turbine_environment, "opcua")
