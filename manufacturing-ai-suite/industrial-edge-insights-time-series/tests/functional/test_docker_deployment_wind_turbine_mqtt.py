#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""
MQTT-only tests for the Wind Turbine Anomaly Detection sample app.

Split out of ``test_docker_deployment_wind_turbine.py`` so MQTT cases can be
exercised independently in CI / local runs.  The OPC-UA cases live in
``test_docker_deployment_wind_turbine_opcua.py`` and KPI cases in
``test_docker_deployment_wind_turbine_kpi.py``.
"""

import os
import sys
import pytest
import time
import logging

# Add parent directory to path for utils imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import docker_utils
from utils import constants

# Import the fixture directly from conftest_docker.py
pytest_plugins = ["conftest_docker"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Container list used by wait_until_containers_up in multi-stream tests
# ---------------------------------------------------------------------------
_WIND_MQTT_CONTAINERS = [
    constants.CONTAINERS["influxdb"]["name"],
    constants.CONTAINERS["telegraf"]["name"],
    constants.CONTAINERS["time_series_analytics"]["name"],
    constants.CONTAINERS["mqtt_broker"]["name"],
    constants.CONTAINERS["mqtt_publisher"]["name"],
]


# ---------------------------------------------------------------------------
# Environment / .env validation tests (protocol-agnostic, kept with MQTT file)
# ---------------------------------------------------------------------------
def test_blank_values():
    logger.info("TC_001: Testing blank values, checking make check env variables with blank values in .env file")
    case = docker_utils.generate_test_credentials(case_type="blank")
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    docker_utils.update_env_file(env_file_path, case)
    logger.info("Verifying that make check env variables fails with blank values in .env file")
    result = docker_utils.invoke_make_check_env_variables()
    logger.info(f"make check env variables returned: {result}, expected: False")
    assert result == False


def test_invalid_values():
    logger.info("TC_002: Testing invalid values, checking make check env variables with invalid values in .env file")
    case = docker_utils.generate_test_credentials(case_type="invalid")
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    docker_utils.update_env_file(env_file_path, case)
    logger.info("Verifying that make check env variables fails with invalid values in .env file")
    result = docker_utils.invoke_make_check_env_variables()
    logger.info(f"make check env variables returned: {result}, expected: False")
    assert result == False


def test_valid_values():
    logger.info("TC_003: Verifying make check_env_variables with all valid values in .env file")
    case = docker_utils.generate_test_credentials(case_type="valid")
    env_file_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    docker_utils.update_env_file(env_file_path, case)
    logger.info("Verifying that make check env variables succeeds with valid values in .env file")
    result = docker_utils.invoke_make_check_env_variables()
    logger.info(f"make check env variables returned: {result}, expected: True")
    assert result == True


# ---------------------------------------------------------------------------
# MQTT-focused tests
# ---------------------------------------------------------------------------
def test_make_up_mqtt(setup_wind_turbine_environment):
    """TC_005: Testing make up MQTT and make down with valid values in .env file"""
    logger.info("TC_005: Testing make up_mqtt_ingestion app=\"wind-turbine-anomaly-detection\" command execution")
    context = setup_wind_turbine_environment

    # Use enhanced deploy_mqtt function with app parameter
    deploy_result = context["deploy_mqtt"](app=constants.WIND_SAMPLE_APP)
    logger.info(f"MQTT deploy result: {deploy_result}")
    assert deploy_result == True

    # Verify containers are running
    containers = docker_utils.get_the_deployed_containers()
    logger.info(f"Deployed containers: {containers}")
    logger.info(f"Containers found: {len(containers) if containers else 0}")
    assert containers, "No containers found after MQTT deployment"
    # No manual cleanup needed - handled by fixture


def test_multiple_runs_mqtt(setup_wind_turbine_environment):
    """
    TC_006: Testing multiple runs of make up MQTT
    """
    logger.info("TC_006: Testing multiple runs of make up MQTT (refactored)")

    context = setup_wind_turbine_environment
    for i in range(3):
        logger.info(f"Cycle {i+1}:")
        deploy_result = context["deploy_mqtt"](app=constants.WIND_SAMPLE_APP)
        logger.info(f"MQTT deploy result in cycle {i+1}: {deploy_result}")
        assert deploy_result == True
        docker_utils.wait_for_stability(constants.WIND_TURBINE_CYCLE_GAP_TIME)
        containers = docker_utils.get_the_deployed_containers()
        logger.info(f"Containers found in cycle {i+1}: {len(containers) if containers else 0}")
        assert containers, "No containers found after MQTT deployment"
        # Cleanup between iterations (except last one which is handled by fixture)
        if i < 2:
            make_down_result = docker_utils.invoke_make_down()
            logger.info(f"make down result in cycle {i+1}: {make_down_result}")
            assert make_down_result == True


def test_switch_opcua_to_mqtt_ingestion(setup_wind_turbine_environment):
    """TC_009: Testing switch from OPCUA back to MQTT ingestion"""
    logger.info("TC_009: Testing switch from OPCUA back to MQTT ingestion")
    context = setup_wind_turbine_environment
    context["deploy_opcua"]()
    docker_utils.wait_for_stability(constants.WIND_TURBINE_CYCLE_GAP_TIME)
    logger.info("Verifying switch from opcua to mqtt succeeded")
    switch_result = docker_utils.invoke_switch_opcua_mqtt()
    logger.info(f"Switch OPCUA to MQTT result: {switch_result}")
    assert switch_result == True
    # Cleanup handled by fixture


def test_stability_with_mqtt_ingestion(setup_wind_turbine_environment):
    """TC_010: Testing stability of MQTT ingestion"""
    logger.info("TC_010: Testing stability of MQTT ingestion")
    context = setup_wind_turbine_environment
    context["deploy_mqtt"]()

    # Poll until service is ready instead of sleeping blindly
    docker_utils.wait_until_service_ready(timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT)

    # Check container status
    container_status = docker_utils.restart_containers_and_check_status(ingestion_type="mqtt")
    logger.info(f"Container Status: {container_status}")

    logger.info("Verifying all containers are running as expected")
    failed = {k: v for k, v in container_status.items() if v != "Up"}
    if failed:
        logger.info(f"Containers not running: {failed}")
    assert all(status == "Up" for status in container_status.values()), f"Not all containers are running. Failed: {failed}"

    # Cleanup handled by fixture


def test_mqtt_alerts(setup_wind_turbine_environment):
    """TC_013: Testing MQTT alerts functionality.

    The underlying ``validate_mqtt_alert_system`` helper performs 2 sequential
    steps (config POST → log pattern search).  When the helper returns False
    the only signal is the assertion message, which makes triage hard.

    This test mirrors the structure of ``test_opcua_alerts``: explicit
    pre-checks and on-failure log dumps so CI output pinpoints which
    subsystem (deployment / TSAM / MQTT broker / MQTT publisher / Telegraf /
    log pattern) caused the failure without needing to re-run locally.
    """
    import subprocess as _subprocess

    logger.info("TC_013: Testing MQTT alerts functionality")
    context = setup_wind_turbine_environment

    # ------------------------------------------------------------------
    # Phase 1: Deploy MQTT stack
    # ------------------------------------------------------------------
    logger.info("[DEBUG] Phase 1/4: Deploying MQTT stack...")
    deploy_ok = context["deploy_mqtt"]()
    logger.info(f"[DEBUG] deploy_mqtt returned: {deploy_ok}")
    assert deploy_ok, "MQTT deployment failed before alert validation could start"

    # ------------------------------------------------------------------
    # Phase 2: Pre-validation health checks — confirm prerequisites the
    # validate_mqtt_alert_system helper assumes are already in place.
    # ------------------------------------------------------------------
    tsam_name = constants.CONTAINERS["time_series_analytics"]["name"]
    mqtt_broker_name = constants.CONTAINERS["mqtt_broker"]["name"]
    mqtt_publisher_name = constants.CONTAINERS["mqtt_publisher"]["name"]
    telegraf_name = constants.CONTAINERS["telegraf"]["name"]

    logger.info("[DEBUG] Phase 2/4: Pre-validation health checks")
    logger.info(f"[DEBUG] Checking TSAM container '{tsam_name}' is running...")
    tsam_running = docker_utils.container_is_running(tsam_name)
    logger.info(f"[DEBUG]   tsam_running={tsam_running}")
    assert tsam_running, f"TSAM container '{tsam_name}' is not running before MQTT alert validation"

    logger.info(f"[DEBUG] Checking MQTT broker container '{mqtt_broker_name}' is running...")
    mqtt_broker_running = docker_utils.container_is_running(mqtt_broker_name)
    logger.info(f"[DEBUG]   mqtt_broker_running={mqtt_broker_running}")
    assert mqtt_broker_running, f"MQTT broker container '{mqtt_broker_name}' is not running before alert validation"

    logger.info(f"[DEBUG] Checking MQTT publisher container '{mqtt_publisher_name}' is running...")
    mqtt_publisher_running = docker_utils.container_is_running(mqtt_publisher_name)
    logger.info(f"[DEBUG]   mqtt_publisher_running={mqtt_publisher_running}")
    assert mqtt_publisher_running, f"MQTT publisher container '{mqtt_publisher_name}' is not running before alert validation"

    logger.info("[DEBUG] Polling ts-api health endpoint until ready...")
    svc_ready = docker_utils.wait_until_service_ready(
        timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT
    )
    logger.info(f"[DEBUG]   wait_until_service_ready={svc_ready}")
    assert svc_ready, "ts-api health endpoint did not become ready before MQTT alert validation"

    # Snapshot of running containers + their status — useful when triaging
    # failures that show up later as "container X not running".
    try:
        ps_out = _subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        logger.info(f"[DEBUG] docker ps snapshot:\n{ps_out}")
    except Exception as exc:
        logger.warning(f"[DEBUG] Failed to capture docker ps snapshot: {exc}")

    # ------------------------------------------------------------------
    # Phase 3: Run the actual validation helper
    # ------------------------------------------------------------------
    logger.info("[DEBUG] Phase 3/4: Invoking validate_mqtt_alert_system()...")
    validation_result = docker_utils.validate_mqtt_alert_system(constants.WIND_SAMPLE_APP)
    logger.info(f"[DEBUG] validate_mqtt_alert_system returned: {validation_result}")

    # ------------------------------------------------------------------
    # Phase 4: On failure, dump container state + key logs so the CI
    # output is self-sufficient for diagnosis.
    # ------------------------------------------------------------------
    if not validation_result:
        logger.error("[DEBUG] Phase 4/4: Validation FAILED — collecting diagnostics")

        # Re-snapshot container state (something may have crashed / restarted)
        try:
            ps_out = _subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
            logger.error(f"[DEBUG] docker ps -a (post-failure):\n{ps_out}")
        except Exception as exc:
            logger.warning(f"[DEBUG] Failed to capture docker ps -a: {exc}")

        # Tail logs from the containers that participate in the MQTT
        # alert pipeline.  We use --tail to bound output size in CI logs.
        for cname in (tsam_name, mqtt_broker_name, mqtt_publisher_name, telegraf_name):
            try:
                logs_out = _subprocess.run(
                    ["docker", "logs", "--tail", "120", cname],
                    capture_output=True, text=True, timeout=15,
                )
                stdout = (logs_out.stdout or "").strip()
                stderr = (logs_out.stderr or "").strip()
                logger.error(f"[DEBUG] ----- {cname} stdout (last 120) -----\n{stdout}")
                if stderr:
                    logger.error(f"[DEBUG] ----- {cname} stderr (last 120) -----\n{stderr}")
            except Exception as exc:
                logger.warning(f"[DEBUG] Failed to capture logs for {cname}: {exc}")

    logger.info(f"MQTT alert validation result: {validation_result}")
    assert validation_result == True, (
        "MQTT alert system validation failed — see [DEBUG] log lines above for "
        "container state and TSAM/MQTT-broker/MQTT-publisher/Telegraf log tails "
        "captured at failure time."
    )

    # Cleanup handled by fixture


def test_influxdb_data_with_mqtt(setup_wind_turbine_environment):
    """TC_017: Testing InfluxDB data with MQTT ingestion"""
    logger.info("TC_017: Testing InfluxDB data with MQTT ingestion")
    context = setup_wind_turbine_environment
    context["deploy_mqtt"]()

    # Poll until service is ready before querying InfluxDB
    logger.info("Polling until service is ready and data is flowing...")
    docker_utils.wait_until_service_ready(timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT)

    # Test InfluxDB data retrieval
    influxdb_data = docker_utils.execute_influxdb_commands(container_name=constants.CONTAINERS["influxdb"]["name"])

    # Check if the data retrieval was successful (not None)
    logger.info(f"InfluxDB MQTT data retrieval result: {influxdb_data is not None}, data: {influxdb_data}")
    assert influxdb_data is not None, "InfluxDB data retrieval failed"

    # Cleanup handled by fixture


def test_stability_mqtt_for_3_Minutes(setup_wind_turbine_environment):
    """TC_019: Testing make up MQTT and make down for longer duration for 3 Minutes."""
    logger.info("TC_019: Testing make up MQTT and make down for longer duration for 3 Minutes")
    context = setup_wind_turbine_environment
    context["deploy_mqtt"]()

    # Wait for a while to ensure stability (3 minutes)
    logger.info("Waiting for 3 minutes to ensure stability...")
    docker_utils.wait_for_stability(constants.EXTENDED_STABILITY_TIME)

    # Cleanup handled by fixture


def test_mqtt_multi_stream_ingestion(setup_wind_turbine_environment):
    """TC_026: Testing MQTT multi-stream ingestion with wind-turbine-anomaly-detection app"""
    logger.info("TC_026: Testing MQTT multi-stream ingestion with 3 streams")
    context = setup_wind_turbine_environment

    # Set the number of streams for testing
    num_streams = 3

    # Use enhanced deploy_mqtt function with app and num_of_streams parameters
    success = context["deploy_mqtt"](app=constants.WIND_SAMPLE_APP, num_of_streams=num_streams)
    if success:
        logger.info(f"MQTT multi-stream ingestion with {num_streams} streams succeeded")
        # Poll until all containers are up instead of sleeping blindly
        docker_utils.wait_until_containers_up(_WIND_MQTT_CONTAINERS, timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT)

        # Verify containers are running
        containers = docker_utils.get_the_deployed_containers()
        logger.info(f"Deployed containers: {containers}")
        logger.info(f"Containers found after MQTT multi-stream deployment: {len(containers) if containers else 0}")
        assert containers, "No containers found after multi-stream deployment"

        # Verify we have the expected MQTT publisher containers (should be multiple for multi-stream)
        mqtt_containers = [c for c in containers if 'mqtt-publisher' in c]
        logger.info(f"Found {len(mqtt_containers)} MQTT publisher containers: {mqtt_containers}")

        # Run make status check before declaring success
        logger.info("Running make status check to verify deployment health...")
        status_result = docker_utils.invoke_make_status()
        if status_result:
            logger.info("Make status check passed - deployment is healthy")
            test_result = True
        else:
            logger.error("Make status check failed - deployment has issues")
            test_result = False
    else:
        logger.error(f"MQTT multi-stream ingestion with {num_streams} streams failed")
        test_result = False

    logger.info(f"MQTT multi-stream test result: {test_result}")
    assert test_result == True, f"MQTT multi-stream deployment with {num_streams} streams failed"
    # No manual cleanup needed - handled by fixture


def test_mqtt_multi_stream_scalability(setup_wind_turbine_environment):
    """TC_028: Testing MQTT multi-stream scalability with different stream counts"""
    logger.info("TC_028: Testing MQTT multi-stream scalability with different stream counts")
    context = setup_wind_turbine_environment

    # Test with different numbers of streams
    stream_counts = [2, 5]

    for num_streams in stream_counts:
        logger.info(f"Testing MQTT with {num_streams} streams")

        # Use enhanced deploy_mqtt function with app and num_of_streams parameters
        success = context["deploy_mqtt"](app=constants.WIND_SAMPLE_APP, num_of_streams=num_streams)
        if success:
            logger.info(f"MQTT multi-stream ingestion with {num_streams} streams succeeded")
            # Poll until all containers are up instead of sleeping blindly
            docker_utils.wait_until_containers_up(_WIND_MQTT_CONTAINERS, timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT)

            # Verify containers are running
            containers = docker_utils.get_the_deployed_containers()
            logger.info(f"Deployed containers for {num_streams} streams: {len(containers)} total")
            assert containers, f"No containers found after deployment with {num_streams} streams"

            # Run make status check before declaring success
            logger.info("Running make status check to verify deployment health...")
            status_result = docker_utils.invoke_make_status()
            if status_result:
                logger.info("Make status check passed - deployment is healthy")
                test_result = True
            else:
                logger.error("Make status check failed - deployment has issues")
                test_result = False
        else:
            logger.error(f"MQTT multi-stream ingestion with {num_streams} streams failed")
            test_result = False

        logger.info(f"MQTT scalability test result for {num_streams} streams: {test_result}")
        assert test_result == True, f"MQTT multi-stream deployment with {num_streams} streams failed"

        # Clean up between different stream counts (except the last one)
        if num_streams != stream_counts[-1]:
            logger.info(f"Cleaning up after {num_streams} streams test")
            docker_utils.invoke_make_down()
            docker_utils.wait_for_stability(constants.WIND_TURBINE_CYCLE_GAP_TIME)

    # Final cleanup handled by fixture


# ---------------------------------------------------------------------------
# GPU test (MQTT ingestion) — COMMENTED OUT for now
# ---------------------------------------------------------------------------
# @pytest.mark.skipif(not docker_utils.check_system_gpu_devices(), reason="No GPU devices detected on this system")
# def test_gpu_mqtt(setup_wind_turbine_environment):
#     """TC_032: Testing GPU device configuration with MQTT ingestion in time-series analytics config"""
#     logger.info("TC_032: Testing GPU device configuration with MQTT ingestion in time-series analytics config")
#
#     context = setup_wind_turbine_environment
#     context["deploy_mqtt"](app=constants.WIND_SAMPLE_APP)
#     logger.info("mqtt deployment succeeded")
#
#     logger.info("Polling until service is ready...")
#     docker_utils.wait_until_service_ready(timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT)
#
#     logger.info(f"Settle period {constants.WIND_TURBINE_POST_DEPLOY_SETTLE}s before GPU POST...")
#     time.sleep(constants.WIND_TURBINE_POST_DEPLOY_SETTLE)
#
#     curl_result = docker_utils.execute_gpu_config_curl(device="gpu")
#     logger.info(f"GPU configuration curl result: {curl_result}")
#     assert curl_result, "GPU configuration test via REST API failed"
#
#     logger.info("Waiting for service to restart and apply GPU configuration...")
#     docker_utils.wait_until_service_ready(timeout=constants.WIND_TURBINE_CONTAINER_READY_TIMEOUT, accept_503=False)
#     logger.info(f"Grace period {constants.WIND_TURBINE_GPU_RESTART_GRACE}s for kapacitor UDF to bind GPU...")
#     time.sleep(constants.WIND_TURBINE_GPU_RESTART_GRACE)
#
#     logger.info("Verifying if logs contain GPU keywords...")
#     container_name = constants.CONTAINERS["time_series_analytics"]["name"]
#     gpu_result = docker_utils.check_log_gpu(container_name, timeout=constants.WIND_TURBINE_GPU_LOG_TIMEOUT, interval=10)
#
#     logger.info(f"GPU log check result: {gpu_result}")
#     assert gpu_result == True, "GPU keywords not found in logs"
