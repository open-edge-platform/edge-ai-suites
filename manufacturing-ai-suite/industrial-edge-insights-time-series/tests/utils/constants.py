#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os

# Centralized container definitions for all sample apps
CONTAINERS = {
    "influxdb": {
        "name": "ia-influxdb",
        "port": 8086
    },
    "telegraf": {
        "name": "ia-telegraf"
    },
    "time_series_analytics": {
        "name": "ia-time-series-analytics-microservice",
        "port": 5000
    },
    "mqtt_broker": {
        "name": "ia-mqtt-broker",
        "port": 1883
    },
    "mqtt_publisher": {
        "name": "ia-mqtt-publisher"
    },
    "opcua_server": {
        "name": "timeseriessoftware-ia-opcua-server-1",
        "port": 4840
    },
    "grafana": {
        "name": "ia-grafana",
        "port": 3000
    },
    "dlstreamer": {
        "name": "dlstreamer-pipeline-server",
        "port": 8080
    },
    "mediamtx": {
        "name": "mediamtx"
    },
    "nginx_proxy": {
        "name": "nginx_proxy",
        "https_port": 3000,
        "mqtt_port": 1883,
        "image_store_path": "/image_store"
    },
    "coturn": {
        "name": "coturn"
    },
    "fusion_analytics": {
        "name": "ia-fusion-analytics"
    },
    "weld_data_simulator": {
        "name": "ia-weld-data-simulator"
    },
    "multimodal_app": {
        "name": "ia-multimodal-weld-defect-detection-sample-app"
    },
    "seaweedfs_master": {
        "name": "seaweedfs-master"
    },
    "seaweedfs_volume": {
        "name": "seaweedfs-volume"
    },
    "seaweedfs_filer": {
        "name": "seaweedfs-filer"
    },
    "seaweedfs_s3": {
        "name": "seaweedfs-s3"
    }
}

TELEGRAF_MQTT_PLUGIN = "mqtt_consumer"
TELEGRAF_OPCUA_PLUGIN = "opcua"
OPCUA_SERVER_URL = f"opc.tcp://localhost:{CONTAINERS['opcua_server']['port']}"  # Update if needed
ALERT_NODE_ID = "ns=2;s=Alert"  # Replace with the actual node ID used for alerts
UDF_DIR = "../../apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/"
MODEL_DIR = "../../apps/wind-turbine-anomaly-detection/time-series-analytics-config/models/"
TICK_DIR = "../../apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/"
# Fix PYTEST_DIR to use absolute path
import os
PYTEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../functional'))
WIND_INGESTED_CSV= "/apps/wind-turbine-anomaly-detection/simulation-data/wind-turbine-anomaly-detection.csv"
WELD_INGESTED_CSV= "/apps/weld-defect-detection/simulation-data/burnthrough_weld_12-14-22-0201-02.csv"
EDGE_AI_SUITES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../industrial-edge-insights-time-series"))
WIND_TURBINE_INGESTED_TOPIC = "wind-turbine-data"
WIND_TURBINE_ANALYTICS_TOPIC = "wind-turbine-anomaly-data"
WELD_INGESTED_TOPIC = "weld-sensor-data"
WELD_ANALYTICS_TOPIC = "weld-sensor-anomaly-data"
WELD_SAMPLE_APP = "weld-defect-detection"
WIND_SAMPLE_APP = "wind-turbine-anomaly-detection"
WIND_UDF= "windturbine_anomaly_detector"
WIND_MODEL= "windturbine_anomaly_detector.pkl"
WELD_UDF= "weld_defect_detector"
WELD_MODEL= "weld_defect_detector.pkl"
TARGET_SUBPATH = "edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series"

WINDTURBINE_TICK_SCRIPT_PATH = "apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick"

# Configuration directory paths
WINDTURBINE_CONFIG_DIR = "apps/wind-turbine-anomaly-detection/time-series-analytics-config"
HELM_TIMESERIES = "apps/wind-turbine-anomaly-detection/time-series-analytics-config"
HELM_WELD = "apps/weld-defect-detection/time-series-analytics-config"

# KPI Test Constants
KPI_DEPLOYMENT_TIME_THRESHOLD = 120  # Maximum acceptable deployment time in seconds
KPI_BUILD_TIME_THRESHOLD = 180       # Maximum acceptable build time in seconds
KPI_REQUIRED_SUCCESS_RATE = 100      # Required success rate percentage
KPI_TEST_ITERATIONS = 3              # Number of iterations for KPI tests

# Container/Image Size Threshold (in MB)
CONTAINER_IMAGE_SIZE_THRESHOLD = 2200  # 2.2 GB maximum size for any container/image

# Container Stabilization Times (in seconds)
CONTAINER_STABILIZATION_TIME = 30    # Default stabilization time for container tests
EXTENDED_STABILITY_TIME = 180        # Extended time for stability tests (3 minutes)

