#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""GPU device configuration tests for the Multimodal Weld Defect Detection sample app (Helm).

Sequence (chronological, mirrors the documented user-guide flow):
    1. Copy DL Streamer models into the dlstreamer-pipeline-server pod
       (`helm_utils.copy_dlstreamer_models_to_pod`).
    2. Build & upload the Time Series Analytics UDF tar package via
       ``POST /ts-api/udfs/package`` (`helm_utils.upload_udf_tar_package`).
    3. Activate the Time Series Analytics UDF on the chosen device via
       ``POST /ts-api/config`` (`helm_utils.activate_multimodal_tsa_udf_config`).
    4. Activate the DL Streamer pipeline on the chosen device via
       ``POST /pipelines/user_defined_pipelines/<pipeline_name>``
       (`helm_utils.activate_multimodal_dlstreamer_pipeline`).
    5. Verify InfluxDB contains time-series analytics sensor measurements
       (`helm_utils.verify_multimodal_influxdb_data`).
"""

import os
import sys
import time
import logging

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../utils")))
import helm_utils
import docker_utils
import constants

pytest_plugins = ["conftest_helm"]

logger = logging.getLogger(__name__)

(
    _FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE,
    release_name_multi,
    release_name_weld_multi,
    chart_path_multi,
    namespace_multi,
    grafana_url_multi,
    wait_time_multi,
    target,
    PROXY_URL,
) = helm_utils.get_multimodal_env_values()


def _run_multimodal_helm_gpu_flow(device):
    """Execute the five documented multimodal helm steps sequentially."""
    device_upper = device.upper()

    # Pre-check: pods are healthy before activation
    pods_result = helm_utils.verify_pods(namespace_multi)
    logger.info(f"verify_pods result: {pods_result}")
    assert pods_result is True, "Failed to verify pods before UDF activation"  # nosec B101

    # Step 1: Copy DL Streamer models into the pod
    logger.info("Step 1: Copying DL Streamer models to pod")
    step1 = helm_utils.copy_dlstreamer_models_to_pod(chart_path_multi, namespace_multi)
    logger.info(f"copy_dlstreamer_models_to_pod result: {step1}")
    assert step1, "Failed to copy DL Streamer models to pod"  # nosec B101

    # Step 2: Build and upload the TSA UDF tar package
    logger.info("Step 2: Uploading multimodal UDF tar package via /ts-api/udfs/package")
    step2 = helm_utils.upload_udf_tar_package(
        chart_path_multi, sample_app=constants.MULTIMODAL_SAMPLE_APP
    )
    logger.info(f"upload_udf_tar_package result: {step2}")
    assert step2, "Failed to upload multimodal UDF tar package"  # nosec B101

    # Step 3: Activate the TSA UDF config on chosen device
    logger.info(f"Step 3: Activating Time Series Analytics UDF (device='{device_upper}')")
    step3 = helm_utils.activate_multimodal_tsa_udf_config(
        namespace_multi, device_value=device_upper
    )
    logger.info(f"activate_multimodal_tsa_udf_config result: {step3}")
    assert step3, f"Failed to activate Time Series Analytics UDF on {device_upper}"  # nosec B101

    # Step 4: Activate DL Streamer pipeline on chosen device
    logger.info(f"Step 4: Activating DL Streamer pipeline (device='{device_upper}')")
    step4 = helm_utils.activate_multimodal_dlstreamer_pipeline(
        namespace_multi, device_value=device_upper
    )
    logger.info(f"activate_multimodal_dlstreamer_pipeline result: {step4}")
    assert step4, f"Failed to activate DL Streamer pipeline on {device_upper}"  # nosec B101

    # Step 5: Verify InfluxDB contains sensor data from Time Series Analytics
    logger.info("Step 5: Verifying sensor measurements in InfluxDB")
    logger.info(
        f"Waiting {constants.TEST_DATA_PROCESSING_DELAY}s for {device_upper} "
        f"inference output to be written to InfluxDB..."
    )
    time.sleep(constants.TEST_DATA_PROCESSING_DELAY)
    
    influx_result = helm_utils.verify_multimodal_influxdb_data(chart_path_multi, namespace_multi)
    assert influx_result and influx_result.get("success"), (  # nosec B101
        f"InfluxDB verification failed: {influx_result.get('error') if influx_result else 'No result returned'}"
    )
    assert influx_result.get("sensor_data_count", 0) > 0, (  # nosec B101
        "Time Series Analytics measurement data missing from InfluxDB"
    )
    logger.info(
        f"✓ Successfully verified InfluxDB sensor data (sensor={influx_result['sensor_data_count']})"
    )


@pytest.mark.gpu
@pytest.mark.skipif(
    not docker_utils.check_system_gpu_devices(),
    reason="No GPU devices detected on this system",
)
def test_gpu_multimodal_helm(setup_multimodal_helm_environment, request):
    """TC_GPU_MM_HELM_01: Multimodal GPU inference flow (5 documented steps) end-to-end."""
    logger.info("TC_GPU_MM_HELM_01: Multimodal GPU inference flow (Helm)")
    _run_multimodal_helm_gpu_flow(device="GPU")
