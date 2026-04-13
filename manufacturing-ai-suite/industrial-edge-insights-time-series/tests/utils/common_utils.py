#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import subprocess
import json
import time
import os
import yaml
import secrets
import string
from datetime import datetime, timedelta
from ruamel.yaml import YAML
import logging
import re
import socket
import constants

# Set up logger
logger = logging.getLogger(__name__)
PROXY_URL = os.getenv("PROXY_URL", None)


def _is_valid_epoch(ts):
    """Return True if timestamp can be converted to a reasonable epoch."""
    if ts <= 0:
        return False

    # Accept seconds, milliseconds, microseconds, or nanoseconds within sane time bounds
    lower_bound = datetime(2000, 1, 1)
    upper_bound = datetime.now() + timedelta(days=1)
    for divisor in (1, 1_000, 1_000_000, 1_000_000_000):
        try:
            normalized_ts = ts / divisor
            dt = datetime.fromtimestamp(normalized_ts)
            if lower_bound <= dt <= upper_bound:
                return True
        except (ValueError, OverflowError, OSError):
            continue
    return False


def extract_sender_ntp_timestamps(metadata_values):
    """Return list of RTP sender timestamps parsed from metadata field strings."""
    timestamps = []
    pattern = re.compile(r"sender_ntp_unix_timestamp_ns[\"']?:\s*(\d+)")
    for raw_value in metadata_values or []:
        if raw_value is None:
            continue
        match = pattern.search(str(raw_value))
        if match:
            try:
                ts = int(match.group(1))
            except ValueError as exc:
                logger.error("Encountered invalid RTP timestamp value: %s", match.group(1))
                raise ValueError(f"Invalid RTP timestamp value: {match.group(1)}") from exc

            if not _is_valid_epoch(ts):
                logger.error("Encountered invalid RTP timestamp epoch: %s", match.group(1))
                raise ValueError(f"Invalid RTP timestamp epoch: {match.group(1)}")

            timestamps.append(ts)
    return timestamps

def get_host_ip():
    """Get the IP address of the host machine."""
    try:
        # Connect to a remote server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        host_ip = s.getsockname()[0]
        s.close()
        return host_ip
    except Exception as e:
        logger.warning(f"Could not determine host IP, falling back to 127.0.0.1: {e}")
        return "127.0.0.1"

def _container_is_running(name):
    """Check if a container is running."""
    result = subprocess.run(["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"], 
                          capture_output=True, text=True)
    return name in result.stdout