# Multimodal wait durations (in seconds) to avoid hard-coded sleeps in tests
MULTIMODAL_WAIT_AFTER_CHART_GEN = 10
MULTIMODAL_WAIT_AFTER_VALUES_UPDATE = 15
MULTIMODAL_WAIT_AFTER_HELM_INSTALL = 30
MULTIMODAL_WAIT_AFTER_PODS_READY = 20
MULTIMODAL_WAIT_AFTER_UDF_ACTIVATION = 25
MULTIMODAL_WAIT_FOR_VISION_DATA = 60

# Multimodal SeaweedFS S3 wait durations (in seconds)
MULTIMODAL_SEAWEED_WAIT_POD_STABILIZATION = 30   # wait after essential pods verified
MULTIMODAL_SEAWEED_WAIT_INFLUX_CONSISTENCY = 15  # wait for InfluxDB data consistency
MULTIMODAL_SEAWEED_WAIT_S3_API_RESPONSE = 10     # wait for S3 API response processing
MULTIMODAL_SEAWEED_WAIT_S3_POPULATE = 30         # wait for S3 storage to be fully populated
MULTIMODAL_SEAWEED_WAIT_FILE_VALIDATION = 10     # wait before file content validation

# Multimodal specific constants
MULTIMODAL_TARGET_SUBPATH = "edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal"
MULTIMODAL_APPLICATION_DIRECTORY = os.path.join(os.path.dirname(__file__), "../../../industrial-edge-insights-multimodal")
MULTIMODAL_SAMPLE_APP = "multimodal-weld-detection"

# Sample App Configurations - JSON objects containing all relevant config for each app
SAMPLE_APPS_CONFIG = {
    "wind-turbine-anomaly-detection": {
        "app_name": "wind-turbine-anomaly-detection",
        "display_name": "Wind Turbine Anomaly Detection",
        "ingested_topic": "wind-turbine-data",
        "analytics_topic": "wind-turbine-anomaly-data",
        "alert_topic": "alerts/wind_turbine",
        "udf": "windturbine_anomaly_detector",
        "model": "windturbine_anomaly_detector.pkl",
        "udf_deployment_package": "windturbine_anomaly_udf",
        "config_dir": "apps/wind-turbine-anomaly-detection/time-series-analytics-config",
        "udfs_dir": "apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/",
        "models_dir": "apps/wind-turbine-anomaly-detection/time-series-analytics-config/models/",
        "tick_scripts_dir": "apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/",
        "tick_script_path": "apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick",
        "alert_config": {
            "enabled": True,
            "threshold": 0.8,
            "node_id": "ns=2;s=WindTurbineAlert"
        },
        "grafana_dashboard": "wind-turbine-dashboard"
    },
    "weld-defect-detection": {
        "app_name": "weld-defect-detection", 
        "display_name": "Weld Defect Detection",
        "ingested_topic": "weld-sensor-data",
        "analytics_topic": "weld-sensor-anomaly-data",
        "alert_topic": "alerts/weld_defects",
        "udf": "weld_defect_detector",
        "model": "weld_defect_detector.cb",
        "udf_deployment_package": "weld_anomaly_udf",
        "config_dir": "apps/weld-defect-detection/time-series-analytics-config",
        "udfs_dir": "apps/weld-defect-detection/time-series-analytics-config/udfs/",
        "models_dir": "apps/weld-defect-detection/time-series-analytics-config/models/",
        "tick_scripts_dir": "apps/weld-defect-detection/time-series-analytics-config/tick_scripts/",
        "tick_script_path": "apps/weld-defect-detection/time-series-analytics-config/tick_scripts/weld_defect_detector.tick",
        "alert_config": {
            "enabled": True,
            "threshold": 0.7,
            "node_id": "ns=2;s=WeldAlert"
        },
        "grafana_dashboard": "weld-anomaly-dashboard"
    },
    "multimodal-weld-detection": {
        "app_name": "multimodal-weld-detection",
        "display_name": "Multimodal Weld Defect Detection",
        "ingested_topic": "weld-sensor-data",
        "analytics_topic": "weld-sensor-anomaly-data",
        "vision_topic": "vision_weld_defect_classification",
        "vision_measurement": "vision-weld-classification-results",
        "fusion_topic": "fusion/anomaly_detection_results",
        "fusion_measurement": "fusion_result",
        "alert_topic": "alerts/weld_defect_detection",
        "udf": "weld_defect_detector",
        "model": "weld_defect_detector.cb",
        "udf_deployment_package": "weld_anomaly_udf",
        "config_dir": "configs/time-series-analytics-microservice",
        "udfs_dir": "configs/time-series-analytics-microservice/udfs/",
        "models_dir": "configs/time-series-analytics-microservice/models/",
        "tick_scripts_dir": "configs/time-series-analytics-microservice/tick_scripts/",
        "tick_script_path": "configs/time-series-analytics-microservice/tick_scripts/weld_defect_detector.tick",
        "alert_config": {
            "enabled": True,
            "threshold": 0.7,
            "node_id": "ns=2;s=WeldAlert"
        },
        "grafana_dashboard": "multimodal-weld-detection-dashboard",
        # Multimodal-specific additional containers
        "additional_containers": [
            "ia-grafana",
            "ia-weld-data-simulator",
            "ia-fusion-analytics",
            "dlstreamer-pipeline-server",
            "mediamtx",
            "coturn",
            "nginx_proxy"
        ],
        # Multimodal container list definition
        "multimodal_container_list": [
            CONTAINERS["influxdb"]["name"],
            CONTAINERS["telegraf"]["name"],
            CONTAINERS["time_series_analytics"]["name"],
            CONTAINERS["mqtt_broker"]["name"],
            CONTAINERS["grafana"]["name"],
            CONTAINERS["weld_data_simulator"]["name"],
            CONTAINERS["fusion_analytics"]["name"],
            CONTAINERS["dlstreamer"]["name"],
            CONTAINERS["mediamtx"]["name"],
            CONTAINERS["coturn"]["name"],
            CONTAINERS["nginx_proxy"]["name"]
        ]
    }
}
# Alert configurations from main branch
MQTT_ALERT =  {
                    "mqtt_broker_host": "ia-mqtt-broker",
                    "mqtt_broker_port": 1883,
                    "name": "my_mqtt_broker"
                }
