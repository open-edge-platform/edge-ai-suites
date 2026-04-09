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
import os
import subprocess
import time
import logging
import conftest_helm
# Set up logger
logger = logging.getLogger(__name__)

# Import the fixture directly from conftest_helm.py
pytest_plugins = ["conftest_helm"]

# Retrieve environment variables
FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL = helm_utils.get_env_values()

@pytest.mark.parametrize("telegraf_input_plugin", [constants.TELEGRAF_OPCUA_PLUGIN])
def test_influxdb_data_retention_with_opcua(setup_helm_environment, telegraf_input_plugin):
    logger.info("TC_001: Testing InfluxDB data retention of 1 hour with opcua plugin.")
    # Define the path to the config.json file
   
    assert helm_utils.verify_pods(namespace) is True, "Pods are not running as expected for opcua input plugin"
    # Get the current system time
    
    assert helm_utils.setup_sample_app_udf_deployment_package(chart_path) == True, "Failed to set up wind turbine anomaly detector for opcua input plugin"
    logger.info(f"UDF deployment package is activated and wait for the pods to stabilize in {wait_time} seconds")

    time.sleep(wait_time)  # Wait for the pods to stabilize    
    assert helm_utils.verify_pods_logs(namespace, "DEBUG") is True, "Pods logs are not working for opcua input plugin"

    # Print the InfluxDB retention duration value from case 6
    influxdb_username, influxdb_password, influxdb_retention_duration = helm_utils.fetch_influxdb_credentials(chart_path)
    logger.info(f"InfluxDB Retention Duration : {influxdb_retention_duration}")
    duration = helm_utils.parse_duration(influxdb_retention_duration)
    logger.info(f"Parsed InfluxDB Retention Duration: {duration} seconds")
    assert helm_utils.execute_influxdb_commands(namespace, chart_path) is True, "Failed to execute InfluxDB commands for opcua input plugin"  
    response, success = helm_utils.verify_influxdb_retention(namespace, chart_path, response=None)
    if success == True and response is not None:
        logger.info(f"InfluxDB response for first record is working as expected for opcua input plugin: {response}")
    else:
        logger.warning("InfluxDB response for first record is not working as expected for opcua input plugin")

    logger.info(f"Waiting for the InfluxDB retention duration in secs to take effect... {2 * duration + 300}")
    time.sleep(2 * duration + 300)  # Wait for the InfluxDB retention to take effect
    response1, success = helm_utils.verify_influxdb_retention(namespace, chart_path, response=None)
    logger.info(f"First record before retention duration: {response} and second record after retention: {response1}")
    if success == True and response1 is not None:
        if response1 != response:
            success = True
        elif response1 == response:
            logger.warning("InfluxDB retention duration is not working as expected for opcua input plugin")
            success = False        
        else:
            logger.error("Unable to fetch the data from InfluxDB for opcua input plugin")
            success = False
    else:
        logger.error("InfluxDB command is not fetched properly")
        success = False
    assert success is True, "InfluxDB retention duration is not working as expected for opcua input plugin"
