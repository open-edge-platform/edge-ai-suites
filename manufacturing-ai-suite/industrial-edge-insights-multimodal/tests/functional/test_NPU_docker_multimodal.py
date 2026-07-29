#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""NPU device configuration tests for the Multimodal Weld Defect Detection sample app (Docker).

Sequence (chronological):
    1. Deploy multimodal stack (`make up`).
    2. POST NPU UDF config to Time Series Analytics microservice
       (`docker_utils.execute_multimodal_gpu_config_curl`).
    3. POST NPU model device to DL Streamer Pipeline Server pipeline
       (`docker_utils.execute_dlstreamer_pipeline_activation`).
    4. Verify multimodal data in InfluxDB
       (`docker_utils.execute_influxdb_commands_multimodal`).
"""

import os
import sys
import json
import time
import logging

import pytest

# Add parent directory to path for utils imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import docker_utils
from utils import constants

pytest_plugins = ["conftest_docker"]

logger = logging.getLogger(__name__)

MULTIMODAL_TSA_CONFIG_PATH = os.path.join(
    constants.MULTIMODAL_APPLICATION_DIRECTORY,
    "configs",
    "time-series-analytics-microservice",
    "config.json",
)


def _load_multimodal_tsa_config():
    """Load the multimodal Time Series Analytics microservice config.json."""
    with open(MULTIMODAL_TSA_CONFIG_PATH, "r") as f:
        return json.load(f)


def _has_npu_devices():
    """Best-effort NPU detection, supports branches without explicit NPU checker."""
    checker = getattr(docker_utils, "check_system_npu_devices", None)
    if callable(checker):
        return checker()

    logger.warning("docker_utils.check_system_npu_devices() not found; skipping NPU pre-check")
    return True


def _run_multimodal_npu_flow(context, device):
    """Execute the four multimodal GPU/NPU steps sequentially."""
    device_upper = device.upper()

    # Step 1: Deploy the multimodal stack
    logger.info("Step 1: Deploying multimodal stack via 'make up'")
    context["deploy_multimodal"]()

    # Allow containers to stabilize and begin processing
    logger.info(
        f"Settle period {constants.TEST_DATA_PROCESSING_DELAY}s before "
        f"posting {device_upper} configurations..."
    )
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)

    # Step 2: Configure Time Series Analytics UDF for NPU
    logger.info(f"Step 2: Posting Time Series Analytics UDF config with device='{device_upper}'")
    tsa_config = _load_multimodal_tsa_config()
    tsa_result = docker_utils.execute_multimodal_gpu_config_curl(tsa_config, device=device_upper)
    logger.info(f"TSA {device_upper} config result: {tsa_result}")
    assert tsa_result, f"Failed to post Time Series Analytics {device_upper} configuration"  # nosec B101

    # Step 3: Activate DL Streamer Pipeline Server pipeline on GPU/NPU
    logger.info(f"Step 3: Activating DL Streamer pipeline with device='{device_upper}'")
    dlsps_result = docker_utils.execute_dlstreamer_pipeline_activation(device=device_upper)
    logger.info(f"DL Streamer pipeline activation result: {dlsps_result}")
    assert dlsps_result, f"Failed to activate DL Streamer pipeline on {device_upper}"  # nosec B101

    # Allow processed data (TSA + DLSPS) to land in InfluxDB
    logger.info(
        f"Waiting {constants.TEST_DATA_PROCESSING_DELAY}s for {device_upper} "
        f"inference output to be written to InfluxDB..."
    )
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)

    # Step 4: Verify InfluxDB contains both analytics and vision multimodal measurements
    logger.info("Step 4: Verifying multimodal measurements in InfluxDB")
    
    # Get measurement names from constants
    sensor_measurement = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP).get("analytics_topic")
    vision_measurement = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP).get("vision_measurement")
    
    influx_response = docker_utils.execute_influxdb_commands_multimodal()
    logger.info(f"Multimodal InfluxDB response (truncated): {str(influx_response)[:500]}")
    assert influx_response, "InfluxDB query for multimodal measurements returned no response"  # nosec B101
    assert sensor_measurement in influx_response, (  # nosec B101
        f"Time Series Analytics measurement '{sensor_measurement}' missing from InfluxDB"
    )
    assert vision_measurement in influx_response, (  # nosec B101
        f"DL Streamer measurement '{vision_measurement}' missing from InfluxDB"
    )


@pytest.mark.npu
@pytest.mark.skipif(
    not _has_npu_devices(),
    reason="No NPU devices detected on this system",
)
def test_npu_multimodal(setup_multimodal_environment):
    """TC_NPU_MM_01: Multimodal NPU inference flow (TSA UDF + DLSPS pipeline) end-to-end."""
    logger.info("TC_NPU_MM_01: Multimodal NPU inference flow (Docker)")
    _run_multimodal_npu_flow(setup_multimodal_environment, device="NPU")