OPCUA_ALERT = {
            "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
            "namespace": 1,
            "node_id": 2004
        }

# Essential sample app name constants - access via SAMPLE_APPS_CONFIG and helper functions
WELD_SAMPLE_APP = "weld-defect-detection"
WIND_SAMPLE_APP = "wind-turbine-anomaly-detection"
MULTIMODAL_SAMPLE_APP = "multimodal-weld-detection"

# Helper functions to get app configurations
def get_app_config(app_name):
    """Get the complete configuration for a specific app"""
    return SAMPLE_APPS_CONFIG.get(app_name, {})

def get_app_topics(app_name):
    """Get all topic names for a specific app"""
    config = get_app_config(app_name)
    return {
        "ingested": config.get("ingested_topic"),
        "analytics": config.get("analytics_topic"), 
        "alert": config.get("alert_topic")
    }

def get_app_influxdb_measurement(app_name):
    """Get the InfluxDB measurement name for a specific app (uses ingested_topic)"""
    config = get_app_config(app_name)
    return config.get("ingested_topic")

def get_app_vision_measurement(app_name):
    """Get the InfluxDB vision measurement name for a specific app"""
    config = get_app_config(app_name)
    return config.get("vision_measurement")

def get_app_alert_config(app_name):
    """Get the alert configuration for a specific app"""
    config = get_app_config(app_name)
    return config.get("alert_config", {})

# Essential database and configuration constants
INFLUXDB_DATABASE = "datain"

# Essential container constants (commonly used in tests)
NGINX_CONTAINER = CONTAINERS["nginx_proxy"]["name"]
NGINX_HTTPS_PORT = str(CONTAINERS["nginx_proxy"]["https_port"])
NGINX_EXPECTED_PORTS = [str(CONTAINERS["nginx_proxy"]["https_port"]), str(CONTAINERS["nginx_proxy"]["mqtt_port"])]
MEDIAMTX_CONTAINER = CONTAINERS["mediamtx"]["name"]
COTURN_CONTAINER = CONTAINERS["coturn"]["name"]

# Essential test constants
TEST_DATA_PROCESSING_DELAY = 120   # seconds - increased for simulation startup phase
TEST_MQTT_TIMEOUT = 60             # seconds
TEST_NGINX_STARTUP_DELAY = 10      # seconds
TEST_CURL_TIMEOUT = 30             # seconds
TEST_PROCESS_CHECK_TIMEOUT = 30    # seconds for process checks
UDF_DEPLOYMENT_TIMEOUT = 180       # seconds (3 minutes) - aligned with 08Weekly fast approach
PODS_HEALTHY_CHECK_STATUS_TIMEOUT = 60    # seconds - standard pod cleanup timeout
PODS_HEALTHY_CHECK_STATUS_TIMEOUT_MULTI = 120  # seconds - extended timeout for multimodal (dual-service) cleanup
PODS_VERIFY_TIMEOUT = 300          # seconds - timeout for verify_pods after Helm install
MQTT_PORT_INT = CONTAINERS["mqtt_broker"]["port"]
MULTIMODAL_DOCKER_PRE_TEARDOWN_WAIT = 5   # seconds before teardown validations
MULTIMODAL_DOCKER_POST_TEARDOWN_WAIT = 10 # seconds to let containers stop
MULTIMODAL_DOCKER_FUSION_READY_WAIT = 10  # seconds to ensure fusion logs propagate

# MediaMTX streaming constants - access via nginx proxy
MEDIAMTX_STREAM_URL = f"https://localhost:{CONTAINERS['nginx_proxy']['https_port']}/samplestream"

OPCUA_SERVER_PORT = 30003
