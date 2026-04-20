#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import subprocess
import json
import sys
import time
import os
import shutil
import tempfile
import copy
import random
import common_utils
from common_utils import cross_verify_img_handle_with_s3
import yaml
import secrets
import string
from ruamel.yaml import YAML
import logging
import re
from pathlib import Path
import constants

# Define PROXY_URL at module level
PROXY_URL = os.getenv("PROXY_URL", None)

# Base directory used to resolve relative paths defined in pytest.ini
FUNCTIONAL_TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "functional"))



# Set up logger
logger = logging.getLogger(__name__)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TS_API_INTERNAL_URL = os.getenv("TS_API_INTERNAL_URL", "https://nginx:15443/ts-api/config")


def _resolve_path_under_repo(path_value):
    """Resolve relative chart paths against the repository root when possible."""
    if not path_value:
        return path_value

    expanded = os.path.expandvars(path_value)
    if os.path.isabs(expanded) and os.path.exists(expanded):
        return expanded

    marker = "edge-ai-suites"
    if marker in expanded:
        suffix = expanded.split(marker, 1)[1].lstrip(os.sep + "./")
        candidate = os.path.join(REPO_ROOT, marker, suffix)
    else:
        candidate = os.path.join(REPO_ROOT, expanded.lstrip("./"))

    candidate = os.path.normpath(candidate)
    if os.path.exists(candidate):
        return candidate

    return expanded

def _get_sample_app_config_dir(chart_path, sample_app):
    """Return absolute config directory for the given sample app relative to the chart path."""
    if not chart_path:
        logger.error("Chart path is required to locate sample app configuration for '%s'", sample_app)
        return None

    resolved_chart = _resolve_path_under_repo(chart_path) or os.path.expandvars(chart_path)
    chart_dir = Path(resolved_chart).expanduser().resolve()
    base_dir = chart_dir.parent

    relative_map = {
        constants.WIND_SAMPLE_APP: constants.HELM_TIMESERIES,
        constants.WELD_SAMPLE_APP: constants.HELM_WELD,
    }
    relative_path = relative_map.get(sample_app)
    if not relative_path:
        app_cfg = constants.get_app_config(sample_app)
        relative_path = app_cfg.get("config_dir") if app_cfg else None

    if not relative_path:
        logger.error("Unable to determine configuration directory for sample app '%s'", sample_app)
        return None

    config_path = Path(relative_path)
    if not config_path.is_absolute():
        config_path = (base_dir / config_path).resolve()

    if not config_path.exists():
        logger.error(
            "Configuration directory '%s' does not exist for sample app '%s'",
            config_path,
            sample_app,
        )
        return None
    return config_path


def _stage_udf_package(config_dir, sample_app):
    """Copy required UDF artifacts into a temporary directory for kubectl cp."""
    staging_root = Path(tempfile.mkdtemp(prefix=f"{sample_app}_udf_"))
    package_dir = staging_root / sample_app
    try:
        package_dir.mkdir(parents=True, exist_ok=True)
        for folder in ("models", "tick_scripts", "udfs"):
            source = config_dir / folder
            if not source.exists():
                logger.error("Required folder '%s' not found under %s", folder, config_dir)
                raise FileNotFoundError(f"Missing folder {folder}")
            shutil.copytree(source, package_dir / folder, dirs_exist_ok=True)
        return package_dir, staging_root
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _build_alerts_payload(alert_mode):
    """Construct the alerts payload block expected by the ts-api config endpoint."""
    if isinstance(alert_mode, dict):
        return alert_mode

    mode = (alert_mode or "mqtt").lower()
    if mode == "mqtt":
        return {"mqtt": copy.deepcopy(constants.MQTT_ALERT)}
    if mode == "opcua":
        return {"opcua": copy.deepcopy(constants.OPCUA_ALERT)}

    logger.error("Unsupported alert mode '%s' supplied for UDF activation", alert_mode)
    return None


def _build_udf_payload(sample_app, device_value, alert_mode):
    """Generate the full ts-api payload for the given app/device/alert combination."""
    app_cfg = constants.get_app_config(sample_app)
    udf_name = app_cfg.get("udf") if app_cfg else None
    model_name = app_cfg.get("model") if app_cfg else None

    if not udf_name or not model_name:
        fallback = {
            constants.WIND_SAMPLE_APP: (constants.WIND_UDF, constants.WIND_MODEL),
            constants.WELD_SAMPLE_APP: (constants.WELD_UDF, constants.WELD_MODEL),
        }.get(sample_app)
        if fallback:
            udf_name, model_name = fallback

    if not udf_name or not model_name:
        logger.error("Unable to resolve UDF/model names for sample app '%s'", sample_app)
        return None

    alerts_block = _build_alerts_payload(alert_mode)
    if not alerts_block:
        return None

    payload = {
        "udfs": {
            "name": udf_name,
            "models": model_name,
            "device": device_value,
        },
        "alerts": alerts_block,
    }
    return payload

def _resolve_chart_path(raw_path):
    """Return an absolute chart path regardless of current working directory."""
    if not raw_path:
        return raw_path

    expanded_path = os.path.expandvars(raw_path)
    if os.path.isabs(expanded_path):
        return os.path.normpath(expanded_path)

    # pytest.ini paths are authored relative to tests/functional
    normalized_path = os.path.abspath(os.path.join(FUNCTIONAL_TESTS_DIR, expanded_path))
    return os.path.normpath(normalized_path)

def get_env_values():
    """Load configuration and extract Helm-related values."""
    # Access the configuration directly
    FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE= os.getenv("FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE", None)
    release_name = os.getenv("release_name", None)
    release_name_weld = os.getenv("release_name_weld", None)
    chart_path = _resolve_chart_path(os.getenv("chart_path", None))
    namespace = os.getenv("namespace", None)
    grafana_url = os.getenv("grafana_url", None)
    wait_time = int(os.getenv("wait_time_for_pods_to_come_up", "90"))  # Default sleep time if not set
    target = os.getenv("target", None)
    if not all([FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, chart_path, namespace, grafana_url, wait_time, target]):
        raise EnvironmentError("One or more environment variables are not set.")
    return FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL

def _resolve_chart_path_from_cwd(raw_path):
    """Resolve a chart path relative to the current working directory (pytest invocation dir)."""
    if not raw_path:
        return raw_path
    expanded = os.path.expandvars(raw_path)
    if os.path.isabs(expanded) and os.path.exists(expanded):
        return expanded
    resolved = os.path.normpath(os.path.join(os.getcwd(), expanded))
    if os.path.exists(resolved):
        return resolved
    # Fall back to the repo-root strategy as a last resort
    return _resolve_path_under_repo(raw_path)


def get_multimodal_env_values():
    """Load multimodal Helm configuration while reusing generic defaults when needed."""
    functional_path = os.getenv("FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE", None)
    release_name_multi = os.getenv("release_name_multi", release_name)
    release_name_weld_multi = os.getenv("release_name_weld_multi", release_name_weld)
    raw_chart_path_multi = os.getenv("chart_path_multi", None)
    chart_path_multi = _resolve_chart_path_from_cwd(raw_chart_path_multi) if raw_chart_path_multi else chart_path
    namespace_multi = os.getenv("namespace_multi", namespace)
    grafana_url_multi = os.getenv("grafana_url_multi", grafana_url)
    wait_time_multi = int(os.getenv("wait_time_for_pods_to_come_up_multi", str(wait_time)))
    target_host = os.getenv("target", target)
    proxy_url = PROXY_URL

    if not all([functional_path, release_name_multi, chart_path_multi, namespace_multi, grafana_url_multi, wait_time_multi, target_host]):
        raise EnvironmentError("Multimodal Helm environment variables are not set.")

    return (
        functional_path,
        release_name_multi,
        release_name_weld_multi,
        chart_path_multi,
        namespace_multi,
        grafana_url_multi,
        wait_time_multi,
        target_host,
        proxy_url,
    )

FUNCTIONAL_FOLDER_PATH_FROM_TEST_FILE, release_name, release_name_weld, chart_path, namespace, grafana_url, wait_time, target, PROXY_URL = get_env_values()
# Check if environment variables are set
password_test_cases = {
    "test_case_1": {
        "INFLUXDB_USERNAME": "",
        "INFLUXDB_PASSWORD": "",
        "VISUALIZER_GRAFANA_USER": "",
        "VISUALIZER_GRAFANA_PASSWORD": "",
        "MINIO_ACCESS_KEY": "",
        "POSTGRES_PASSWORD": "",
        "MINIO_SECRET_KEY": ""
    },
    "test_case_2": {
        "INFLUXDB_USERNAME": common_utils.generate_password(4),
        "INFLUXDB_PASSWORD": common_utils.generate_password(2),
        "VISUALIZER_GRAFANA_USER": common_utils.generate_password(4),
        "VISUALIZER_GRAFANA_PASSWORD": common_utils.generate_password(7),
        "MINIO_ACCESS_KEY": common_utils.generate_password(0),
        "POSTGRES_PASSWORD": common_utils.generate_password(1),
        "MINIO_SECRET_KEY": common_utils.generate_password(5)
    },
    "test_case_3": {
        "INFLUXDB_USERNAME": common_utils.generate_username(5),
        "INFLUXDB_PASSWORD": common_utils.generate_password(10),
        "VISUALIZER_GRAFANA_USER": common_utils.generate_username(5),
        "VISUALIZER_GRAFANA_PASSWORD": common_utils.generate_password(10),
        "MINIO_ACCESS_KEY": common_utils.generate_password(10),
        "POSTGRES_PASSWORD": common_utils.generate_password(10),
        "MINIO_SECRET_KEY": common_utils.generate_password(10),
        "HTTP_PROXY": os.getenv("http_proxy", PROXY_URL),
        "HTTPS_PROXY": os.getenv("https_proxy", PROXY_URL),
        "LOG_LEVEL": "DEBUG",
        "HOST_IP": common_utils.get_host_ip(),
        "S3_STORAGE_USERNAME": common_utils.generate_username(8),
        "S3_STORAGE_PASSWORD": common_utils.generate_password(12),
        "MTX_WEBRTCICESERVERS2_0_USERNAME": common_utils.generate_username(8),
        "MTX_WEBRTCICESERVERS2_0_PASSWORD": common_utils.generate_password(12),
    },
    
        "test_case_4": {
            "INFLUXDB_USERNAME": common_utils.generate_username(5),
            "INFLUXDB_PASSWORD": common_utils.generate_password(10),
            "VISUALIZER_GRAFANA_USER": common_utils.generate_username(5),
            "VISUALIZER_GRAFANA_PASSWORD": common_utils.generate_password(10),
            "MINIO_ACCESS_KEY": common_utils.generate_password(10),
            "POSTGRES_PASSWORD": common_utils.generate_password(10),
            "MINIO_SECRET_KEY": common_utils.generate_password(10),
            "HOST_IP": common_utils.get_host_ip(),
            "HTTP_PROXY": os.getenv("http_proxy", PROXY_URL),
            "HTTPS_PROXY": os.getenv("https_proxy", PROXY_URL),
            "LOG_LEVEL": "DEBUG",
        },
        "test_case_5": {
            "INFLUXDB_USERNAME": common_utils.generate_username(5),
            "INFLUXDB_PASSWORD": common_utils.generate_password(10),
            "VISUALIZER_GRAFANA_USER": common_utils.generate_username(5),
            "VISUALIZER_GRAFANA_PASSWORD": common_utils.generate_password(10),
            "MINIO_ACCESS_KEY": common_utils.generate_password(10),
            "POSTGRES_PASSWORD": common_utils.generate_password(10),
            "MINIO_SECRET_KEY": common_utils.generate_password(10),
            "HOST_IP": common_utils.get_host_ip(),
            "HTTP_PROXY": os.getenv("http_proxy", PROXY_URL),
            "HTTPS_PROXY": os.getenv("https_proxy", PROXY_URL),
            "LOG_LEVEL": "INFO",
        },
        "test_case_6": {
            "INFLUXDB_USERNAME": common_utils.generate_username(5),
            "INFLUXDB_PASSWORD": common_utils.generate_password(10),
            "VISUALIZER_GRAFANA_USER": common_utils.generate_username(5),
            "VISUALIZER_GRAFANA_PASSWORD": common_utils.generate_password(10),
            "MINIO_ACCESS_KEY": common_utils.generate_password(10),
            "POSTGRES_PASSWORD": common_utils.generate_password(10),
            "MINIO_SECRET_KEY": common_utils.generate_password(10),
            "HOST_IP": common_utils.get_host_ip(),
            "HTTP_PROXY": os.getenv("http_proxy", PROXY_URL),
            "HTTPS_PROXY": os.getenv("https_proxy", PROXY_URL),
            "LOG_LEVEL": "WARN",
        },
    # Add other test cases as needed
}