def _collect_live_logs(container_name, monitor_duration, search_pattern=None):
    """Collect logs from a container for a specified duration with pattern search."""
    
    try:
        # Run docker logs command for the duration
        process = subprocess.Popen(
            f"docker logs -f {container_name}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Collect logs for the specified duration
        start_time = time.time()
        while time.time() - start_time < monitor_duration:
            line = process.stdout.readline()
            if line:
                line_stripped = line.strip()
                logger.info(f"[LOG] {line_stripped}")
                
                # Check for search pattern if provided
                if search_pattern and search_pattern.lower() in line_stripped.lower():
                    process.terminate()
                    process.wait()
                    return True
        
        # Terminate the process
        process.terminate()
        process.wait()
        
        return False if search_pattern else True
        
    except Exception as e:
        logger.error(f"Error collecting logs: {str(e)}")
        return False

def wait_for_stability(seconds=30):
    """Wait for containers/services to stabilize."""
    logger.info(f"Waiting {seconds} seconds for services to stabilize...")
    time.sleep(seconds)


def wait_for_pods_ready(namespace, timeout=90):
    """Wait for all pods in namespace to reach Ready state using kubectl wait.

    Exits as soon as all pods are Ready (faster than a fixed sleep when pods
    come up early). Falls back gracefully on error without raising, so the
    caller's own verify_pods() assertion handles any residual failures.
    """
    logger.info("Waiting up to %ss for all pods in '%s' to be Ready...", timeout, namespace)
    try:
        result = subprocess.run(
            ["kubectl", "wait", "--for=condition=Ready", "pods", "--all",
             "-n", namespace, f"--timeout={timeout}s"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("All pods in '%s' are Ready.", namespace)
            return True
        logger.warning(
            "kubectl wait reported not-ready for namespace '%s' (rc=%d): %s",
            namespace, result.returncode, result.stderr.strip(),
        )
        return False
    except Exception as exc:
        logger.warning("kubectl wait raised an exception: %s. Continuing.", exc)
        return False


# Backwards compatibility for older imports
_wait_for_stability = wait_for_stability

def _run_command(cmd):
    """Execute shell commands."""
    return subprocess.run(cmd, shell=True).returncode

def _check_and_set_working_directory():
    """Check current working directory and change to wind turbine directory."""
    current_dir = os.getcwd()
    logger.debug(f"Current working directory: {current_dir}")
    
    # Check if we're already in or below the target directory
    if "edge-ai-suites" in current_dir:
        logger.debug("Already in edge-ai-suites directory structure")
        
        # Split the path and find where the target directory starts
        parts = current_dir.split(os.sep)
        
        try:
            edge_index = parts.index('edge-ai-suites')
            # Take everything up to 'edge-ai-suites' and rebuild the path
            root_parts = parts[:edge_index]
            root_path = os.sep.join(root_parts) if root_parts else os.sep
            
            # Rebuild the target path
            target_dir = os.path.join(root_path, constants.TARGET_SUBPATH)
        except ValueError:
            # If 'edge-ai-suites' not found in parts, use constants
            target_dir = os.path.join(current_dir, constants.EDGE_AI_SUITES_DIR)
    else:
        # If not in edge-ai-suites structure, use constants to build path
        target_dir = constants.EDGE_AI_SUITES_DIR
    
    logger.debug(f"Target directory: {target_dir}")
    
    if os.path.exists(target_dir):
        original_dir = current_dir
        os.chdir(target_dir)
        logger.debug(f"Changed working directory to: {os.getcwd()}")
        return True, original_dir
    else:
        logger.error(f"Target directory does not exist: {target_dir}")
        return False, current_dir

def _invoke_make_down():
    """Execute make down command."""
    try:
        success, original_dir = _check_and_set_working_directory()
        if not success:
            logger.debug("Failed to set working directory for make down")
            return False
        
        result = _run_command("make down")
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.debug("make down failed")
            return False
        
        logger.debug("make down succeeded")
        return True
        
    except Exception as e:
        logger.error(f"Exception during make down: {str(e)}")
        return False

def _invoke_make_up_opcua_ingestion():
    """Execute make up_opcua_ingestion command."""
    try:
        success, original_dir = _check_and_set_working_directory()
        if not success:
            logger.debug("Failed to set working directory for OPC-UA ingestion")
            return False
            
        result = _run_command("make up_opcua_ingestion")
        
        # Return to original directory before returning result
        os.chdir(original_dir)
        
        if result != 0:  # Command failed
            logger.debug("make up_opcua_ingestion failed")
            return False
        
        logger.debug("make up_opcua_ingestion succeeded")
        return True
        
    except Exception as e:
        logger.error(f"Exception during make up_opcua_ingestion: {str(e)}")
        return False

def generate_password(length=10):
    """Generate a secure random password with at least one digit."""

    alphabet = string.ascii_letters + string.digits
    # Ensure at least one digit is included
    password = [secrets.choice(string.digits)]
    # Generate the rest of the password
    password.extend(secrets.choice(alphabet) for _ in range(length - 1))
    # Shuffle the password to mix the digit with other characters
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)

def generate_username(length=10):
    """Generate a secure random username."""
    alphabet = string.ascii_letters
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def check_logs_for_alerts(resource_name, input_type, resource_type="container", namespace=None, timeout=300, interval=10):
    """
    Check container or pod logs for specific alert messages with a timeout.
    
    Args:
        resource_name (str): Name of the container or pod
        input_type (str): Type of alert to search for ('mqtt' or 'opcua')
        timeout (int): Maximum time to wait for alerts (seconds)
        interval (int): Check interval (seconds)
        resource_type (str): Type of resource ('container' or 'pod')
        namespace (str): Kubernetes namespace (required for pods)
    
    Returns:
        bool: True if alert found, False otherwise
    """
    # Define alert message patterns - these match Kapacitor's actual log output
    # Kapacitor logs when it sends alerts, patterns are case-insensitive
    alert_patterns = {
        "mqtt": "alerts/wind_turbine",  # Simplified to match topic in logs
        "opcua": "opcua_alerts",  # Matches the HTTP endpoint
        "mqtt_weld": "alerts/weld_defects"  # Simplified to match topic in logs
    }
    
    # Validate inputs
    input_lower = input_type.lower()
    if input_lower not in alert_patterns:
        logger.error(f"✗ Unknown input type: {input_type}. Use 'mqtt' or 'opcua'")
        return False
    
    if resource_type == "pod" and not namespace:
        logger.error("✗ Namespace is required for pod logs")
        return False
    
    search_pattern = alert_patterns[input_lower]
    
    logger.info(f"Checking {resource_type} '{resource_name}' logs for {input_type.upper()} alerts...")
    logger.info(f"Timeout: {timeout}s, Check interval: {interval}s")
    
    # Check if container is running (only for containers)
    if resource_type == "container" and not _container_is_running(resource_name):
        logger.error(f"✗ Container {resource_name} is not running")
        return False
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        elapsed_time = time.time() - start_time
        remaining_time = timeout - elapsed_time
        
        logger.info(f"Monitoring... (elapsed: {elapsed_time:.1f}s, remaining: {remaining_time:.1f}s)")
        
        try:
            # Get logs based on resource type
            if resource_type == "container":
                # For containers, use existing collect_live_logs function
                monitor_duration = min(interval, remaining_time)
                result = _collect_live_logs(resource_name, monitor_duration, search_pattern)

                if result is True:
                    logger.info(f"✓ {input_type.upper()} Alert found in {resource_type} '{resource_name}' logs")
                    return True
                    
            elif resource_type == "pod":
                # For pods, use kubectl to get logs
                result = subprocess.run(
                    ["kubectl", "logs", resource_name, "-n", namespace, "--tail=100"],
                    capture_output=True, text=True, check=True
                )
                logs = result.stdout.strip()
                
                if search_pattern in logs.lower():
                    logger.info(f"✓ {input_type.upper()} Alert found in {resource_type} '{resource_name}' logs:")
                    logger.info(logs)
                    return True
                else:
                    logger.info(f"No {input_type} alerts found in {resource_type} '{resource_name}' logs. Retrying...")
            
            # Break if remaining time is less than interval
            if remaining_time <= interval:
                break
                
            # Wait before next check (only for pods, containers handle timing in collect_live_logs)
            if resource_type == "pod":
                time.sleep(min(interval, remaining_time))
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to fetch logs for {resource_type} '{resource_name}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while checking {resource_type} logs: {e}")
            return False
    
    logger.info(f"Timeout reached ({timeout}s). No {input_type} alerts found in {resource_type} '{resource_name}' logs.")
    return False

def update_alert_in_tick_script(file_path, setup):
    """Remove specific alert configuration and add a new one in the .tick file."""
    # Define the alert pattern to remove
    remove_alert_pattern1 = re.compile(
        r'\|alert\(\)\s*\.crit\(lambda: "anomaly_status" > 0\)\s*'
        r'\.message\(.*?\)\s*\.noRecoveries\(\)\s*\.mqtt\(.*?\)\s*'
        r'\.topic\(.*?\)\s*\.qos\(1\)', re.DOTALL
    )
    remove_alert_pattern2 = re.compile(
        r'\|alert\(\)\s*\.crit\(lambda: "anomaly_status" > 0\)\s*'
        r'\.message\(.*?wind_speed.*?grid_active_power.*?anomaly_status.*?\)\s*'
        r'\.noRecoveries\(\)\s*\.post\(.*?opcua_alerts.*?\)\s*\.timeout\(30s\)',
        re.DOTALL
    )
    # Define the new alert script to add
    new_alert_script1 = """
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected for wind speed: {{ index .Fields "wind_speed" }} Grid Active Power: {{ index .Fields "grid_active_power" }} Anomaly Status: {{ index .Fields "anomaly_status" }} ')
        .noRecoveries()
        .mqtt('my_mqtt_broker')
        .topic('alerts/wind_turbine')
        .qos(1)
"""
    new_alert_script2 = """
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected for wind speed: {{ index .Fields "wind_speed" }} Grid Active Power: {{ index .Fields "grid_active_power" }} Anomaly Status: {{ index .Fields "anomaly_status" }} ')
        .noRecoveries()
        .post('http://localhost:5000/opcua_alerts')
        .timeout(30s)
"""
    new_alert_script3 = """
    |alert()
                .crit(lambda: "anomaly_status" > 0)
                .message('{"time": "{{ index .Time }}", "Pressure": {{ index .Fields "Pressure" }}, "CO2 Weld Flow": {{ index .Fields "CO2 Weld Flow" }}, "anomaly_status": {{ index .Fields "anomaly_status" }} } ')
                .noRecoveries()
                .mqtt('my_mqtt_broker')
                .topic('alerts/weld_defects')
                .qos(1)
"""

    
    try:
        # Read the existing content of the .tick file
        with open(file_path, 'r') as file:
            content = file.read()

        # Remove the specific alert section
        
        content = remove_alert_pattern1.sub('', content)
        logger.debug("Removed MQTT alert pattern from the .tick file.")
        content = remove_alert_pattern2.sub('', content)
        logger.debug("Removed OPCUA alert pattern from the .tick file.")
        
        # Append the new alert script
        if setup == "mqtt":
            content += new_alert_script1
            logger.debug("Added new MQTT alert script to the .tick file.")
        elif setup == "opcua":
            content += new_alert_script2
            logger.debug("Added new OPCUA alert script to the .tick file.")
        elif setup == "mqtt_weld":
            content += new_alert_script3
            logger.debug("Added new MQTT Weld alert script to the .tick file.")
        else:
            logger.error(f"Invalid setup type: {setup}. Use 'mqtt' or 'opcua' or 'mqtt_weld'.")
            return False

        # Write the updated content back to the .tick file
        with open(file_path, 'w') as file:
            file.write(content)

        logger.debug("Alert configuration updated successfully.")
        return True

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False
    

def update_log_level(level):
    """Simple log level update in .env file"""
    env_file = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
    
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update LOG_LEVEL line
    with open(env_file, 'w') as f:
        for line in lines:
            if line.startswith("LOG_LEVEL="):
                f.write(f"LOG_LEVEL={level}\n")
            else:
                f.write(line)
    
    logger.debug(f"Updated LOG_LEVEL to {level}")
    
def check_logs_by_level(resource_name, log_level, resource_type="container", namespace=None, tail_lines=10, monitor_duration=10, update_config=False):
    """
    Check container or pod logs for specific log levels.
    For containers, can optionally update configuration and restart services.
    
    Args:
        resource_name (str): Name of the container or pod
        log_level (str): Log level to search for ('DEBUG', 'INFO', 'WARN', 'ERROR')
        resource_type (str): Type of resource ('container' or 'pod')
        namespace (str): Kubernetes namespace (required for pods)
        tail_lines (int): Number of recent log lines to check for pods
        monitor_duration (int): Duration for container log monitoring (unused but kept for compatibility)
        update_config (bool): If True, update .env file and restart containers (container only)
    
    Returns:
        bool: True if specified log level found (except ERROR which returns False), False otherwise
    """
    # Validate inputs
    valid_log_levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    log_level_upper = log_level.upper()
    
    if log_level_upper not in valid_log_levels:
        logger.error(f"✗ Unknown log level: {log_level}. Valid levels: {valid_log_levels}")
        return False
    
    if resource_type == "pod" and not namespace:
        logger.error("✗ Namespace is required for pod logs")
        return False
    
    if resource_type not in ["container", "pod"]:
        logger.error(f"✗ Unknown resource type: {resource_type}. Use 'container' or 'pod'")
        return False
    
    logger.info(f"Checking {resource_type} '{resource_name}' logs for {log_level_upper} level entries...")
    
    try:
        if resource_type == "container":
            # Handle configuration update if requested
            if update_config:
                logger.debug(f"\n--- Testing {log_level_upper} with config update ---")
                
                # Update .env file
                update_log_level(log_level_upper)
                
                # Wait for configuration changes to take effect and containers to restart
                wait_for_stability(45)
            
            # Container log checking using docker logs with grep
            grep_command = f"docker logs {resource_name} 2>&1 | grep -i '{log_level_upper}'"
            logger.info(f"Executing command: {grep_command}")
            
            result = subprocess.run(grep_command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                # Found matching logs
                lines = result.stdout.strip().split('\n')
                count = len(lines)
                
                if log_level_upper == "ERROR":
                    logger.error(f"✗ Found {count} {log_level_upper} log entries in container '{resource_name}'")
                    logger.error("Sample error entries:")
                    for i, line in enumerate(lines[:3]):
                        logger.error(f"  {i+1}: {line}")
                    if count > 3:
                        logger.error(f"  ... and {count - 3} more error entries")
                    return False
                else:
                    logger.info(f"✓ Found {count} {log_level_upper} log entries in container '{resource_name}'")
                    logger.info("Sample log entries:")
                    for i, line in enumerate(lines[:3]):
                        logger.info(f"  {i+1}: {line}")
                    if count > 3:
                        logger.info(f"  ... and {count - 3} more entries")
                    return True
            else:
                logger.info(f"✗ No {log_level_upper} log entries found in container '{resource_name}'")
                return False
                
        elif resource_type == "pod":
            # Pod log checking using kubectl logs
            result = subprocess.run(
                ["kubectl", "logs", resource_name, "-n", namespace, f"--tail={tail_lines}"],
                capture_output=True, text=True, check=True
            )
            logs = result.stdout.strip()
            
            # Check for log level pattern - support multiple formats:
            # 1. Python logging format: "ERROR -", "INFO -", "DEBUG -"
            # 2. Kapacitor format: "lvl=error", "lvl=info", "lvl=debug"
            # 3. Uvicorn/Gunicorn format: "INFO:", "DEBUG:", "ERROR:"
            # 4. Standard logging format: "level=INFO", "level=DEBUG"
            log_pattern_python = f"{log_level_upper} -"
            log_pattern_kapacitor = f"lvl={log_level_upper.lower()}"
            log_pattern_uvicorn = f"{log_level_upper}:"
            log_pattern_level_eq = f"level={log_level_upper.lower()}"
            
            logs_upper = logs.upper()
            found = (log_pattern_python in logs_upper
                     or log_pattern_kapacitor.upper() in logs_upper
                     or log_pattern_uvicorn in logs_upper
                     or log_pattern_level_eq.upper() in logs_upper)
            
            if found:
                if log_level_upper == "ERROR":
                    # Filter out benign errors
                    benign_error_patterns = [
                        "error while sending usage report",  # Kapacitor telemetry timeout
                        "usage.influxdata.com",  # InfluxData usage reporting endpoint
                        "WARNING: Retrying",  # PyPI connection retry
                        "ConnectTimeoutError",  # PyPI connection timeout
                        "Connection to pypi.org timed out",  # PyPI timeout
                    ]
                    is_benign = any(pattern.lower() in logs.lower() for pattern in benign_error_patterns)
                    
                    if is_benign:
                        logger.info(f"✓ Benign {log_level_upper} found in logs for pod '{resource_name}' (expected during operation):")
                        logger.info(logs)
                        return True
                    else:
                        logger.error(f"✗ {log_level_upper} found in logs for pod '{resource_name}':")
                        logger.error(logs)
                        return False
                else:
                    logger.info(f"✓ {log_level_upper} found in logs for pod '{resource_name}':")
                    logger.info(logs)
                    return True
            else:
                logger.info(f"✗ No {log_level_upper} found in logs for pod '{resource_name}'. Recent logs:")
                logger.info(logs)
                return False
                
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Failed to fetch logs for {resource_type} '{resource_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error checking {resource_type} logs: {str(e)}")
        return False

def check_container_log_level(container_name=constants.CONTAINERS["time_series_analytics"]["name"], monitor_duration=10):
    """
    Simple container log level verification.
    
    Args:
        container_name (str): Name of the container to check
        monitor_duration (int): Duration for container log monitoring
    
    Returns:
        bool: True if both INFO and DEBUG verification pass, False otherwise
    """
    logger.info("=== Container Log Level Verification ===")
    
    # Test INFO level (with config update)
    info_result = check_logs_by_level(container_name, "INFO", update_config=True)
    
    # Test DEBUG level (with config update)  
    debug_result = check_logs_by_level(container_name, "DEBUG", update_config=True)
    
    # Results
    all_passed = info_result and debug_result
    logger.info(f"Results: INFO {'✓' if info_result else '✗'}, DEBUG {'✓' if debug_result else '✗'}")
    
    return all_passed


def check_individual_log_level(container_name, log_level, update_config=False, restart_container=False):
    """
    Check individual log level for a specific container with optional container restart.
    
    Args:
        container_name (str): Name of the container to check
        log_level (str): Log level to check ('INFO', 'DEBUG', etc.)
        update_config (bool): Whether to update .env file with new log level
        restart_container (bool): Whether to restart the container after config update
    
    Returns:
        bool: True if log level found, False otherwise
    """
    logger.info(f"=== Individual Log Level Check: {log_level} ===")
    
    if update_config:
        # Update .env file
        update_log_level(log_level)
        
        if restart_container:
            # Import docker_utils here to avoid circular imports
            from . import docker_utils
            logger.debug(f"Restarting container {container_name} for log level {log_level}...")
            restart_exit_code = docker_utils.restart_container(container_name)
            if restart_exit_code != 0:
                logger.error(f"Failed to restart container {container_name}, exit code: {restart_exit_code}")
                return False
            
            # Wait for container to stabilize
            docker_utils.wait_for_stability(45)
    
    # Check logs for the specified level
    result = check_logs_by_level(container_name, log_level, update_config=False)
    
    logger.info(f"Log level {log_level} check result: {'✓' if result else '✗'}")
    return result

def check_mqtt_topic_data(topic, broker_host="localhost", broker_port=1883, timeout=30):
    """Check if data is being published to an MQTT topic."""
    import paho.mqtt.client as mqtt
    
    logger.info(f"Checking MQTT topic: {topic} on {broker_host}:{broker_port}")
    
    data_received = {"received": False}
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker")
            client.subscribe(topic)
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def on_message(client, userdata, msg):
        logger.info(f"Message received on topic {msg.topic}: {msg.payload.decode()}")
        data_received["received"] = True
        client.disconnect()
    
    try:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        
        client.connect(broker_host, broker_port, 60)
        
        # Wait for message or timeout
        start_time = time.time()
        client.loop_start()
        
        while not data_received["received"] and (time.time() - start_time) < timeout:
            time.sleep(1)
        
        client.loop_stop()
        client.disconnect()
        
        return data_received["received"]
        
    except Exception as e:
        logger.error(f"Error checking MQTT topic: {e}")
        return False

def check_http_endpoint(url, timeout=30, expected_status=200):
    """Check if an HTTP endpoint is accessible."""
    import requests
    
    logger.info(f"Checking HTTP endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == expected_status:
            logger.info(f"✓ HTTP endpoint {url} is accessible (status: {response.status_code})")
            return True
        else:
            logger.warning(f"HTTP endpoint {url} returned status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error accessing HTTP endpoint {url}: {e}")
        return False

def check_port_accessibility(host, port, timeout=10):
    """Check if a TCP port is accessible."""
    import socket
    
    logger.info(f"Checking port accessibility: {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            logger.info(f"✓ Port {host}:{port} is accessible")
            return True
        else:
            logger.warning(f"Port {host}:{port} is not accessible")
            return False
            
    except Exception as e:
        logger.error(f"Error checking port {host}:{port}: {e}")
        return False

def find_critical_errors_in_logs(logs):
    """Find critical errors in container logs."""
    if not logs:
        return []
    
    critical_patterns = [
        r"fatal|FATAL",
        r"error.*failed|ERROR.*FAILED", 
        r"panic|PANIC",
        r"exception|Exception|EXCEPTION",
        r"segmentation fault",
        r"out of memory|OOM",
        r"connection refused",
        r"permission denied"
    ]
    
    critical_errors = []
    
    for pattern in critical_patterns:
        matches = re.findall(pattern, logs, re.IGNORECASE)
        if matches:
            critical_errors.extend(matches)
    
    # Filter out common non-critical errors
    non_critical_patterns = [
        r"user token not found",  # Common Grafana warning
        r"no data",
        r"timeout.*retry"
    ]
    
    filtered_errors = []
    for error in critical_errors:
        is_critical = True
        for non_critical in non_critical_patterns:
            if re.search(non_critical, error, re.IGNORECASE):
                is_critical = False
                break
        if is_critical:
            filtered_errors.append(error)
    
    return filtered_errors


def check_influxdb_data(measurement, database="datain", container_name="ia-influxdb", timeout=30):
    """
    Check if data exists in InfluxDB measurement
    
    Args:
        measurement (str): The measurement name to check
        database (str): The database name (default: "datain")
        container_name (str): The InfluxDB container name (default: "ia-influxdb")
        timeout (int): Timeout in seconds (default: 30)
        
    Returns:
        bool: True if data exists, False otherwise
    """
    try:
        # Check if container is running first
        if not _container_is_running(container_name):
            logger.warning(f"Container {container_name} is not running")
            return False
        
        # Execute InfluxDB query to check for data
        query_cmd = [
            "docker", "exec", container_name,
            "influx", "-database", database,
            "-execute", f"SELECT COUNT(*) FROM \"{measurement}\" LIMIT 1"
        ]
        
        result = subprocess.run(
            query_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            # Check if the output contains any count > 0
            if "count" in output.lower() and any(char.isdigit() and char != '0' for char in output):
                logging.info(f"Data found in measurement: {measurement}")
                return True
            else:
                logging.info(f"No data found in measurement: {measurement}")
                return False
        else:
            logging.error(f"Failed to query InfluxDB: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logging.error(f"InfluxDB query timed out after {timeout} seconds")
        return False
    except Exception as e:
        logging.error(f"Error checking InfluxDB data: {e}")
        return False

def get_system_ip():
    """
    Get the system's primary IP address using hostname command.
    
    Returns:
        str: The system's IP address, or None if not found
    """
    try:
        # Use hostname -I command - simple and reliable
        result = subprocess.run(
            ["hostname", "-I"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        if result.returncode == 0:
            ips = result.stdout.strip().split()
            # Get the first non-localhost IP that's not Docker bridge or link-local
            for ip in ips:
                if (ip and ip != "127.0.0.1" and 
                    not ip.startswith("127.") and 
                    not ip.startswith("169.254.") and 
                    not ip.startswith("172.17.") and  # Docker bridge
                    not ip.startswith("172.18.") and  # Docker networks
                    not ip.startswith("172.19.") and  # Docker networks
                    not ip.startswith("192.168.49.")):  # Minikube/K8s
                    logger.info(f"Detected system IP address: {ip}")
                    return ip
    except Exception as e:
        logger.error(f"Failed to detect system IP address: {e}")
    
    logger.error("Could not detect system IP address")
    return None

def update_host_ip_in_env(env_file_path=None, target_ip=None):
    """
    Update the HOST_IP value in the .env file with the system's IP address.
    
    Args:
        env_file_path (str): Path to the .env file. If None, uses multimodal app .env
        target_ip (str): IP address to set. If None, auto-detects system IP
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Determine .env file path
        if env_file_path is None:
            env_file_path = os.path.join(
                constants.EDGE_AI_SUITES_DIR, 
                "manufacturing-ai-suite", 
                "industrial-edge-insights-multimodal", 
                ".env"
            )
        
        # Get target IP
        if target_ip is None:
            target_ip = get_system_ip()
            if target_ip is None:
                logger.error("Could not detect system IP address for .env update")
                return False
        
        # Check if .env file exists
        if not os.path.exists(env_file_path):
            logger.error(f".env file not found: {env_file_path}")
            return False
        
        # Read current .env file content
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
        
        # Update HOST_IP line
        updated_lines = []
        host_ip_updated = False
        
        for line in lines:
            if line.strip().startswith("HOST_IP="):
                old_value = line.strip().split('=', 1)[1] if '=' in line else ""
                updated_lines.append(f"HOST_IP={target_ip}\n")
                host_ip_updated = True
                logger.info(f"Updated HOST_IP from '{old_value}' to '{target_ip}'")
            else:
                updated_lines.append(line)
        
        # Write updated content back to file
        if host_ip_updated:
            with open(env_file_path, 'w') as f:
                f.writelines(updated_lines)
            logger.info(f"Successfully updated HOST_IP in {env_file_path}")
            return True
        else:
            logger.warning("HOST_IP line not found in .env file")
            return False
            
    except Exception as e:
        logger.error(f"Error updating HOST_IP in .env file: {e}")
        return False

def setup_multimodal_environment():
    """
    Setup multimodal environment by updating HOST_IP and other necessary configurations.
    This should be called before running multimodal tests.
    
    Returns:
        bool: True if setup was successful, False otherwise
    """
    logger.debug("Setting up multimodal environment...")
    
    try:
        # Update HOST_IP in .env file
        if not update_host_ip_in_env():
            logger.error("Failed to update HOST_IP in .env file")
            return False
        
        # Additional setup steps can be added here
        logger.info("✓ Multimodal environment setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up multimodal environment: {e}")
        return False


def cross_verify_img_handle_with_s3(selected_img_handle, jpg_files):
    """
    Cross-verify that the selected img_handle has a corresponding image file in S3 storage.
    This function is deployment-agnostic and used by both Docker and Helm deployments.
    
    Args:
        selected_img_handle (str): The img_handle to search for
        jpg_files (list): List of .jpg file paths from S3 storage
        
    Returns:
        dict: Result with verification status, matched file, and verification details
    """
    matched_files = []
    
    for jpg_file in jpg_files:
        if selected_img_handle in jpg_file:
            matched_files.append(jpg_file)
    
    return {
        "img_handle_found": len(matched_files) > 0,
        "selected_handle": selected_img_handle,
        "matched_files": matched_files,
        "total_jpg_files": len(jpg_files),
        "match_count": len(matched_files)
    }