def update_values_yaml(file_path, values):
    """Update the values.yaml file with the provided values."""
    try:
        # Expand environment variables in the file path
        expanded_path = os.path.expandvars(file_path)

        ryaml = YAML()
        ryaml.preserve_quotes = True

        with open(expanded_path, 'r') as file:
            data = ryaml.load(file)

        # Ensure the env section exists
        if 'env' not in data:
            data['env'] = {}

        # Update the env section with the provided values
        data['env'].update(values)

        # Write the updated data back to the file
        with open(expanded_path, 'w') as file:
            ryaml.dump(data, file)

        # Return True to indicate success
        return True

    except Exception as e:
        logger.error(f"Failed to update values.yaml: {e}")
        return False

def verify_pods(namespace, timeout=300, interval=5):
    """Verify pods using kubectl and wait until all are running or timeout."""
    start_time = time.time()
    try:
        while True:
            # Construct the kubectl command to get pod status in the namespace
            kubectl_command = ["kubectl", "get", "pods", "-n", namespace]

            # Execute the kubectl command and capture the output
            logger.info(f"Checking pod status in namespace '{namespace}'...")
            result = subprocess.run(kubectl_command, capture_output=True, text=True, check=True)

            # Parse the output to check pod statuses
            lines = result.stdout.strip().split('\n')
            
            # Check if there are any pods (more than just the header)
            if len(lines) <= 1:
                logger.warning(f"No pods found in namespace '{namespace}'")
                # If there are no pods, we can't verify them as running
                # This might indicate the deployment hasn't started yet
                elapsed_time = time.time() - start_time
                if elapsed_time > timeout:
                    logger.error("Timeout reached. No pods found in namespace.")
                    return False
                time.sleep(interval)
                continue
            
            # Print the header
            logger.info("NAME\t\t\t\t\t\tREADY\tSTATUS\tRESTARTS\tAGE")

            # Skip the header line and process pods
            pod_lines = lines[1:]
            all_running = True
            pod_count = 0
            
            for line in pod_lines:
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                columns = line.split()
                if len(columns) < 5:  # Ensure we have enough columns
                    logger.warning(f"Unexpected kubectl output format: {line}")
                    continue
                    
                pod_name = columns[0]
                pod_ready = columns[1]
                pod_status = columns[2]
                pod_restarts = columns[3]
                pod_age = columns[4]
                pod_count += 1

                # Print the pod information
                logger.info(f"{pod_name}\t\t{pod_ready}\t{pod_status}\t{pod_restarts}\t{pod_age}")

                if pod_status != "Running":
                    all_running = False

            # If we found pods and all are running, return success
            if pod_count > 0 and all_running:
                logger.info(f"All {pod_count} pods are running.")
                return True
            elif pod_count > 0 and not all_running:
                logger.info(f"Some pods are not yet running. Waiting...")
            
            # Check if timeout has been reached
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                logger.error(f"Timeout reached. Not all pods are running after {timeout}s.")
                return False

            # Wait before checking again
            time.sleep(interval)

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to verify pods: {e}")
        return False


def _parse_cpu_to_millicores(value):
    """Convert CPU usage strings reported by kubectl top into millicores."""
    if not value:
        return 0

    value = value.strip().lower()
    try:
        if value.endswith("n"):
            return float(value[:-1]) / 1000000.0
        if value.endswith("u"):
            return float(value[:-1]) / 1000.0
        if value.endswith("m"):
            return float(value[:-1])
        return float(value) * 1000.0
    except ValueError:
        logger.debug("Unable to parse CPU value '%s'", value)
        return 0


def _parse_memory_to_mb(value):
    """Convert memory usage strings reported by kubectl top into megabytes."""
    if not value:
        return 0

    value = value.strip().lower()
    multipliers = {
        "ki": 1 / 1024.0,
        "mi": 1.0,
        "gi": 1024.0,
        "ti": 1024.0 * 1024.0,
        "k": 1 / 1024.0,
        "m": 1.0,
        "g": 1024.0,
        "t": 1024.0 * 1024.0,
    }

    try:
        for unit, multiplier in multipliers.items():
            if value.endswith(unit):
                return float(value[:-len(unit)]) * multiplier
        return float(value) / (1024.0 * 1024.0)
    except ValueError:
        logger.debug("Unable to parse memory value '%s'", value)
        return 0


def _init_resource_result(cpu_threshold_millicores, memory_threshold_gb):
    return {
        "success": False,
        "pod_count": 0,
        "total_cpu_millicores": 0.0,
        "total_memory_mb": 0.0,
        "cpu_threshold_millicores": cpu_threshold_millicores,
        "memory_threshold_gb": memory_threshold_gb,
        "cpu_exceeded": False,
        "memory_exceeded": False,
        "error": None,
    }


def validate_helm_deployment_resources(namespace, cpu_threshold_millicores=2000, memory_threshold_gb=8):
    """Aggregate CPU and memory usage for pods in a namespace and compare to thresholds.
    
    Args:
        namespace: Kubernetes namespace to check
        cpu_threshold_millicores: CPU threshold in millicores (e.g., 2000 = 2 CPU cores)
        memory_threshold_gb: Memory threshold in GB
    """
    result = _init_resource_result(cpu_threshold_millicores, memory_threshold_gb)
    metrics_command = ["kubectl", "top", "pods", "-n", namespace]

    try:
        completed = subprocess.run(metrics_command, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        error_msg = getattr(exc, "stderr", "")
        error_msg = error_msg.strip() if isinstance(error_msg, str) else ""
        result["error"] = error_msg or str(exc)
        logger.error("Failed to collect resource metrics for namespace '%s': %s", namespace, result["error"])
        return result

    lines = [line for line in completed.stdout.strip().splitlines() if line.strip()]
    if len(lines) <= 1:
        result["error"] = f"No metrics data returned for namespace '{namespace}'"
        logger.warning(result["error"])
        return result

    for line in lines[1:]:
        columns = line.split()
        if len(columns) < 3:
            continue
        result["pod_count"] += 1
        result["total_cpu_millicores"] += _parse_cpu_to_millicores(columns[1])
        result["total_memory_mb"] += _parse_memory_to_mb(columns[2])

    if result["pod_count"] == 0:
        result["error"] = f"kubectl top returned no pod rows for namespace '{namespace}'"
        logger.warning(result["error"])
        return result

    memory_threshold_mb = memory_threshold_gb * 1024.0
    result["cpu_exceeded"] = result["total_cpu_millicores"] > cpu_threshold_millicores
    result["memory_exceeded"] = result["total_memory_mb"] > memory_threshold_mb
    result["success"] = not result["cpu_exceeded"] and not result["memory_exceeded"]

    if result["success"]:
        logger.info(
            "Resource usage within limits for namespace '%s' (CPU %.1fm / %.1fm, Memory %.1fMB / %.1fMB)",
            namespace,
            result["total_cpu_millicores"],
            cpu_threshold_millicores,
            result["total_memory_mb"],
            memory_threshold_mb,
        )
    else:
        result["error"] = result["error"] or "Resource usage exceeded thresholds"
        logger.warning(
            "Resource usage exceeded limits for namespace '%s' (CPU %.1fm / %.1fm, Memory %.1fMB / %.1fMB)",
            namespace,
            result["total_cpu_millicores"],
            cpu_threshold_millicores,
            result["total_memory_mb"],
            memory_threshold_mb,
        )

    return result


def verify_multimodal_core_components(namespace):
    """Ensure all multimodal core components have running pods in the namespace."""
    response = {
        "success": False,
        "missing_components": [],
        "unhealthy_components": {},
        "pods": {},
        "error": None,
    }

    components = constants.SAMPLE_APPS_CONFIG.get(constants.MULTIMODAL_SAMPLE_APP, {}).get("multimodal_container_list", [])
    if not components:
        response["error"] = "Multimodal container list is not defined"
        logger.error(response["error"])
        return response

    try:
        completed = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        response["error"] = exc.stderr.strip() if exc.stderr else str(exc)
        logger.error("Failed to inspect pods for namespace '%s': %s", namespace, response["error"])
        return response

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        response["error"] = f"Unable to parse kubectl response: {exc}"
        logger.error(response["error"])
        return response

    items = data.get("items", [])
    if not items:
        response["error"] = f"No pods found in namespace '{namespace}'"
        logger.warning(response["error"])
        return response

    for item in items:
        name = item.get("metadata", {}).get("name", "")
        phase = item.get("status", {}).get("phase", "Unknown")
        response["pods"][name] = phase

    def _aliases(component_name):
        base = component_name.replace("ia-", "")
        candidate_set = {
            component_name,
            base,
            base.replace("_", "-"),
            base.replace("_", ""),
        }
        if "_" in base:
            candidate_set.add(base.split("_", 1)[0])
        return [alias for alias in candidate_set if alias]

    for component in components:
        aliases = _aliases(component)
        matching = [
            name
            for name in response["pods"]
            if any(alias in name for alias in aliases)
        ]
        if not matching:
            response["missing_components"].append(component)
            continue

        unhealthy = [name for name in matching if response["pods"][name].lower() != "running"]
        if unhealthy:
            response["unhealthy_components"][component] = unhealthy

    response["success"] = not response["missing_components"] and not response["unhealthy_components"]
    if response["success"]:
        logger.info("All multimodal core components are running in namespace '%s'", namespace)
    else:
        if response["missing_components"]:
            logger.warning("Missing multimodal components in namespace '%s': %s", namespace, response["missing_components"])
        if response["unhealthy_components"]:
            logger.warning("Unhealthy multimodal components in namespace '%s': %s", namespace, response["unhealthy_components"])

    return response

def uninstall_helm_charts(release_name, namespace):
    """Check if a Helm release is installed in the specified namespace and uninstall it if found."""

    try:
        # List Helm releases in the specified namespace
        list_command = f"helm list -n {namespace} -q"
        result = subprocess.run(list_command, shell=True, capture_output=True, text=True, check=True)
        releases = result.stdout.strip().split()

        # Check if the release is present
        if release_name in releases:
            logger.info(f"Release '{release_name}' found in namespace '{namespace}'. Uninstalling...")
            uninstall_command = f"helm uninstall {release_name} -n {namespace}"
            subprocess.run(uninstall_command, shell=True, check=True)
            logger.info(f"Release '{release_name}' uninstalled successfully.")
            return True
        else:
            logger.info(f"Release '{release_name}' not found in namespace '{namespace}'. No action needed.")
            return True

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return False

def list_directory_contents():
    """List all files and directories in the current directory."""
    try:
        logger.info("Listing directory contents...")
        subprocess.run(["ls", "-al"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to list directory contents: {e}")
        return False
    return True

def fetch_influxdb_credentials(chart_path):
    """Fetch INFLUXDB_USERNAME and INFLUXDB_PASSWORD from values.yaml."""
    try:
        expanded_chart_path = os.path.expandvars(chart_path or "")
        if not expanded_chart_path:
            logger.error("Chart path is not provided for fetching InfluxDB credentials.")
            return None, None, None

        if expanded_chart_path.endswith(".yaml") and os.path.isfile(expanded_chart_path):
            values_yaml_path = expanded_chart_path
        else:
            values_yaml_path = os.path.join(expanded_chart_path, 'values.yaml')

        logger.info(f"Fetching InfluxDB credentials from: {values_yaml_path}")
    
        # Open and read the YAML file
        with open(values_yaml_path, 'r') as file:
            values = yaml.safe_load(file)

        # Extract the INFLUXDB_USERNAME and INFLUXDB_PASSWORD
        influxdb_username = values.get('env', {}).get('INFLUXDB_USERNAME')
        influxdb_password = values.get('env', {}).get('INFLUXDB_PASSWORD')
        influxdb_retention_duration = values.get('env', {}).get("INFLUXDB_RETENTION_DURATION")
        logger.info("Yaml file values: %s", values)
        # Print or return the values
        logger.info(f"INFLUXDB_USERNAME: {influxdb_username}")
        logger.info(f"INFLUXDB_PASSWORD: REDACTED")
        logger.info(f"INFLUXDB_RETENTION_DURATION: {influxdb_retention_duration}")
        if not influxdb_username or not influxdb_password or not influxdb_retention_duration:
            logger.error("InfluxDB credentials not found in values.yaml.")
            return None, None, None
        return influxdb_username, influxdb_password, influxdb_retention_duration
    except FileNotFoundError:
        logger.error(f"File not found: {values_yaml_path}")
        return None, None, None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, None, None

def _wait_for_pod_with_substring(namespace, substring, timeout=240, interval=5):
    """Wait for a pod whose name contains the provided substring."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pod_names = get_pod_names(namespace)
        for pod_name in pod_names:
            if substring in pod_name:
                logger.info("Found pod '%s' matching '%s'.", pod_name, substring)
                return pod_name
        logger.info(
            "Pod containing '%s' not ready yet in namespace '%s'. Retrying in %ss...",
            substring,
            namespace,
            interval,
        )
        time.sleep(interval)
    logger.error("Timed out after %ss waiting for pod containing '%s' in namespace '%s'.", timeout, substring, namespace)
    return None

def _wait_for_pod_ready(pod_name, namespace, timeout=180):
    """Block until the given pod reports Ready condition."""
    try:
        subprocess.run(
            [
                "kubectl",
                "wait",
                "-n",
                namespace,
                "--for=condition=Ready",
                f"pod/{pod_name}",
                f"--timeout={timeout}s",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        logger.error("Timeout while waiting for pod %s to become Ready: %s", pod_name, stderr)
        return False


def wait_for_mqtt_sample(namespace, topic=constants.WIND_TURBINE_INGESTED_TOPIC, timeout=180, interval=10):
    """Subscribe from inside the broker pod until a single message is observed on the topic."""
    pod_name = _wait_for_pod_with_substring(namespace, "mqtt-broker")
    if not pod_name:
        return False

    logger.info("Waiting for MQTT data on topic '%s' within namespace '%s'.", topic, namespace)
    deadline = time.time() + timeout
    wait_flag = str(max(1, min(30, int(interval))))

    while time.time() < deadline:
        command = [
            "kubectl",
            "exec",
            "-n",
            namespace,
            pod_name,
            "--",
            "mosquitto_sub",
            "-h",
            "localhost",
            "-v",
            "-t",
            topic,
            "-C",
            "1",
            "-W",
            wait_flag,
        ]

        result = subprocess.run(command, capture_output=True, text=True)
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            first_line = stdout.splitlines()[0]
            logger.info("Received MQTT sample on topic '%s': %s", topic, first_line)
            return True

        logger.info(
            "No MQTT sample observed yet on topic '%s' (rc=%s). Retrying in %ss...",
            topic,
            result.returncode,
            interval,
        )
        time.sleep(interval)

    logger.error(
        "Timed out after %ss waiting for MQTT data on topic '%s' in namespace '%s'.",
        timeout,
        topic,
        namespace,
    )
    return False


def verify_mqtt_alerts_via_subscription(namespace, alert_type, timeout=180, interval=15):
    """Verify MQTT alerts by subscribing directly to the alert topic on the MQTT broker."""
    pod_name = _wait_for_pod_with_substring(namespace, "mqtt-broker")
    if not pod_name:
        logger.error("MQTT broker pod not found in namespace '%s'", namespace)
        return False

    # Determine alert topic based on alert type
    if alert_type.lower() == "mqtt":
        alert_topic = "alerts/wind_turbine"
    elif alert_type.lower() == "mqtt_weld":
        alert_topic = "alerts/weld_defects"
    else:
        logger.error("Unknown alert type for MQTT subscription: %s", alert_type)
        return False

    logger.info(
        "Subscribing to MQTT alert topic '%s' in namespace '%s' (timeout=%ss)...",
        alert_topic,
        namespace,
        timeout,
    )
    deadline = time.time() + timeout
    wait_flag = str(max(1, min(30, int(interval))))

    while time.time() < deadline:
        command = [
            "kubectl",
            "exec",
            "-n",
            namespace,
            pod_name,
            "--",
            "mosquitto_sub",
            "-h",
            "localhost",
            "-v",
            "-t",
            alert_topic,
            "-C",
            "1",
            "-W",
            wait_flag,
        ]

        result = subprocess.run(command, capture_output=True, text=True, timeout=interval + 5)
        stdout = result.stdout.strip()
        
        if result.returncode == 0 and stdout:
            # Alert received
            logger.info("✓ MQTT alert received on topic '%s': %s", alert_topic, stdout[:200])
            return True

        remaining = int(deadline - time.time())
        logger.info(
            "No alert on topic '%s' yet (rc=%s). Remaining time: %ss. Retrying...",
            alert_topic,
            result.returncode,
            remaining,
        )
        
        if remaining <= 0:
            break
            
        time.sleep(min(interval, remaining))

    logger.error(
        "Timed out after %ss waiting for MQTT alerts on topic '%s' in namespace '%s'.",
        timeout,
        alert_topic,
        namespace,
    )
    return False


def verify_influxdb_connectivity(namespace, chart_path):
    """Verify basic InfluxDB connectivity without strict data validation (08Weekly aligned approach)."""
    logger.info(f"Verifying InfluxDB connectivity in namespace '{namespace}'...")
    try:
        # Get credentials
        influxdb_username, influxdb_password, _ = fetch_influxdb_credentials(chart_path)
        if not influxdb_username or not influxdb_password:
            logger.error("InfluxDB credentials missing from chart values.")
            return False

        # Find InfluxDB pod
        pod_name = _wait_for_pod_with_substring(namespace, "influxdb")
        if not pod_name:
            logger.error("InfluxDB pod not found")
            return False

        # Wait for pod to be ready
        if not _wait_for_pod_ready(pod_name, namespace):
            logger.error("InfluxDB pod not ready")
            return False

        # Simple connectivity test - just show measurements (doesn't require data)
        command = [
            "kubectl", "exec", "-n", namespace, pod_name, "--",
            "influx",
            "-username", influxdb_username,
            "-password", influxdb_password, 
            "-database", constants.INFLUXDB_DATABASE,
            "-execute", "SHOW MEASUREMENTS"
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"InfluxDB connectivity test failed: {result.stderr}")
            return False
            
        logger.info("InfluxDB connectivity verified successfully")
        return True
        
    except Exception as e:
        logger.error(f"InfluxDB connectivity verification failed: {e}")
        return False


def execute_influxdb_commands(namespace, chart_path, sample_app=constants.WIND_SAMPLE_APP):
    """Execute InfluxDB commands inside the InfluxDB pod."""
    logger.info(f"Executing InfluxDB commands in namespace '{namespace}'...")
    try:
        influxdb_username, influxdb_password, _ = fetch_influxdb_credentials(chart_path)
        if not influxdb_username or not influxdb_password:
            logger.error("InfluxDB credentials missing from chart values. Aborting validation.")
            return False

        pod_name = _wait_for_pod_with_substring(namespace, "influxdb")
        if not pod_name:
            return False

        if not _wait_for_pod_ready(pod_name, namespace):
            return False

        if sample_app == constants.WIND_SAMPLE_APP:
            measurements = (
                constants.WIND_TURBINE_INGESTED_TOPIC,
                constants.WIND_TURBINE_ANALYTICS_TOPIC,
            )
        elif sample_app == constants.WELD_SAMPLE_APP:
            measurements = (
                constants.WELD_INGESTED_TOPIC,
                constants.WELD_ANALYTICS_TOPIC,
            )
        else:
            logger.error("Unknown sample app '%s' for InfluxDB validation.", sample_app)
            return False

        def _run_influx(query):
            command = [
                "kubectl",
                "exec",
                "-n",
                namespace,
                pod_name,
                "--",
                "influx",
                "-username",
                influxdb_username,
                "-password",
                influxdb_password,
                "-database",
                constants.INFLUXDB_DATABASE,
                "-execute",
                query,
            ]
            return subprocess.run(command, capture_output=True, text=True, check=True).stdout

        # Wait for measurements to appear with retry logic (similar to alert verification)
        max_measurement_attempts = 12  # 12 attempts * 15 seconds = 3 minutes
        measurement_retry_delay = 15
        measurements_output = ""
        measurement_names = set()
        
        logger.info(f"Waiting for measurements to appear in InfluxDB (timeout: {max_measurement_attempts * measurement_retry_delay}s)...")
        for attempt in range(1, max_measurement_attempts + 1):
            try:
                measurements_output = _run_influx("SHOW MEASUREMENTS")
                measurement_names = set(_parse_measurement_names(measurements_output))
                missing = [name for name in measurements if name not in measurement_names]
                
                if not missing:
                    logger.info(f"All expected measurements found in InfluxDB on attempt {attempt}/{max_measurement_attempts}")
                    break
                    
                logger.info(
                    f"Measurement check attempt {attempt}/{max_measurement_attempts}: "
                    f"Found {len(measurement_names)} measurements, missing: {', '.join(missing)}"
                )
                
                if attempt < max_measurement_attempts:
                    logger.info(f"Waiting {measurement_retry_delay}s for data pipeline to populate measurements...")
                    time.sleep(measurement_retry_delay)
                    
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip() if exc.stderr else str(exc)
                logger.warning(f"Failed to query measurements (attempt {attempt}/{max_measurement_attempts}): {stderr}")
                if attempt < max_measurement_attempts:
                    time.sleep(measurement_retry_delay)
                else:
                    logger.error("Failed to query measurements from InfluxDB after all retries")
                    return False
        else:
            # Loop completed without break - measurements still missing
            missing = [name for name in measurements if name not in measurement_names]
            logger.error(
                f"Missing measurements in database '{constants.INFLUXDB_DATABASE}' after {max_measurement_attempts} attempts: {', '.join(missing)}"
            )
            logger.debug("SHOW MEASUREMENTS output:\n%s", measurements_output)
            return False

        counts = {}
        max_attempts = 6
        retry_delay = 10
        for measurement in measurements:
            query = f'SELECT COUNT(*) FROM "{measurement}"'
            last_output = ""
            for attempt in range(1, max_attempts + 1):
                try:
                    result_output = _run_influx(query)
                except subprocess.CalledProcessError as exc:
                    stderr = exc.stderr.strip() if exc.stderr else str(exc)
                    logger.error(
                        "Failed to query measurement '%s' (attempt %d/%d): %s",
                        measurement,
                        attempt,
                        max_attempts,
                        stderr,
                    )
                    return False

                last_output = result_output
                row_count = _extract_influx_count(result_output)
                logger.info(
                    "Measurement '%s' count attempt %d/%d: %s",
                    measurement,
                    attempt,
                    max_attempts,
                    row_count,
                )
                if row_count > 0:
                    counts[measurement] = row_count
                    break

                if attempt < max_attempts:
                    logger.info(
                        "No data yet for '%s'. Sleeping %ss before next query...",
                        measurement,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
            else:
                logger.error(
                    "Measurement '%s' did not return any rows after %d attempts.",
                    measurement,
                    max_attempts,
                )
                logger.debug("Last query output for '%s':\n%s", measurement, last_output)
                return False

        logger.info("InfluxDB validation successful. Measurement counts: %s", counts)
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return False


def _parse_measurement_names(raw_output):
    names = []
    if not raw_output:
        return names

    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("name") or set(stripped) == {"-"}:
            continue
        names.append(stripped.split()[0])
    return names


def _extract_influx_count(raw_output):
    if not raw_output:
        return 0

    for line in reversed(raw_output.strip().splitlines()):
        tokens = line.split()
        for token in reversed(tokens):
            if token.replace('.', '', 1).isdigit():
                try:
                    return int(float(token))
                except ValueError:
                    continue
    return 0


def verify_multimodal_influxdb_data(chart_path, namespace=None, database=constants.INFLUXDB_DATABASE):
    """Validate InfluxDB connectivity and data for the multimodal deployment."""
    result = {
        "success": False,
        "connectivity": False,
        "measurements_found": False,
        "data_found": False,
        "vision_data_count": 0,
        "sensor_data_count": 0,
        "total_measurements": 0,
        "measurements_output": "",
        "pod_name": None,
        "error": None,
    }

    resolved_chart = _resolve_path_under_repo(chart_path) if chart_path else chart_path
    chart_for_credentials = resolved_chart or chart_path
    if chart_for_credentials and not chart_for_credentials.endswith(os.sep):
        chart_for_credentials = chart_for_credentials + os.sep

    if namespace is None:
        try:
            (_functional_path,
             _release_name_multi,
             _release_name_weld_multi,
             _chart_path_multi,
             env_namespace,
             _grafana_url_multi,
             _wait_time_multi,
             _target_multi,
             _proxy_url_multi,) = get_multimodal_env_values()
            namespace = env_namespace
        except Exception:
            namespace = os.getenv("namespace_multi") or globals().get("namespace")

    if not namespace:
        namespace = "multimodal-sample-app"

    credentials = fetch_influxdb_credentials(chart_for_credentials) if chart_for_credentials else (None, None, None)
    if not credentials or not credentials[0] or not credentials[1]:
        result["error"] = "InfluxDB credentials not found in chart values"
        logger.error(result["error"])
        return result

    influxdb_username, influxdb_password, _ = credentials

    # Find the first InfluxDB pod in the given namespace without using a shell pipeline
    pod_proc = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
    )
    pod_name = ""
    if pod_proc.returncode == 0:
        try:
            pods_data = json.loads(pod_proc.stdout)
            for item in pods_data.get("items", []):
                name = item.get("metadata", {}).get("name", "")
                if "influxdb" in name:
                    pod_name = name
                    break
        except json.JSONDecodeError:
            result["error"] = f"Failed to parse kubectl pod list JSON for namespace '{namespace}'"
            logger.error(result["error"])
            return result

    if not pod_name:
        result["error"] = f"Unable to locate InfluxDB pod in namespace '{namespace}'"
        logger.error(result["error"])
        return result

    result["pod_name"] = pod_name

    def _exec_influx(query):
        exec_command = [
            "kubectl", "exec", "-n", namespace, pod_name, "--",
            "influx",
            "-username", influxdb_username,
            "-password", influxdb_password,
            "-database", database,
            "-execute", query,
        ]
        return subprocess.run(exec_command, capture_output=True, text=True, check=True).stdout

    try:
        measurements_output = _exec_influx("SHOW MEASUREMENTS")
        result["measurements_output"] = measurements_output
        result["connectivity"] = True
    except subprocess.CalledProcessError as exc:
        result["error"] = f"Failed to query InfluxDB measurements: {exc.stderr.strip() if exc.stderr else exc}"
        logger.error(result["error"])
        return result

    measurement_names = _parse_measurement_names(result["measurements_output"])
    result["measurements_found"] = bool(measurement_names)

    mm_config = constants.get_app_config(constants.MULTIMODAL_SAMPLE_APP) or {}
    sensor_measurement = (
        constants.get_app_influxdb_measurement(constants.MULTIMODAL_SAMPLE_APP)
        or mm_config.get("ingested_topic")
        or "weld-sensor-data"
    )
    vision_measurement = (
        constants.get_app_vision_measurement(constants.MULTIMODAL_SAMPLE_APP)
        or mm_config.get("vision_measurement")
        or "vision-weld-classification-results"
    )

    for key, measurement in (("sensor_data_count", sensor_measurement), ("vision_data_count", vision_measurement)):
        if not measurement:
            continue
        try:
            count_output = _exec_influx(f"SELECT COUNT(*) FROM \"{measurement}\"")
            result[key] = _extract_influx_count(count_output)
        except subprocess.CalledProcessError as exc:
            logger.warning("Failed to query measurement '%s': %s", measurement, exc.stderr.strip() if exc.stderr else exc)

    result["total_measurements"] = result["sensor_data_count"] + result["vision_data_count"]
    result["data_found"] = result["total_measurements"] > 0
    result["success"] = result["connectivity"] and result["measurements_found"] and result["data_found"]

    if result["success"]:
        logger.info(
            "✅ Verified InfluxDB data for multimodal deployment (sensor=%s, vision=%s)",
            result["sensor_data_count"],
            result["vision_data_count"],
        )
    else:
        if not result["measurements_found"]:
            result["error"] = result["error"] or "No measurements returned from InfluxDB"
        elif not result["data_found"]:
            result["error"] = result["error"] or "InfluxDB measurements returned zero records"
        logger.warning(result["error"] or "Multimodal InfluxDB data verification failed")

    return result


def query_influxdb_measurement_via_kubectl(
    namespace,
    measurement,
    username,
    password,
    database=constants.INFLUXDB_DATABASE,
    limit=3,
    pod_name=None,
    timeout=30,
    order_by_time_desc=False,
):
    """Query an InfluxDB measurement inside the cluster and return parsed rows."""
    result = {
        "success": False,
        "records": [],
        "raw_output": "",
        "error": None,
        "pod_name": pod_name,
    }

    namespace = namespace or os.getenv("namespace_multi") or os.getenv("namespace")
    if not namespace:
        result["error"] = "Namespace is required to query InfluxDB"
        logger.error(result["error"])
        return result

    if not pod_name:
        pod_name = _wait_for_pod_with_substring(namespace, "influxdb", timeout=max(timeout, 60))
    if not pod_name:
        result["error"] = f"Unable to locate InfluxDB pod in namespace '{namespace}'"
        logger.error(result["error"])
        return result

    # Ensure pod is actually Ready before issuing kubectl exec
    readiness_timeout = max(timeout, 60)
    if not _wait_for_pod_ready(pod_name, namespace, timeout=readiness_timeout):
        result["error"] = (
            f"InfluxDB pod '{pod_name}' in namespace '{namespace}' did not become ready"
        )
        logger.error(result["error"])
        return result

    result["pod_name"] = pod_name
    order_clause = " ORDER BY time DESC" if order_by_time_desc else ""
    query = f'SELECT * FROM "{measurement}"{order_clause} LIMIT {limit}'
    cmd = [
        "kubectl", "exec", "-n", namespace, pod_name, "--",
        "influx",
        "-username", username,
        "-password", password,
        "-database", database,
        "-format", "json",
        "-execute", query,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        result["raw_output"] = proc.stdout.strip()
        if proc.returncode != 0:
            stderr = proc.stderr.strip() if proc.stderr else "Unknown error"
            result["error"] = f"InfluxDB query failed: {stderr}"
            logger.error(result["error"])
            return result

        json_payload = _extract_influx_json(result["raw_output"])
        if not json_payload:
            result["error"] = "InfluxDB response did not contain JSON payload"
            logger.error(result["error"])
            return result

        data = json.loads(json_payload)
        series = data.get("results", [{}])[0].get("series", [])
        if series:
            columns = series[0].get("columns", [])
            values = series[0].get("values", [])
            result["records"] = [dict(zip(columns, row)) for row in values]
            result["success"] = bool(result["records"])
        else:
            result["error"] = f"No data returned for measurement {measurement}"
            logger.warning(result["error"])

    except subprocess.TimeoutExpired:
        result["error"] = f"InfluxDB query timed out after {timeout} seconds"
        logger.error(result["error"])
    except json.JSONDecodeError as exc:
        result["error"] = f"Failed to parse InfluxDB JSON output: {exc}"
        logger.error(result["error"])
    except Exception as exc:
        result["error"] = f"Unexpected error querying InfluxDB: {exc}"
        logger.error(result["error"])

    return result


def _extract_influx_json(cli_output):
    """Return the first JSON document from influx cli output."""
    if not cli_output:
        return None
    for line in cli_output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return line
    return None


def parse_duration(duration):
    """Convert a duration string in the format 'XhYmZs' to seconds."""
    hours = 0
    minutes = 0
    seconds = 0

    # Parse the duration string
    if 'h' in duration:
        hours = int(duration.split('h')[0])
        duration = duration.split('h')[1]
    if 'm' in duration:
        minutes = int(duration.split('m')[0])
        duration = duration.split('m')[1]
    if 's' in duration:
        seconds = int(duration.split('s')[0])

    # Calculate total seconds
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds

def verify_influxdb_retention(namespace, chart_path, response):
    """Execute InfluxDB commands inside the InfluxDB pod."""
    logger.info(f"Executing InfluxDB commands in namespace '{namespace}'...")
    try:
        # Step 1: Identify the InfluxDB pod
        influxdb_username, influxdb_password, influxdb_retention_duration = fetch_influxdb_credentials(chart_path)
        pod_name_command = (
            f"kubectl get pods -n {namespace} "
            "-o jsonpath='{.items[*].metadata.name}' | tr ' ' '\\n' | grep influxdb | head -n 1"
        )
        result = subprocess.run(pod_name_command, shell=True, capture_output=True, text=True, check=True)
        pod_name = result.stdout.strip()

        if not pod_name:
            logger.error("InfluxDB pod not found.")
            return False

        logger.info(f"InfluxDB pod found: {pod_name}")

        # Step 2: Execute InfluxDB commands inside the pod
        influx_commands = (
            f"influx -username {influxdb_username} -password {influxdb_password} -database datain "
            f"-execute 'SELECT time, wind_speed FROM {constants.WIND_TURBINE_INGESTED_TOPIC} ORDER BY time ASC LIMIT 1'  | awk 'NR==4 {{print $1}}'"
        )

        exec_command = f"kubectl exec -n {namespace} {pod_name} -- {influx_commands}"
        logger.info(f"Executing InfluxDB query inside pod '{pod_name}': 'SELECT time, wind_speed FROM {constants.WIND_TURBINE_INGESTED_TOPIC} ORDER BY time ASC LIMIT 1;' with redacted credentials.")
        result = subprocess.run(exec_command, shell=True, capture_output=True, text=True, check=True)
        response = result.stdout.strip()

        if response:
            logger.info(f"First time value in '{constants.WIND_TURBINE_INGESTED_TOPIC}':", response)
            return response, True
        else:
            logger.error(f"No time data found in '{constants.WIND_TURBINE_INGESTED_TOPIC}'.")
            return None, False
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e.stderr}")
        return None, False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, False

def generate_helm_chart(chart_path, sample_app=constants.WIND_SAMPLE_APP):
    """Run make gen_helm_chart in the parent directory."""
    original_dir = os.getcwd()
    try:
        
        os.chdir(chart_path)
        os.chdir("../")
        list_directory_contents()

        # Run the make command
        logger.info("Generating Helm chart...")
        result = subprocess.run(["make", "gen_helm_charts", "app=" + sample_app], capture_output=True, text=True, check=True)
        logger.info(result.stdout)
        logger.info("Helm chart generated successfully.")
        list_directory_contents()

        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate Helm chart: {e.stderr}")
        return False
    finally:
        os.chdir(original_dir)
        logger.info(f"Restored working directory to: {os.getcwd()}")

def helm_install(release_name, chart_path, namespace, telegraf_input_plugin, continuous_simulator_ingestion="True", val="false", sample_app=None):
    """Install a Helm chart with specified parameters."""
    try:
        # Construct the Helm install command
        helm_command = [
            "helm", "install", release_name, chart_path,
            "--set", f"env.privileged_access_required={val}",
            "--set", f"env.TELEGRAF_INPUT_PLUGIN={telegraf_input_plugin}",
            "--set", f"env.CONTINUOUS_SIMULATOR_INGESTION={continuous_simulator_ingestion}",
            "-n", namespace, "--create-namespace"
        ]
        
        # Add SAMPLE_APP if provided (critical for matching UDF package name)
        if sample_app:
            helm_command.extend(["--set", f"env.SAMPLE_APP={sample_app}"])

        # Execute the Helm install command and capture output
        logger.info(f"Installing Helm chart with {telegraf_input_plugin}...")
        result = subprocess.run(helm_command, capture_output=True, text=True, check=True)

        # Print the output for debugging purposes
        logger.info(result.stdout)
        
        # Configuration will be handled by setup_sample_app_udf_deployment_package() using TS API
        # as recommended in the documentation instead of directly updating ConfigMaps
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Helm chart: Error: INSTALLATION FAILED: values don't meet the specifications of the schema(s) in the following chart(s): {e.stderr}")
        return False

def helm_uninstall(release_name, namespace):
    """Uninstall a Helm release with specified parameters."""
    try:
        # Construct the Helm uninstall command
        helm_command = [
            "helm", "uninstall", release_name,
            "-n", namespace
        ]

        # Execute the Helm uninstall command and capture output
        logger.info(f"Uninstalling Helm release '{release_name}' from namespace '{namespace}'...")
        result = subprocess.run(helm_command, capture_output=True, text=True, check=True)

        # Print the output for debugging purposes
        logger.info(result.stdout)
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to uninstall Helm release: Error: uninstall: Release not loaded: ts-wind-turbine-anomaly: release: not found: {e.stderr}")
        return False

def helm_upgrade(release_name, chart_path, namespace, telegraf_input_plugin1):
    """Upgrade a Helm release with specified parameters."""
    try:
        # Construct the Helm upgrade command
        helm_command = [
            "helm", "upgrade", release_name, chart_path,
            "--set", f"env.TELEGRAF_INPUT_PLUGIN={telegraf_input_plugin1}",
            "-n", namespace
        ]

        # Execute the Helm upgrade command and capture output
        logger.info(f"Upgrading Helm release '{release_name}'...")
        result = subprocess.run(helm_command, capture_output=True, text=True, check=True)

        # Print the output for debugging purposes
        logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to upgrade Helm release: {e.stderr}")
        return False

def get_pod_names(namespace):
    """Fetch pod names in the given namespace."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "jsonpath={.items[*].metadata.name}"],
            capture_output=True, text=True, check=True
        )
        
        #pod_name = next((name for name in pod_names if 'timeseries' in name or 'telegraf' in name), None)
        pod_names = result.stdout.strip().split()
        return pod_names
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fetch pod names: {e}")
        return []

def check_pod_logs_for_errors(namespace, pod_name):
    """Check pod logs for errors."""
    try:
        result = subprocess.run(
            ["kubectl", "logs", pod_name, "-n", namespace, "--tail=5"],
            capture_output=True, text=True, check=True
        )
        logs = result.stdout.strip()
       
        # Filter out benign warnings that should not be treated as errors
        benign_patterns = [
            "WARNING: Retrying",  # PyPI connection retry warnings
            "ConnectTimeoutError",  # PyPI connection timeout warnings
            "Connection to pypi.org timed out",  # Specific PyPI timeout message
            "The directory '/.cache/pip' or its parent directory is not owned",  # pip cache warning
            "error while sending usage report",  # Kapacitor telemetry timeout (benign)
            "usage.influxdata.com",  # InfluxData usage reporting endpoint timeout
        ]
        
        # Check if "error" exists in logs (case-insensitive)
        logs_lower = logs.lower()
        if "error" in logs_lower:
            # Check if it's a benign warning that should be ignored (case-insensitive)
            is_benign = any(pattern.lower() in logs_lower for pattern in benign_patterns)
            
            if is_benign:
                logger.info(f"Benign pip warnings found in logs for pod {pod_name} (expected during package installation). Logs:\n{logs}")
                return True
            else:
                logger.error(f"Error found in logs for pod {pod_name}:")
                logger.error(logs)
                return False
        else:
            logger.info(f"No errors found in logs for pod {pod_name}. Logs:\n{logs}")
            return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fetch logs for pod {pod_name}: {e}")
        return False
def restart_deployment(namespace, pod):
    """List deployments and restart the 'opcua-server' deployment in the specified namespace."""
    try:
        # List deployments in the specified namespace
        logger.info(f"Listing deployments in namespace '{namespace}':")
        list_command = f"kubectl get deployments -n {namespace}"
        subprocess.run(list_command, shell=True, check=True)

        # Get deployment names using jsonpath
        list_names_command = f"kubectl get deployments -n {namespace} -o jsonpath='{{.items[*].metadata.name}}'"
        result = subprocess.run(list_names_command, shell=True, capture_output=True, text=True, check=True)
        
        # Get the list of deployment names
        deployments = result.stdout.strip().split()

        # Check if pod is in the list of deployments
        if f"deployment-{pod}" in deployments:
            logger.info(f"Found pod deployment '{pod}'. Restarting...")
            restart_command = f"kubectl rollout restart deployments 'deployment-{pod}' -n {namespace}"
            subprocess.run(restart_command, shell=True, check=True)
            logger.info(f"'{pod}' deployment restarted successfully.")
            return True
        else:
            logger.info(f"'{pod}' deployment not found in namespace.")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return False

def with_model_registry(chart_path, input):
    """Check time-series pod after model registry is enabled in the configuration."""
    original_dir = os.getcwd()
    try:
        # Step 1: Create a ZIP archive
        if input == "mqtt":
            assert setup_mqtt_alerts(chart_path) == True
            logger.info("MQTT alerts setup in tick script completed successfully.")
        elif input == "opcua":
            assert setup_opcua_alerts(chart_path) == True
            logger.info("OPC UA alerts setup in tick script completed successfully.")
        os.chdir(chart_path)
        os.chdir('../' + constants.HELM_TIMESERIES)
         # Create the directory
        os.makedirs('wind-turbine-anomaly-detection', exist_ok=True)

        # Copy the files into the new directory
        logger.info("Copying files to 'wind-turbine-anomaly-detection' directory...")
        result = subprocess.run(['cp', '-r', 'models', 'tick_scripts', 'udfs', 'wind-turbine-anomaly-detection/.'], check=True)
        if result.stdout:
            logger.info("Files copied successfully to 'wind-turbine-anomaly-detection' directory.")
        elif result.stderr:
            logger.error(f"Error copying files: {result.stderr.decode('utf-8')}")
        tar_command = f"tar cf windturbine_anomaly_detector.tar udfs models tick_scripts"
        result = subprocess.run(tar_command, shell=True, capture_output=True, text=True, check=True)
        logger.info("TAR archive created successfully.")
        if result.stdout:
            logger.info(f"TAR command output: {result.stdout}")
        if result.stderr:
            logger.error(f"TAR command stderr: {result.stderr}")
        

        # Step 2: Upload the tar file using kubectl exec to avoid port-forwarding
        # Find the model registry pod
        model_registry_pod_command = (
            f"kubectl get pods -n {namespace} "
            "-o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | "
            "grep model-registry | head -n 1"
        )
        result = subprocess.run(model_registry_pod_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0 and result.stdout:
            model_registry_pod = result.stdout.decode('utf-8').strip().replace("'", "")
            logger.info(f"Found model registry pod: {model_registry_pod}")
        else:
            logger.error("Model registry pod not found.")
            return False

        # Copy the TAR file to the model registry pod first
        kubectl_cp_command = [
            'kubectl', 'cp', 'windturbine_anomaly_detector.tar',
            f'{model_registry_pod}:/tmp/windturbine_anomaly_detector.tar',
            '-n', namespace
        ]
        logger.info(f"Copying TAR file to model registry pod: {' '.join(kubectl_cp_command)}")
        result = subprocess.run(kubectl_cp_command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Error copying TAR file to pod: {result.stderr}")
            return False

        # Upload using curl from within the pod (in-cluster call)
        upload_command = [
            'kubectl', 'exec', model_registry_pod, '-n', namespace, '--',
            'curl', '-L', '-X', 'POST', 'http://localhost:8080/models',
            '-H', 'Content-Type: multipart/form-data',
            '-F', 'name="windturbine_anomaly_detector"',
            '-F', 'version="1.0"',
            '-F', 'file=@/tmp/windturbine_anomaly_detector.tar;type=application/x-tar'
        ]
        logger.info(f"Uploading model via kubectl exec: {' '.join(upload_command)}")
        result = subprocess.run(upload_command, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Model upload command output: {result.stdout}")
            logger.info("Model uploaded successfully.")
        else:
            logger.error(f"Model upload command errors: {result.stderr}")

        # Step 3: Send configuration update using kubectl exec
        config_payload1 = json.dumps({
            "model_registry": {
                "enable": True,
                "version": "1.0"
            },
            "udfs": {
                "name": constants.WIND_UDF,
                "models": constants.WIND_MODEL
            },
            "alerts": {
                "mqtt": {
                    "mqtt_broker_host": constants.CONTAINERS["mqtt_broker"]["name"],
                    "mqtt_broker_port": constants.CONTAINERS["mqtt_broker"]["port"],
                    "name": "my_mqtt_broker"
                }
            }
        })
        
        config_payload2 = json.dumps({
            "model_registry": {
                "enable": True,
                "version": "1.0"
            },
            "udfs": {
                "name": constants.WIND_UDF,
                "models": constants.WIND_MODEL
            },
            "alerts": {
                "opcua": {
                    "opcua_server": "opc.tcp://ia-opcua-server:4840/freeopcua/server/",
                    "namespace": 1,
                    "node_id": 2004
                }
            }
        })
        logger.info(f"Sending configuration update command based on input: {input}")
        # Execute the configuration update command using kubectl exec instead of port forwarding
        if input == "mqtt":
            success = _post_ts_api_config(payload=config_payload1, method="POST")
            if success:
                logger.info("Configuration for mqtt updated successfully via kubectl exec")
                return True
            else:
                logger.error("Failed to update mqtt configuration via kubectl exec")
                return False

        elif input == "opcua":
            success = _post_ts_api_config(payload=config_payload2, method="POST")
            if success:
                logger.info("Configuration for opcua updated successfully via kubectl exec")
                return True
            else:
                logger.error("Failed to update opcua configuration via kubectl exec")
                return False

        # If input is neither mqtt nor opcua, return False
        else:
            logger.error("Invalid input. Please enter 'mqtt' or 'opcua'.")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return False
    finally:
        os.chdir(original_dir)
        logger.info(f"Restored working directory to: {os.getcwd()}")

def verify_pods_logs(namespace, log_type):
    """Verify logs for all pods in the namespace."""
    pod_names = get_pod_names(namespace)
    if not pod_names:
        logger.error("No pods found or failed to fetch pod names.")
        return False

        
    # Filter pod names to include only those containing 'timeseries' or 'telegraf'
    relevant_pod_names = [name for name in pod_names if 'time-series' in name or 'telegraf' in name or 'influxdb' in name]

    if not relevant_pod_names:
        logger.error("No relevant pods found containing 'time-series' or 'telegraf' or 'influxdb'.")
        return False
    all_logs_ok = True

    for pod_name in relevant_pod_names:
        if not check_pod_logs_for_errors(namespace, pod_name):
            all_logs_ok = False

    if all_logs_ok:
        logger.info("All pod logs are clean.")
        return True
    else:
        logger.error("Errors found in pod logs.")
        return False

def verify_ts_logs(namespace, log_type):
    """Verify logs for all pods in the namespace."""
    pod_names = get_pod_names(namespace)
    if not pod_names:
        logger.error("No pods found or failed to fetch pod names.")
        return False

    # Filter pod names to include only those containing 'time-series'
    relevant_pod_names = [name for name in pod_names if 'time-series' in name]

    if not relevant_pod_names:
        logger.error("No relevant pods found containing 'time-series'.")
        return False
    all_logs_ok = True

    for pod_name in relevant_pod_names:
        if not common_utils.check_logs_by_level(pod_name, log_type, "pod", namespace, tail_lines=200):
            all_logs_ok = False

    if all_logs_ok:
        logger.info("All pod logs are clean.")
        return True
    else:
        logger.error("Errors found in pod logs.")
        return False
    
     
def verify_ts_logs_alerts(namespace, alert_type):
    """Verify alerts by subscribing to MQTT broker or checking logs."""
    
    # For MQTT alerts, try subscribing to the MQTT broker directly first
    if alert_type.lower() in ["mqtt", "mqtt_weld"]:
        logger.info("Attempting to verify MQTT alerts via broker subscription...")
        if verify_mqtt_alerts_via_subscription(namespace, alert_type):
            logger.info("MQTT alerts verified via broker subscription.")
            return True
        logger.warning("Direct MQTT subscription check failed, falling back to log verification...")
    
    # Fall back to log checking
    pod_names = get_pod_names(namespace)
    if not pod_names:
        logger.error("No pods found or failed to fetch pod names.")
        return False

    # Filter pod names to include only those containing 'time-series'
    relevant_pod_names = [name for name in pod_names if 'time-series' in name]

    if not relevant_pod_names:
        logger.error("No relevant pods found containing 'time-series'.")
        return False
    alerts_found = False

    for pod_name in relevant_pod_names:
        logger.info("Checking pod %s for %s alerts...", pod_name, alert_type)
        if common_utils.check_logs_for_alerts(pod_name, alert_type, "pod", namespace):
            logger.info("Alerts detected in pod %s.", pod_name)
            alerts_found = True
            break
        logger.info("No %s alerts detected in pod %s. Continuing...", alert_type, pod_name)

    if alerts_found:
        logger.info("At least one time-series pod emitted %s alerts.", alert_type)
        return True

    logger.error(
        "No %s alerts detected in any time-series pod within namespace '%s'.",
        alert_type,
        namespace,
    )
    return False


def _get_time_series_pod_name(target_namespace=None):
    """Return the first time-series analytics pod name in the target namespace."""
    ns = target_namespace or namespace
    cmd = ["kubectl", "get", "pods", "-n", ns, "-o", "json"]
    result = subprocess.run(
        cmd,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        logger.error(f"Unable to fetch time-series pod name: {stderr}")
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse kubectl pods JSON output: {e}")
        return None

    pod_name = None
    for item in data.get("items", []):
        name = item.get("metadata", {}).get("name", "")
        if "deployment-time-series-analytics-microservice" in name:
            pod_name = name
            break

    if not pod_name:
        logger.error("Time Series Analytics pod not found.")
        return None

    return pod_name


def _post_ts_api_config(
    payload,
    target_namespace=None,
    pod_name=None,
    endpoint=None,
    method="POST",
    max_attempts=3,
    delay_seconds=5,
):
    """Execute a ts-api call via external nginx proxy (exactly like Docker does)."""
    ns = target_namespace or namespace
    
    target_endpoint = endpoint or "https://localhost:30001/ts-api/config"
    http_method = method.upper()
    
    # Build curl command to run from test machine (NOT inside pod)
    curl_command = [
        'curl', '-k', '-X', http_method, target_endpoint,
        '-H', 'accept: application/json',
        '-H', 'Content-Type: application/json'
    ]

    if payload and http_method in {"POST", "PUT", "PATCH", "DELETE"}:
        curl_command.extend(['-d', payload])

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Executing Time Series API request (attempt %d/%d) via external nginx: %s",
            attempt,
            max_attempts,
            " ".join(curl_command),
        )
        
        try:
            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
        except subprocess.SubprocessError as exc:
            logger.error(f"Failed to execute ts-api request: {exc}")
            result = None

        if result and result.returncode == 0:
            logger.info("ts-api request completed successfully. Response:")
            logger.info(result.stdout.strip())
            logger.info("Waiting 5 seconds for configuration to be processed...")
            time.sleep(5)
            return True

        logger.warning("ts-api request attempt %d failed.", attempt)
        if result:
            stderr = result.stderr.strip()
            if stderr:
                logger.warning(stderr)

        if attempt < max_attempts:
            logger.info(
                "Waiting %d seconds before retrying ts-api request...",
                delay_seconds,
            )
            time.sleep(delay_seconds)

    logger.error("ts-api request failed after %d attempts.", max_attempts)
    return False


def _restart_ts_api_config(target_namespace=None, pod_name=None):
    """Invoke the ts-api restart endpoint to reload alert/UDF config via external nginx."""
    restart_endpoint = "https://localhost:30001/ts-api/config?restart=true"
    result = _post_ts_api_config(
        payload=None,
        target_namespace=target_namespace,
        pod_name=pod_name,
        endpoint=restart_endpoint,
        method="GET",
        max_attempts=2,
        delay_seconds=5
    )
    if result:
        logger.info("Configuration restart successful. Waiting 45 seconds for microservice to fully restart and activate UDF...")
        time.sleep(45)
    else:
        logger.warning("Configuration restart failed, waiting 15 seconds before continuing...")
        time.sleep(15)
    return result
        

def setup_sample_app_udf_deployment_package(
    chart_path,
    sample_app=constants.WIND_SAMPLE_APP,
    device_value="cpu",
    alert_mode="mqtt",
    target_namespace=None,
):
    """Package and activate the sample app UDF bundle following the documented Helm workflow."""
    ns = target_namespace or namespace
    try:
        config_dir = _get_sample_app_config_dir(chart_path, sample_app)
        if not config_dir:
            return False

        pod_name = _get_time_series_pod_name(ns)
        if not pod_name:
            return False

        try:
            package_dir, staging_root = _stage_udf_package(config_dir, sample_app)
        except Exception as exc:
            logger.error("Failed to stage UDF package for '%s': %s", sample_app, exc)
            return False

        try:
            kubectl_cp_command = [
                "kubectl",
                "cp",
                str(package_dir),
                f"{pod_name}:/tmp/",
                "-n",
                ns,
            ]
            logger.info(
                "Copying '%s' package from %s to pod %s in namespace %s",
                sample_app,
                package_dir,
                pod_name,
                ns,
            )
            result = subprocess.run(kubectl_cp_command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(
                    "Error copying '%s' to pod %s: %s",
                    sample_app,
                    pod_name,
                    result.stderr.strip(),
                )
                return False
            logger.info("Copied '%s' to pod %s.", sample_app, pod_name)
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

        payload = _build_udf_payload(sample_app, device_value, alert_mode)
        if not payload:
            return False

        json_payload = json.dumps(payload)
        logger.info("Payload:\n%s", json_payload)

        # Use external nginx proxy approach (exactly like Docker does)
        logger.info("Using external nginx proxy for API access (matches Docker pattern)...")

        if not _post_ts_api_config(json_payload, target_namespace=ns, pod_name=pod_name):
            return False

        logger.info("Restarting ts-api configuration to apply new UDF and alert changes...")
        if not _restart_ts_api_config(target_namespace=ns, pod_name=pod_name):
            logger.error("Failed to restart ts-api configuration after payload update.")
            return False

        logger.info("ts-api configuration restart completed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        logger.error("An error occurred while executing a command: %s", e)
        return False
    except Exception as e:
        logger.error("An unexpected error occurred while activating the UDF package: %s", e)
        return False

def setup_multimodal_udf_deployment_package(chart_path, namespace, device_value="cpu"):
    """Configure multimodal UDF deployment artifacts and activate required services."""
    original_dir = os.getcwd()
    try:
        logger.info("Setting up multimodal UDF deployment packages...")

        os.chdir(chart_path)
        os.chdir("../")

        logger.info("Step 1: Copying DL Streamer models to dlstreamer-pipeline-server pod")
        dlstreamer_pod_command = (
            f"kubectl get pods -n {namespace} "
            "-o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | "
            "grep deployment-dlstreamer-pipeline-server | head -n 1"
        )
        result = subprocess.run(dlstreamer_pod_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0 and result.stdout:
            dlstreamer_pod = result.stdout.decode('utf-8').strip().replace("'", "")
            logger.info(f"Found DL Streamer pod: {dlstreamer_pod}")
        else:
            logger.error("DL Streamer pod not found.")
            return False

        models_path = "configs/dlstreamer-pipeline-server/models"
        if os.path.exists(models_path):
            kubectl_cp_dlstreamer = [
                'kubectl', 'cp', models_path,
                f'{dlstreamer_pod}:/home/pipeline-server/resources/',
                '-c', 'dlstreamer-pipeline-server', '-n', namespace
            ]
            logger.info(f"Copying DL Streamer models: {' '.join(kubectl_cp_dlstreamer)}")
            result = subprocess.run(kubectl_cp_dlstreamer, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info("DL Streamer models copied successfully.")
            else:
                logger.error(f"Error copying DL Streamer models: {result.stderr.decode('utf-8')}")
                return False
        else:
            logger.warning("DL Streamer models directory not found, skipping...")

        logger.info("Step 2: Setting up Time Series Analytics UDF package")
        ts_config_path = "configs/time-series-analytics-microservice"
        if not os.path.exists(ts_config_path):
            logger.error("Time Series Analytics config directory not found.")
            return False

        os.chdir(ts_config_path)
        os.makedirs("weld_defect_detector", exist_ok=True)
        for item in ["models", "tick_scripts", "udfs"]:
            if os.path.exists(item):
                result = subprocess.run(['cp', '-r', item, 'weld_defect_detector/.'], capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"Copied {item} to weld_defect_detector directory.")
                else:
                    logger.error(f"Error copying {item}: {result.stderr}")
                    return False

        ts_pod_command = (
            f"kubectl get pods -n {namespace} "
            "-o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | "
            "grep deployment-time-series-analytics-microservice | head -n 1"
        )
        result = subprocess.run(ts_pod_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0 and result.stdout:
            ts_pod = result.stdout.decode('utf-8').strip().replace("'", "")
            logger.info(f"Found Time Series Analytics pod: {ts_pod}")
        else:
            logger.error("Time Series Analytics pod not found.")
            return False

        kubectl_cp_ts = [
            'kubectl', 'cp', 'weld_defect_detector',
            f'{ts_pod}:/tmp/', '-n', namespace
        ]
        logger.info(f"Copying Time Series UDF package: {' '.join(kubectl_cp_ts)}")
        result = subprocess.run(kubectl_cp_ts, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info("Time Series UDF package copied successfully.")
        else:
            logger.error(f"Error copying Time Series UDF package: {result.stderr.decode('utf-8')}")
            return False

        logger.info("Step 3: Activating Time Series Analytics UDF")
        # Use external nginx proxy approach (exactly like Docker does)
        logger.info("Using external nginx proxy for API access (matches Docker pattern)...")

        payload = {
            "udfs": {
                "name": constants.WELD_UDF,
                "models": constants.WELD_MODEL,
                "device": device_value
            },
            "alerts": {
                "mqtt": {
                    "mqtt_broker_host": constants.CONTAINERS["mqtt_broker"]["name"],
                    "mqtt_broker_port": constants.CONTAINERS["mqtt_broker"]["port"],
                    "name": "my_mqtt_broker"
                }
            }
        }
        json_payload = json.dumps(payload)
        logger.info(f"Time Series UDF payload: {json_payload}")
        
        if not _post_ts_api_config(json_payload, target_namespace=namespace, pod_name=ts_pod):
            logger.error("Failed to post Time Series UDF configuration")
            return False

        logger.info("Restarting ts-api configuration to apply new UDF changes...")
        if not _restart_ts_api_config(target_namespace=namespace, pod_name=ts_pod):
            logger.error("Failed to restart ts-api configuration after UDF update.")
            return False
        
        logger.info("Time Series UDF activated successfully via external nginx proxy")

        logger.info("Step 4: Activating DL Streamer Pipeline")
        dlstreamer_payload = {
            "destination": {
                "metadata": {
                    "type": "mqtt",
                    "topic": "vision_weld_defect_classification"
                },
                "frame": [{
                    "type": "webrtc",
                    "peer-id": "samplestream"
                },
                {
                    "type": "s3_write",
                    "bucket": "dlstreamer-pipeline-results",
                    "folder_prefix": "weld-defect-classification",
                    "block": False
                }]
            },
            "parameters": {
                "classification-properties": {
                    "model": "/home/pipeline-server/resources/models/weld-defect-classification-f16-DeiT/deployment/Classification/model/model.xml",
                    "device": device_value.upper()
                }
            }
        }
        # Use kubectl exec to avoid port forwarding dependency
        dlstreamer_activate_command = [
            'kubectl', 'exec', dlstreamer_pod, '-n', namespace, '-c', 'dlstreamer-pipeline-server', '--',
            'curl', '-X', 'POST',
            'http://localhost:8080/pipelines/user_defined_pipelines/weld_defect_classification',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps(dlstreamer_payload)
        ]
        logger.info(f"Activating DL Streamer Pipeline via kubectl exec: {' '.join(dlstreamer_activate_command)}")
        result = subprocess.run(dlstreamer_activate_command, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("DL Streamer Pipeline activated successfully.")
            logger.info(f"Response: {result.stdout}")
        else:
            logger.warning(f"DL Streamer Pipeline activation response: {result.stderr}")

        logger.info("Multimodal UDF deployment package setup completed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing command during multimodal UDF setup: {e}")
        return False
    except Exception as e:
        logger.error(f"Error setting up multimodal UDF deployment package: {e}")
        return False
    finally:
        os.chdir(original_dir)

def setup_mqtt_alerts(chart_path, sample_app=constants.WIND_SAMPLE_APP):
    original_dir = os.getcwd()
    try:
        # Navigate to the specified directory
        os.chdir(chart_path)
        
        if sample_app == constants.WIND_SAMPLE_APP:
            os.chdir('../' + constants.HELM_TIMESERIES)
            logger.debug(f"Current working directory: {os.getcwd()}")
            file_path = f'{os.getcwd()}/tick_scripts/windturbine_anomaly_detector.tick'
            logger.info(f"File path for tick script: {file_path}")
            setup = "mqtt"
        elif sample_app == constants.WELD_SAMPLE_APP:
            os.chdir('../' + constants.HELM_WELD)
            logger.debug(f"Current working directory: {os.getcwd()}")
            file_path = f'{os.getcwd()}/tick_scripts/weld_defect_detector.tick'
            logger.info(f"File path for tick script: {file_path}")
            setup = "mqtt_weld"

        success = common_utils.update_alert_in_tick_script(file_path, setup)
        if success:
            logger.info("MQTT alert configuration set successfully.")
            return True
        else:
            logger.error("Failed to set MQTT alert configuration.")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return False
    finally:
        os.chdir(original_dir)
        logger.info(f"Restored working directory to: {os.getcwd()}")
    
def setup_opcua_alerts(chart_path, sample_app=None, device="cpu"):
    try:
        if not sample_app:
            sample_app = constants.WIND_SAMPLE_APP
        config_dir = _get_sample_app_config_dir(chart_path, sample_app)
        if not config_dir:
            return False

        tick_script_path = config_dir / "tick_scripts" / Path(constants.WINDTURBINE_TICK_SCRIPT_PATH).name
        if not tick_script_path.exists():
            logger.error("Tick script not found for OPC UA update: %s", tick_script_path)
            return False
        logger.info("Updating OPC UA alert block in tick script: %s", tick_script_path)
        success = common_utils.update_alert_in_tick_script(str(tick_script_path), setup="opcua")
        if not success:
            logger.error("Failed to set OPC UA alert configuration in tick script.")
            return False

        logger.info("OPC UA alert configuration updated successfully. Redeploying UDF package...")
        return setup_sample_app_udf_deployment_package(
            chart_path,
            sample_app=sample_app,
            device_value=device,
            alert_mode="opcua",
        )

    except subprocess.CalledProcessError as e:
        logger.error("An error occurred while executing a command: %s", e)
        return False
    except Exception as e:
        logger.error("An unexpected error occurred while configuring OPC UA alerts: %s", e)
        return False        
    
def pod_restart(target_namespace, deployment_name="deployment-influxdb"):
    """Restart a deployment and wait for it to become ready again.
    
    Args:
        target_namespace: Kubernetes namespace where the deployment exists
        deployment_name: Name of the deployment to restart (default: "deployment-influxdb")
    """
    ns = target_namespace or namespace
    resource = f"deployment/{deployment_name}"

    try:
        logger.info("Restarting %s in namespace %s", resource, ns)
        subprocess.run(
            ["kubectl", "rollout", "restart", resource, "-n", ns],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["kubectl", "rollout", "status", resource, "-n", ns, "--timeout=180s"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Deployment %s has been restarted successfully in namespace %s", deployment_name, ns)
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else str(e)
        logger.error("Failed to restart %s in namespace %s: %s", resource, ns, stderr)
        return False

def measure_deployment_time(ingestion_type, release_name, iterations=None):
    """Simple deployment time measurement function."""
    iterations = iterations or constants.KPI_TEST_ITERATIONS
    times = []
    assert uninstall_helm_charts(release_name, namespace) == True, "Failed to uninstall Helm release."
    time.sleep(20)
    logger.info("Helm release is uninstalled if it exists")
    case = password_test_cases["test_case_3"]
    logger.info("Validating pod logs with respect to log level : debug")
    values_yaml_path = os.path.expandvars(chart_path + '/values.yaml')
    assert update_values_yaml(values_yaml_path, case) == True, "Failed to update values.yaml."
    
    # Determine SAMPLE_APP based on release name to match UDF package directory
    sample_app = "wind-turbine-anomaly-detection" if "wind" in release_name.lower() else "weld-defect-detection"
    
    logger.info(f"Starting {ingestion_type} deployment time measurement...")
    for i in range(iterations):
        logger.info(f"\n=== Test Iteration {i+1}/{iterations} ===")
        start = time.time()
        try:
            if ingestion_type == "mqtt":
                logger.info(f"Starting {ingestion_type} deployment...")
                success = helm_install(release_name, chart_path, namespace, constants.TELEGRAF_MQTT_PLUGIN, sample_app=sample_app)
            elif ingestion_type == "opcua":
                logger.info(f"Starting {ingestion_type} deployment...")
                success = helm_install(release_name, chart_path, namespace, constants.TELEGRAF_OPCUA_PLUGIN, sample_app=sample_app)
            if success:
                # Check if all pods are up and running
                logger.info("Checking pod status...")
                time.sleep(0.5)  # Wait for pods to stabilize
                pods_up = verify_pods(namespace)
                deploy_time = time.time() - start
                if pods_up:
                    times.append(deploy_time)
                    logger.info(f"✓ Deployment successful: {deploy_time:.1f}s")
                else:
                    logger.error("✗ Deployment failed: Pods not running properly")
            else:
                deploy_time = time.time() - start
                logger.error(f"✗ Deployment failed after {deploy_time:.1f}s")
        except Exception as e:
            logger.error(f"✗ Deployment error: {str(e)}")
        if i < iterations - 1:  # Perform cleanup between iterations, but not after the last one
            try:
                logger.info("Starting cleanup process...")
                cleanup_success = helm_uninstall(release_name, namespace)
                if cleanup_success:
                    logger.info("✓ Cleanup successful, waiting for stability...")
                    assert check_pods(namespace) == True, "Pods are still running after cleanup"
                    # Give more time for system to stabilize after cleanup
                else:
                    logger.error("✗ Cleanup function returned False")
                    continue  # Skip to next iteration if cleanup failed
            except Exception as e:
                logger.error(f"✗ Cleanup error: {str(e)}")
                continue  # Skip to next iteration if cleanup failed
    if not times:
        logger.error(f"✗ All {ingestion_type} deployment attempts failed")
        return 0, float('inf'), float('inf'), float('inf'), []
    success_rate = len(times) * 100 / iterations
    avg_time = sum(times) / len(times)
    logger.info(f"\n=== {ingestion_type} Final Results ===")
    logger.info(f"Success Rate: {success_rate}%")
    logger.info(f"Average Time: {avg_time:.1f}s")
    logger.info(f"Best Time: {min(times):.1f}s")
    logger.info(f"Worst Time: {max(times):.1f}s")

    return success_rate, avg_time, min(times), max(times), times

def check_pods(namespace, timeout=180, interval=5):
    """
    Checks the status of pods in the specified Kubernetes namespace for up to 3 minutes.
    Returns True if no resources are found within the timeout period, otherwise returns False.

    :param namespace: The Kubernetes namespace to check.
    :param timeout: The maximum time to wait in seconds (default is 180 seconds).
    :param interval: The interval between checks in seconds (default is 5 seconds).
    :return: True if no resources are found within the timeout, False otherwise.
    """
    start_time = time.time()
    
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            logger.warning(f"Timeout reached after {timeout}s. Some pods may still exist in namespace '{namespace}'.")
            return False
        try:
            # Execute the kubectl command to get pods in the namespace
            result = subprocess.run(
                ["kubectl", "get", "pod", "-n", namespace],
                capture_output=True,
                text=True,
                check=True
            )
            # Debug: Print the command output
            logger.debug(f"Command output: {result.stdout.strip()}")
            # Check if the output contains "No resources found"
            if not result.stdout.strip() or "No resources found" in result.stdout:
                logger.info(f"No resources found in {namespace} namespace.")
                return True
            else:
                logger.info(f"Pods are still terminating in {namespace} namespace. Waiting...")

        except subprocess.CalledProcessError as e:
            if "not found" in str(e).lower():
                logger.info(f"Namespace {namespace} not found - considered as no pods running.")
                return True
            logger.warning(f"An error occurred while checking pods: {e}")

        # Wait for the specified interval before checking again
        time.sleep(interval)

    logger.warning(f"Timeout reached after {timeout}s. Some pods may still exist in namespace '{namespace}'.")
    return False

def execute_gpu_config_curl_helm(device="gpu", namespace="time-series-analytics"):
    """Execute curl command to post GPU configuration to the time-series analytics API in Helm environment.
    
    Args:
        device (str): Device to use for configuration ('gpu', 'cpu', etc.)
        namespace (str): Kubernetes namespace for the deployment
    """
    try:
        logger.info(f"Executing curl command to post {device.upper()} configuration to API via Helm...")
        
        # Create configuration with device field using SAMPLE_APPS_CONFIG
        wind_config = constants.SAMPLE_APPS_CONFIG["wind-turbine-anomaly-detection"]
        gpu_config = {
            "udfs": {
                "name": wind_config["udf"],
                "models": wind_config["model"],
                "device": device
            },
            "alerts": {
                "mqtt": constants.MQTT_ALERT
            }
        }
        
        # Convert config to JSON string for curl command
        gpu_config_json = json.dumps(gpu_config)
        
        # Get the time-series analytics pod name without using shell
        get_pod_cmd = ["kubectl", "get", "pods", "-n", namespace, "-l", "app=ia-time-series-analytics-microservice", "-o", "jsonpath={.items[0].metadata.name}"]
        result = subprocess.run(get_pod_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0 or not result.stdout.strip():
            logger.error(f"Failed to get time-series analytics pod name: {result.stderr}")
            return False
            
        pod_name = result.stdout.strip()
        logger.info(f"Found time-series analytics pod: {pod_name}")
        
        # Use kubectl exec to avoid port forwarding dependency  
        # Post configuration to the time-series analytics API via kubectl exec
        success = _post_ts_api_config(
            payload=gpu_config_json, 
            method="POST",
            target_namespace=namespace,
            pod_name=pod_name
        )
        
        if success:
            logger.info(f"{device.upper()} configuration POST via kubectl exec succeeded")
            return True
        else:
            logger.error(f"kubectl exec command failed for {device.upper()} configuration")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout executing {device.upper()} configuration curl command")
        return False
    except Exception as e:
        logger.error(f"Exception during {device.upper()} configuration: {str(e)}")
        return False


def check_log_gpu_helm(namespace, timeout=300, interval=10):
    """
    Check Kubernetes pod logs for GPU-related messages with a timeout.
    
    Args:
        namespace (str): Kubernetes namespace to check pods in
        timeout (int): Maximum time to wait in seconds
        interval (int): Time between checks in seconds
        
    Returns:
        bool: True if GPU keywords found, False otherwise
    """
    try:
        logger.info(f"Checking for GPU keywords in {namespace} namespace logs...")
        
        # Get time-series analytics pod name
        get_pod_cmd = f"kubectl get pods -n {namespace} -l app=ia-time-series-analytics-microservice -o jsonpath='{{.items[0].metadata.name}}'"
        result = subprocess.run(get_pod_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0 or not result.stdout.strip():
            logger.error(f"Failed to get time-series analytics pod name: {result.stderr}")
            return False
            
        pod_name = result.stdout.strip()
        logger.info(f"Checking logs for pod: {pod_name}")
        
        start_time = time.time()
        gpu_pattern = re.compile(r'gpu|GPU', re.IGNORECASE)
        
        while time.time() - start_time < timeout:
            try:
                # Get recent logs from the pod
                logs_cmd = f"kubectl logs -n {namespace} {pod_name} --tail=1000"
                result = subprocess.run(logs_cmd, shell=True, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    logs = result.stdout
                    
                    # Search for GPU keywords
                    gpu_matches = gpu_pattern.findall(logs)
                    
                    if gpu_matches:
                        gpu_count = len(gpu_matches)
                        logger.info(f"✓ Found 'GPU' in pod logs ({gpu_count} occurrences)")
                        logger.info(f"✓ GPU pattern found in logs for pod {pod_name}")
                        return True
                else:
                    logger.warning(f"Failed to get logs from pod {pod_name}: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.warning("Timeout getting pod logs, retrying...")
            except Exception as e:
                logger.warning(f"Error getting logs: {str(e)}")
            
            # Wait before next check
            time.sleep(interval)
        
        logger.warning(f"GPU keywords not found in pod logs after {timeout} seconds")
        return False
        
    except Exception as e:
        logger.error(f"Exception during GPU log check: {str(e)}")
        return False


# =================================================================
# SEAWEED / S3 STORAGE HELM FUNCTIONS
# =================================================================

def verify_seaweed_essential_pods(namespace):
    """
    Verify that essential pods are running for S3 image storage in Helm deployment
    """
    try:
        essential_components = [
            "dlstreamer",  # DLStreamer pod
            "influxdb",    # InfluxDB pod
            "seaweedfs"    # SeaweedFS pods (master, filer, s3)
        ]

        # Get all pod names in the namespace
        pod_names = get_pod_names(namespace)
        logger.info(f"Found pods in namespace '{namespace}': {pod_names}")

        running_pods = []

        for component in essential_components:
            # Find pods matching the component pattern
            matching_pods = [pod for pod in pod_names if component in pod]

            if not matching_pods:
                logger.error(f"✗ {component} pod not found in namespace '{namespace}'")
                continue

            # Check each matched pod's own phase/ready state directly
            component_running = False
            for pod in matching_pods:
                try:
                    result = subprocess.run(
                        [
                            "kubectl", "get", "pod", pod,
                            "-n", namespace,
                            "-o", "jsonpath={.status.phase}:{.status.conditions[?(@.type=='Ready')].status}"
                        ],
                        capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        output = result.stdout.strip()
                        phase, ready = (output.split(":", 1) + [""])[:2]
                        if phase == "Running" and ready == "True":
                            running_pods.append(component)
                            logger.info(f"✓ {component} pod is running and ready: {pod}")
                            component_running = True
                            break
                        else:
                            logger.warning(f"Pod {pod} not ready: phase={phase}, ready={ready}")
                    else:
                        logger.warning(f"Could not query pod {pod}: {result.stderr.strip()}")
                except Exception as e:
                    logger.warning(f"Could not verify pod status for {pod}: {e}")

            if not component_running:
                logger.error(f"✗ No healthy pod found for component: {component}")

        # Check if we have the minimum required components
        required_count = 3  # dlstreamer, influxdb, seaweedfs
        success = len(running_pods) >= required_count

        return {
            "success": success,
            "running_pods": running_pods,
            "total_checked": required_count,
            "missing_pods": [c for c in essential_components if c not in running_pods]
        }

    except Exception as e:
        logger.error(f"Error verifying seaweed essential pods: {e}")
        return {"success": False, "error": str(e), "running_pods": [], "missing_pods": essential_components}


def get_vision_img_handles_from_influxdb_helm(credentials, namespace, database="datain", measurement="vision-weld-classification-results"):
    """
    Query InfluxDB for vision metadata to extract img_handle values in Helm deployment
    """
    try:
        # Get InfluxDB pod name
        influxdb_pods = get_pod_names(namespace)
        influxdb_pod = None
        
        for pod in influxdb_pods:
            if "influxdb" in pod:
                influxdb_pod = pod
                break
                
        if not influxdb_pod:
            return {"success": False, "error": "InfluxDB pod not found"}
        
        # Use LIMIT query to get alphanumeric handles (matches Docker approach)
        query = f"SELECT img_handle FROM \"{measurement}\" LIMIT 10"
        
        kubectl_cmd = [
            "kubectl", "exec", "-n", namespace, influxdb_pod, "--", 
            "influx", "-username", credentials["INFLUXDB_USERNAME"], 
            "-password", credentials["INFLUXDB_PASSWORD"], 
            "-database", database, "-execute", query, "-format", "csv"
        ]
        
        result = subprocess.run(kubectl_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {"success": False, "error": f"InfluxDB query failed: {result.stderr}"}
        
        # Parse CSV output to extract alphanumeric img_handle values
        img_handles = []
        lines = result.stdout.strip().split('\n')
        
        logger.info("InfluxDB query CSV output (first 5 lines):")
        for i, line in enumerate(lines[:5]):
            logger.info(f"  Line {i}: {line}")
        
        # Parse CSV - format: time,field2,img_handle (extract 3rd column like Docker does)
        for line in lines[1:]:  # Skip header
            if line and ',' in line:
                parts = line.split(',')
                if len(parts) >= 3:  # Ensure we have at least 3 columns
                    img_handle = parts[2].strip()  # Extract 3rd value (after 2nd comma)
                    # Only accept alphanumeric handles (like OXCV8C89KF, 2QX98C4Y18)
                    if (img_handle and 
                        img_handle != 'img_handle' and 
                        not img_handle.isdigit() and
                        len(img_handle) >= 6 and 
                        len(img_handle) <= 15):
                        # Check if it contains both letters and numbers (alphanumeric)
                        if any(c.isalpha() for c in img_handle) and any(c.isdigit() for c in img_handle):
                            img_handles.append(img_handle)
        
        # Remove duplicates
        img_handles = list(set(img_handles))
        
        if not img_handles:
            return {"success": False, "error": "No alphanumeric img_handle values found"}
            
        selected_handle = random.choice(img_handles)
        
        logger.info(f"Found {len(img_handles)} alphanumeric img_handle values")
        logger.info(f"Selected img_handle for testing: {selected_handle}")
        
        return {
            "success": True,
            "handles": img_handles,
            "total_handles": len(img_handles),
            "selected_handle": selected_handle
        }
        
    except Exception as e:
        logger.error(f"Error querying InfluxDB in helm: {e}")
        return {"success": False, "error": str(e)}


def execute_seaweedfs_bucket_query_helm(namespace):
    """
    Execute SeaweedFS S3 API query via direct nginx service access in Helm deployment
    """
    try:
        # Execute curl command via direct nginx service access
        bucket_url = "https://localhost:30001/image-store/buckets/dlstreamer-pipeline-results/weld-defect-classification/?limit=5000"
        curl_cmd = [
            "curl", "-sk", "--connect-timeout", "10", "--max-time", "30",
            "-H", "Accept: application/json",
            bucket_url
        ]

        logger.info(f"Executing SeaweedFS bucket query: {' '.join(curl_cmd)}")

        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=45)
        
        logger.info(f"Curl result - Return code: {result.returncode}")
        logger.info(f"Curl stdout: {result.stdout[:500]}")  # Log first 500 chars
        logger.info(f"Curl stderr: {result.stderr[:500]}")  # Log first 500 chars  
        
        if result.returncode != 0:
            return {"success": False, "error": f"Curl command failed (code {result.returncode}): {result.stderr}"}
        
        # Parse JSON response
        try:
            bucket_data = json.loads(result.stdout)
            
            if "Entries" in bucket_data:
                entries = bucket_data["Entries"]
                jpg_files = []
                
                for entry in entries:
                    # SeaweedFS API returns "FullPath" not "Name"
                    full_path = entry.get("FullPath", "")
                    if full_path.endswith('.jpg'):
                        jpg_files.append(full_path)
                
                return {
                    "success": True,
                    "jpg_files": jpg_files,
                    "total_files": len(entries),
                    "bucket_url": bucket_url
                }
            else:
                return {"success": False, "error": "Invalid bucket response format"}
                
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse JSON response: {e}"}
                
    except Exception as e:
        logger.error(f"Error executing SeaweedFS query in helm: {e}")
        return {"success": False, "error": str(e)}


def validate_s3_images_content_helm(namespace, matched_files, max_files_to_check=3):
    """
    Validate S3 image file content via direct nginx service access and curl commands
    """
    try:
        files_to_check = matched_files[:max_files_to_check]
        logger.info(f"Validating content of {len(files_to_check)} image files (max: {max_files_to_check})")
        
        checked_files = []
        non_empty_count = 0
        empty_count = 0
        
        for file_path in files_to_check:
            filename = file_path.split('/')[-1]
            file_url = f"https://localhost:30001/image-store/{file_path.lstrip('/')}"
            
            logger.info(f"Checking file size for: {file_url}")
            
            # Use curl -skI to get headers only (file size check)
            curl_cmd = [
                "curl", "-skI", "--connect-timeout", "10", "--max-time", "15",
                file_url
            ]
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=20)
            
            file_check = {"filename": filename, "success": False, "is_empty": True, "size_human": "0 bytes"}
            
            if result.returncode == 0:
                headers = result.stdout
                
                # Extract Content-Length from headers
                for line in headers.split('\n'):
                    if line.lower().startswith('content-length:'):
                        size_str = line.split(':', 1)[1].strip().replace('\r', '')
                        try:
                            size_bytes = int(size_str)
                            if size_bytes > 0:
                                file_check["success"] = True
                                file_check["is_empty"] = False
                                file_check["size_human"] = f"{size_bytes} bytes"
                                logger.info(f"File is NOT empty: {filename} (size: {size_bytes} bytes)")
                                non_empty_count += 1
                            else:
                                logger.warning(f"File is EMPTY: {filename}")
                                empty_count += 1
                            break
                        except ValueError:
                            logger.warning(f"Could not parse file size: {size_str}")
                            empty_count += 1
                else:
                    logger.warning(f"Content-Length header not found for: {filename}")
                    empty_count += 1
            else:
                logger.error(f"Curl failed for {filename}: {result.stderr}")
                empty_count += 1
            
            checked_files.append(file_check)
        
        success = non_empty_count > 0
        
        return {
            "success": success,
            "checked_files": checked_files,
            "total_checked": len(checked_files),
            "non_empty_count": non_empty_count,
            "empty_count": empty_count
        }
            
    except Exception as e:
        logger.error(f"Error validating S3 content in helm: {e}")
        return {"success": False, "error": str(e)}