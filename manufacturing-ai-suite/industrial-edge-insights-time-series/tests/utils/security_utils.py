#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import subprocess
import json
import time
import os
import sys
import aiohttp
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
import helm_utils
import yaml
import secrets
import string
from ruamel.yaml import YAML
import logging
import re
import asyncio
import constants
from influxdb_client import InfluxDBClient
import pandas as pd

# Set up logger
logger = logging.getLogger(__name__)

def fetch_credentials(chart_path, type):
    if type == "influxdb":
        return fetch_influxdb_credentials(chart_path)
    elif type == "grafana":
        return fetch_grafana_credentials(chart_path)
    else:
        logger.error(f"Unknown type: {type}. Supported types are 'influxdb' and 'grafana'.")
        return None, None, None
    
def fetch_influxdb_credentials(chart_path):
    """Fetch INFLUXDB_USERNAME and INFLUXDB_PASSWORD from values.yaml."""
    try:
        values_yaml_path = os.path.expandvars(chart_path + 'values.yaml')
        logger.info(f"Fetching InfluxDB credentials from: {values_yaml_path}")
    
        # Open and read the YAML file
        with open(values_yaml_path, 'r') as file:
            values = yaml.safe_load(file)

        # Extract the INFLUXDB_USERNAME and INFLUXDB_PASSWORD
        influxdb_username = values.get('env', {}).get('INFLUXDB_USERNAME')
        influxdb_password = values.get('env', {}).get('INFLUXDB_PASSWORD')
        logger.info("Yaml file values:", values)
        # Note: Not logging credentials for security reasons
        logger.info("Successfully retrieved InfluxDB credentials from values.yaml")
        if not influxdb_username or not influxdb_password:
            logger.error("InfluxDB credentials not found in values.yaml.")
            return None, None
        return influxdb_username, influxdb_password
    except FileNotFoundError:
        logger.error(f"File not found: {values_yaml_path}")
        return None, None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, None
    
def fetch_grafana_credentials(chart_path):
    """Fetch GRAFANA_USERNAME and GRAFANA_PASSWORD from values.yaml."""
    try:
        values_yaml_path = os.path.expandvars(chart_path + 'values.yaml')
        logger.info(f"Fetching Grafana credentials from: {values_yaml_path}")

        # Open and read the YAML file
        with open(values_yaml_path, 'r') as file:
            values = yaml.safe_load(file)

        # Extract the GRAFANA_USERNAME and GRAFANA_PASSWORD
        grafana_username = values.get('env', {}).get('VISUALIZER_GRAFANA_USER')
        grafana_password = values.get('env', {}).get('VISUALIZER_GRAFANA_PASSWORD')
        logger.info("Yaml file values:", values)
        # Note: Not logging credentials for security reasons
        logger.info("Successfully retrieved Grafana credentials from values.yaml")
        if not grafana_username or not grafana_password:
            logger.error("Grafana credentials not found in values.yaml.")
            return None, None
        return grafana_username, grafana_password
    except FileNotFoundError:
        logger.error(f"File not found: {values_yaml_path}")
        return None, None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None, None

async def login_to_grafana(url, username, password):
    """
    Simple Grafana authentication test using the API endpoint.
    
    Args:
        url: Grafana URL
        username: Grafana username  
        password: Grafana password
        
    Returns:
        bool: True if credentials are valid, False otherwise
    """
    import ssl
    try:
        # Create SSL context that doesn't verify certificates for self-signed certs
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Simple API authentication test - just verify credentials work
            async with session.get(f"{url}/api/user", 
                                   auth=aiohttp.BasicAuth(username, password),
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    logger.info("Grafana authentication successful")
                    return True
                else:
                    logger.error(f"Grafana authentication failed: HTTP {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Grafana authentication error: {e}")
        return False


def influxdb_login(namespace, chart_path):
    """Execute InfluxDB commands inside the InfluxDB pod."""
    logger.info(f"Executing InfluxDB commands in namespace '{namespace}'...")
    try:
        # Step 1: Identify the InfluxDB pod
        influxdb_username, influxdb_password = fetch_influxdb_credentials(chart_path)
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
            "-execute 'SHOW MEASUREMENTS';"
        )
        exec_command = f"kubectl exec -n {namespace} {pod_name} -- {influx_commands}"
        logger.info(f"Executing InfluXDB measurement query 'SHOW MEASUREMENTS' in namespace '%s' on pod '%s' with redacted credentials.",
            namespace,
            pod_name,
        )
        result = subprocess.run(exec_command, shell=True, capture_output=True, text=True, check=True)
        response = result.stdout.strip()
        logger.info(f"InfluxDB response: {response}")
        if "measurements" in response.lower():
            logger.info("InfluxDB login successful and measurements found.")
            return True
        else:            
            logger.error("InfluxDB login failed or no measurements found.")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing a command: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return False

def check_pod_logs_for_creds(namespace, pod_name, creds):
    """Check pod logs for credentials."""
    try:
        result = subprocess.run(
            ["kubectl", "logs", pod_name, "-n", namespace, "--tail=100"],
            capture_output=True, text=True, check=True
        )
        logs = result.stdout.strip()
        if creds[0] in logs or creds[1] in logs:
            logger.error(f"Credentials found in logs for pod {pod_name}.")
            return False
        else:            
            logger.info(f"Credentials are not found in logs for pod {pod_name}.")
            return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fetch logs for pod {pod_name}: {e}")
        return False

def verify_pods_creds(namespace, influxdb_creds, grafana_creds):
    """Verify creds for all pods  logs."""
    pod_names=helm_utils.get_pod_names(namespace)
    if not pod_names:
        logger.error("No pods found or failed to fetch pod names.")
        return False
    start_time = time.time()
    logger.info(f"Checking pod logs for credentials in namespace '{namespace}'...")
    while (time.time() - start_time) < 60:
        if influxdb_creds:
            logger.info("InfluxDB credentials fetched successfully.")
            for pod_name in pod_names:
                result = check_pod_logs_for_creds(namespace, pod_name, influxdb_creds)
                if result:
                    logger.info(f"InfluxDB credentials are not found in logs for pod {pod_name}.")
                    return True
                else:
                    logger.warning(f"InfluxDB credentials found in logs for pod {pod_name}.")
                    return False
        else:
            logger.error("Failed to fetch InfluxDB credentials.")
            return False
        if grafana_creds:
            logger.info("Grafana credentials fetched successfully.")
            for pod_name in pod_names:
                result = check_pod_logs_for_creds(namespace, pod_name, grafana_creds)
                if result:
                    logger.info(f"Grafana credentials are not found in logs for pod {pod_name}.")
                    return True
                else:
                    logger.warning(f"Grafana credentials found in logs for pod {pod_name}.")
                    return False   
        else:
            logger.error("Failed to fetch Grafana credentials.")
            return False
        
def find_exposed_ports_helm(namespace):
    exposed_ports = []

    # Run the kubectl command to get the services
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'svc', '--namespace', namespace],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error executing kubectl command: {e}")
        return exposed_ports

    # Parse the output to find exposed ports
    lines = result.stdout.strip().split('\n')
    for line in lines[1:]:  # Skip the header line
        parts = line.split()
        service_type = parts[1]
        ports = parts[4]

        if service_type == 'NodePort':
            # Extract the external port from the format internal:external/TCP
            for port_mapping in ports.split(','):
                internal_port, external_port = port_mapping.split('/')[0].split(':')
                exposed_ports.append(int(external_port))

    return exposed_ports
        
def find_exposed_ports_docker():
    # Run the docker ps command and capture the output
    result = subprocess.run(
        ["docker", "ps", "--format", "table {{.Names}}\t{{.Ports}}"],
        capture_output=True,
        text=True
    )

    # Filter lines that start with 'ia-' to get relevant containers
    lines = [line for line in result.stdout.splitlines() if line.startswith("ia-")]

    # Initialize a dictionary to store exposed ports for each container
    exposed_ports = {}

    for line in lines:
        # Split the line into container name and ports using regex to handle variable spacing
        import re
        # Match container name (starts with ia-) followed by any whitespace, then capture the rest as ports
        match = re.match(r'(ia-\S+)\s+(.*)', line)
        if match:
            container_name = match.group(1)
            ports = match.group(2) if match.group(2) else ""
        else:
            # Fallback to tab split if regex doesn't match
            parts = line.split('\t')
            container_name = parts[0].strip()
            ports = parts[1].strip() if len(parts) > 1 else ""

        # Initialize a list to store exposed ports for the current container
        exposed_ports[container_name] = []

        # Split the ports by comma and check each one
        for port in ports.split(','):
            port = port.strip()
            # Check if the port is exposed (contains '0.0.0.0' or ':::')
            if '0.0.0.0' in port or ':::' in port:
                exposed_ports[container_name].append(port)

    # Print the exposed ports for each container
    logger.info("Exposed ports:")
    logger.info("------------------")
    for container, ports in exposed_ports.items():
        if ports:
            logger.info(f"{container}: {', '.join(ports)}")
        else:
            logger.info(f"{container}: No exposed ports")

    return exposed_ports

def check_open_ports(target):
    try:
        # Execute the nmap command to check for open ports
        result = subprocess.run(['nmap', '-p-', target], capture_output=True, text=True)

        # Print the nmap command response
        logger.info(result.stdout)
        # Analyze the output to determine if there are open ports
        if "open" in result.stdout:
            return False
        else:
            return True
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False

def check_nmap(target, ports):
    try:
        # Extract actual port numbers from the exposed ports data
        port_numbers = []
        
        # Handle case where ports is already a list (for Helm)
        if isinstance(ports, list):
            port_numbers = [str(port) for port in ports]
        else:
            logger.error(f"Unexpected ports format: {type(ports)}")
            return False
        
        if not port_numbers:
            logger.warning("No ports found to scan")
            return False
            
        # Execute the nmap command to check for open ports
        port_list = ','.join(port_numbers)
        logger.info(f"Scanning ports {port_list} on target {target}")
        result = subprocess.run(['nmap', '-p', port_list, target], capture_output=True, text=True)

        # Print the nmap command response
        logger.info(result.stdout)

        # Analyze the output to determine if there are open ports
        if "open" in result.stdout:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False

def check_nmap_docker(target, ports):
    """Docker-specific nmap checking function that handles Docker port format."""
    try:
        # Extract actual port numbers from the exposed ports data
        port_numbers = []
        
        # Handle case where ports is a dictionary (from Docker exposed ports)
        if isinstance(ports, dict):
            logger.info(f"Debug: Processing exposed ports dictionary: {ports}")
            for container, port_mappings in ports.items():
                logger.info(f"Debug: Container {container} has port mappings: {port_mappings}")
                for port_mapping in port_mappings:
                    # Extract port numbers from strings like "0.0.0.0:3000->3000/tcp"
                    import re
                    matches = re.findall(r':(\d+)->', port_mapping)
                    logger.info(f"Debug: Found port matches in '{port_mapping}': {matches}")
                    port_numbers.extend(matches)
        else:
            logger.error(f"Unexpected ports format: {type(ports)}")
            return False
        
        logger.info(f"Debug: Final extracted port numbers: {port_numbers}")
        
        if not port_numbers:
            logger.warning("No ports found to scan")
            # For Docker deployments, check default exposed ports (nginx proxy)
            # From docker-compose.yml: nginx exposes GRAFANA_PORT:443 and 1883:1883
            default_ports = ["3000", "1883"]  # Default Docker exposed ports
            logger.info(f"Using default Docker exposed ports: {default_ports}")
            port_numbers = default_ports
            
        # Execute the nmap command to check for open ports
        port_list = ','.join(port_numbers)
        logger.info(f"Scanning ports {port_list} on target {target}")
        result = subprocess.run(['nmap', '-p', port_list, target], capture_output=True, text=True)

        # Print the nmap command response
        logger.info(result.stdout)

        # Analyze the output to determine if there are open ports
        if "open" in result.stdout:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False

def update_continuous_simulator_ingestion():
    try:
        # Define the sed command to update the line in the file
        opcua_file= constants.EDGE_AI_SUITES_DIR+"./simulator/opcua-server/opcua_server.py"
        sed_command = (
            f"sed -i 's/continous_simulator_ingestion = (os.getenv(\"CONTINUOUS_SIMULATOR_INGESTION\", \"true\")).lower()/"
            f"continous_simulator_ingestion = (os.getenv(\"CONTINUOUS_SIMULATOR_INGESTION\", \"false\")).lower()/' {opcua_file}"
        )

        # Execute the sed command
        subprocess.run(sed_command, shell=True, check=True)

        logger.info(f"Updated 'CONTINUOUS_SIMULATOR_INGESTION' to 'false' in opcua file {opcua_file}.")
    
        # Define the sed command to update the line in the file
        mqtt_file= constants.EDGE_AI_SUITES_DIR+"./simulator/mqtt-publisher/publisher.py"
        sed_command = (
            f"sed -i 's/continous_simulator_ingestion = (os.getenv(\"CONTINUOUS_SIMULATOR_INGESTION\", \"true\")).lower()/"
            f"continous_simulator_ingestion = (os.getenv(\"CONTINUOUS_SIMULATOR_INGESTION\", \"false\")).lower()/' {mqtt_file}"
        )
        
        # Execute the sed command
        subprocess.run(sed_command, shell=True, check=True)
        logger.info(f"Updated 'CONTINUOUS_SIMULATOR_INGESTION' to 'false' in mqtt file {mqtt_file}.")
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while updating the file: {e}")
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while updating the file: {e}")

def fetch_wind_turbine_data():
    try:
        # Read the CSV file into a DataFrame
        logger.info("Reading CSV file for wind turbine data...")
        csv_file_path = constants.EDGE_AI_SUITES_DIR + constants.WIND_INGESTED_CSV
        df = pd.read_csv(csv_file_path)
        logger.info("CSV file read successfully in path: " + csv_file_path)
        # Fetch the first record of the wind_power column
        first_wind_power = df['wind_speed'].iloc[0]
        # Fetch the last record of the wind_speed column
        last_wind_speed = df['wind_speed'].iloc[-1]
        # Get the total count of records
        total_records = len(df)
        return first_wind_power, last_wind_speed, total_records

    except FileNotFoundError:
        print(f"File not found: {constants.EDGE_AI_SUITES_DIR + './simulator/simulation_data/wind_turbine_data.csv'}")
        return None, None, None
    except KeyError as e:
        print(f"Column not found: {e}")
        return None, None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None

def verify_data_integrity_influxdb(chart_path, namespace, first_wind_speed, last_wind_speed, total_records):
    try:
        influxdb_username, influxdb_password = fetch_influxdb_credentials(chart_path)
        # Step 1: Find the InfluxDB pod name
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

        # Step 2: Execute InfluxDB commands inside the pod to fetch data
        influx_commands = (
            f"influx -username {influxdb_username} -password {influxdb_password} -database datain "
            f"-execute 'SELECT wind_speed FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\" ORDER BY time ASC LIMIT 1;'"
        )
        exec_command = f"kubectl exec -n {namespace} {pod_name} -- {influx_commands}"
        logger.info(f"Executing InfluxDB query inside pod: 'SELECT wind_speed FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\" ORDER BY time ASC LIMIT 1;' "
                    f"with redacted credentials.")
        result = subprocess.run(exec_command, shell=True, capture_output=True, text=True, check=True)
        first_record_response = result.stdout.strip()
        logger.info(f"First record response: {first_record_response}")

        # Parse the first record response
        influx_first_record = parse_influxdb_response(first_record_response)

        influx_commands = (
            f"influx -username {influxdb_username} -password {influxdb_password} -database datain "
            f"-execute 'SELECT wind_speed FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\" ORDER BY time DESC LIMIT 1;'"
        )
        exec_command = f"kubectl exec -n {namespace} {pod_name} -- {influx_commands}"
        logger.info(f"Executing InfluxDB query inside pod: 'SELECT wind_speed FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\" ORDER BY time DESC LIMIT 1;' "
                    f"with redacted credentials.")
        result = subprocess.run(exec_command, shell=True, capture_output=True, text=True, check=True)
        last_record_response = result.stdout.strip()
        logger.info(f"Last record response: {last_record_response}")

        # Parse the last record response
        influx_last_record = parse_influxdb_response(last_record_response)

        influx_commands = (
            f"influx -username {influxdb_username} -password {influxdb_password} -database datain "
            f"-execute 'SELECT COUNT(wind_speed) FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\";'"
        )
        exec_command = f"kubectl exec -n {namespace} {pod_name} -- {influx_commands}"
        logger.info(f"Executing InfluxDB query inside pod: 'SELECT COUNT(wind_speed) FROM \"{constants.WIND_TURBINE_INGESTED_TOPIC}\";' "
                    f"with redacted credentials.")
        result = subprocess.run(exec_command, shell=True, capture_output=True, text=True, check=True)
        count_response = result.stdout.strip()
        logger.info(f"Count response: {count_response}")

        # Parse the count response
        influx_total_count = parse_influxdb_response(count_response)
        # Convert all values to strings for comparison
        first_wind_speed = str(first_wind_speed)
        last_wind_speed = str(last_wind_speed)
        total_records = str(total_records)
        # Verify the data integrity
        if influx_first_record != first_wind_speed:
            logger.error(f"First record mismatch: InfluxDB={influx_first_record}, Expected={first_wind_speed}")
            return False

        if influx_last_record != last_wind_speed:
            logger.error(f"Last record mismatch: InfluxDB={influx_last_record}, Expected={last_wind_speed}")
            return False

        if influx_total_count != total_records:
            logger.error(f"Total count mismatch: InfluxDB={influx_total_count}, Expected={total_records}")
            return False

        logger.info("Data integrity verified successfully.")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred while executing commands: {e}")
        return False

def parse_influxdb_response(response):
    # Implement parsing logic based on the response format
    # This is a placeholder function and needs to be customized
    # according to the actual response format from InfluxDB
    return response.split('\n')[-1].split()[-1]  # Example parsing logic

def verify_docker_file_integrity():
    try:
        docker_compose_path = constants.EDGE_AI_SUITES_DIR + "/docker-compose.yml"
        logger.info(f"Reading docker-compose file from: {docker_compose_path}")
        with open(docker_compose_path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.info(f"Error reading docker-compose.yml: {e}")
        return False
    # Assume all services should have read_only: true
    all_services_read_only = True
    for service_name, service in data.get("services", {}).items():
        if service_name.startswith("ia-"):
            logger.info(f"Checking service with 'ia-' prefix: {service_name}")
            if service.get("read_only", False) is True:
                logger.info(f"Service '{service_name}' has read_only: true")
            else:
                logger.error(f"Service '{service_name}' does not have read_only: true")
                all_services_read_only = False
        else:
            logger.info(f"Service '{service_name}' is not an ia- service.")

    if all_services_read_only:
        logger.info("Docker file verification PASSED: All 'ia-' services have 'read_only: true'.")
        return True
    else:
        logger.error("Docker file verification FAILED: At least one 'ia-' service does not have 'read_only: true'.")
        return False

def verify_helm_file_integrity():
    """
    Check for security settings in specified YAML files:
    - For time-series-analytics-microservice.yaml: Special conditional pattern with privileged access
    - For other files: readOnlyRootFilesystem: true and allowPrivilegeEscalation: false
    
    :return: True if all security settings are correct in all specified files, False otherwise.
    """
    directory = constants.EDGE_AI_SUITES_DIR + "/helm/templates"
    target_files = [
        'broker.yaml', 'opcua.yaml', 'time-series-analytics-microservice.yaml',
        'grafana.yaml', 'mqtt-publisher.yaml', 'influxdb.yaml', 'telegraf.yaml', 'nginx.yaml'
    ]

    # Define regular expressions for standard files
    correct_read_only_regex = re.compile(r'readOnlyRootFilesystem:\s*true')
    incorrect_read_only_regex = re.compile(r'readOnlyRootFilesystem:\s*false')
    correct_privilege_escalation_regex = re.compile(r'allowPrivilegeEscalation:\s*false')
    incorrect_privilege_escalation_regex = re.compile(r'allowPrivilegeEscalation:\s*true')
    
    # Special patterns for time-series-analytics-microservice.yaml
    time_series_conditional_pattern = re.compile(
        r'{{\-\s*if\s+\.Values\.privileged_access_required\s*}}\s*'
        r'privileged:\s*true.*?'
        r'allowPrivilegeEscalation:\s*true\s*'
        r'{{\-\s*else\s*}}\s*'
        r'privileged:\s*false\s*'
        r'allowPrivilegeEscalation:\s*false\s*'
        r'{{\-\s*end\s*}}',
        re.DOTALL
    )
    
    all_files_passed = True

    for root, _, files in os.walk(directory):
        for file in files:
            if file in target_files:
                file_path = os.path.join(root, file)
                logger.info(f"Checking file: {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    if file == 'time-series-analytics-microservice.yaml':
                        # Special validation for time-series file
                        file_has_issues = False
                        issues = []

                        # Check for readOnlyRootFilesystem: true (required in all cases)
                        if not correct_read_only_regex.search(content):
                            file_has_issues = True
                            issues.append("Missing 'readOnlyRootFilesystem: true'")
                        
                        if incorrect_read_only_regex.search(content):
                            file_has_issues = True
                            issues.append("Found 'readOnlyRootFilesystem: false' (should be true)")

                        # Check for the conditional privileged access pattern
                        if not time_series_conditional_pattern.search(content):
                            file_has_issues = True
                            issues.append("Missing or incorrect conditional privileged access pattern")
                            
                            # Additional checks to provide more specific feedback
                            if not re.search(r'{{\-\s*if\s+\.Values\.privileged_access_required\s*}}', content):
                                issues.append("Missing '{{- if .Values.privileged_access_required }}' condition")
                            
                            if not re.search(r'{{\-\s*else\s*}}', content):
                                issues.append("Missing '{{- else }}' clause")
                            
                            if not re.search(r'{{\-\s*end\s*}}', content):
                                issues.append("Missing '{{- end }}' clause")

                        if file_has_issues:
                            logger.error(f"Security issues found in {file_path}:")
                            for issue in issues:
                                logger.error(f"  - {issue}")
                            all_files_passed = False
                        else:
                            logger.info(f"Correct conditional security pattern found in {file_path}: "
                                      f"readOnlyRootFilesystem: true ✓, conditional privileged access pattern ✓")

                    else:
                        # Standard validation for other files
                        file_has_issues = False
                        issues = []

                        # Check for incorrect settings
                        if incorrect_read_only_regex.search(content):
                            file_has_issues = True
                            issues.append("Found 'readOnlyRootFilesystem: false' (should be true)")
                        
                        if incorrect_privilege_escalation_regex.search(content):
                            file_has_issues = True
                            issues.append("Found 'allowPrivilegeEscalation: true' (should be false)")
                        
                        # Check for required correct settings
                        if not correct_read_only_regex.search(content):
                            file_has_issues = True
                            issues.append("Missing 'readOnlyRootFilesystem: true'")
                        
                        if not correct_privilege_escalation_regex.search(content):
                            file_has_issues = True
                            issues.append("Missing 'allowPrivilegeEscalation: false'")

                        if file_has_issues:
                            logger.error(f"Security issues found in {file_path}:")
                            for issue in issues:
                                logger.error(f"  - {issue}")
                            all_files_passed = False
                        else:
                            logger.info(f"Correct security settings found in {file_path}: "
                                      f"readOnlyRootFilesystem: true ✓, allowPrivilegeEscalation: false ✓")

                except FileNotFoundError:
                    logger.error(f"File not found: {file_path}")
                    return False
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
                    return False

    if all_files_passed:
        logger.info("Test case passed: All specified files have correct security settings.")
        return True
    else:
        logger.error("Test case failed: Security issues found in one or more specified files.")
        return False
    
def extract_docker_exposed_ports():
    """
    Extract port numbers from Docker exposed ports for nmap scanning.
    
    Returns:
        list: List of integer port numbers that are exposed
    """
    try:
        exposed_ports_dict = find_exposed_ports_docker()
        if not exposed_ports_dict:
            return []
        
        ports = []
        for container_name, port_list in exposed_ports_dict.items():
            for port_info in port_list:
                # Extract port from format "0.0.0.0:8086->8086/tcp"
                if '->' in port_info:
                    external_port = port_info.split('->')[0].split(':')[-1]
                    ports.append(int(external_port))
        
        # Remove duplicates and return
        return list(set(ports))
        
    except Exception as e:
        logger.error(f"Error extracting Docker exposed ports: {e}")
        return []

def fetch_docker_credentials(credential_type):
    """
    Fetch credentials from .env file for Docker deployment.
    
    Args:
        credential_type (str): Type of credentials to fetch ('influxdb' or 'grafana')
        
    Returns:
        tuple: (username, password) or (None, None) if not found
    """
    try:
        env_path = os.path.join(constants.EDGE_AI_SUITES_DIR, ".env")
        logger.info(f"Fetching {credential_type} credentials from: {env_path}")

        with open(env_path, 'r') as file:
            lines = file.readlines()

        if credential_type == "influxdb":
            username_key = "INFLUXDB_USERNAME="
            password_key = "INFLUXDB_PASSWORD="
        elif credential_type == "grafana":
            username_key = "VISUALIZER_GRAFANA_USER="
            password_key = "VISUALIZER_GRAFANA_PASSWORD="
        else:
            logger.error(f"Unknown credential type: {credential_type}")
            return None, None

        username = None
        password = None
        
        for line in lines:
            line = line.strip()
            if line.startswith(username_key):
                username = line.split('=', 1)[1]
            elif line.startswith(password_key):
                password = line.split('=', 1)[1]
        
        # Note: Not logging credentials for security reasons  
        logger.info(f"Successfully retrieved {credential_type.upper()} credentials from .env file")
        return username, password
        
    except FileNotFoundError:
        logger.error(f"File not found: {env_path}")
        return None, None
    except Exception as e:
        logger.error(f"Error fetching {credential_type} credentials: {e}")
        return None, None

def influxdb_login_docker(container_name="ia-influxdb"):
    """Execute InfluxDB commands inside the Docker container to verify authentication."""
    logger.info(f"Testing InfluxDB authentication in Docker container '{container_name}'...")
    try:
        # Get InfluxDB credentials from .env file
        influxdb_username, influxdb_password = fetch_docker_credentials("influxdb")
        
        if not influxdb_username or not influxdb_password:
            logger.error("Failed to get InfluxDB credentials from .env file.")
            return False

        # Use environment variable to pass password securely to InfluxDB CLI
        # The InfluxDB CLI reads INFLUX_PASSWORD from environment
        influx_commands = (
            f"influx -username {influxdb_username} -database datain "
            "-execute 'SHOW MEASUREMENTS'"
        )
        exec_command = f"docker exec -e INFLUX_PASSWORD={influxdb_password} {container_name} {influx_commands}"
        logger.info(f"Executing InfluxDB command - 'SHOW MEASUREMENTS'  in container '{container_name}' with configured credentials (credentials not shown)")
        
        result = subprocess.run(exec_command, shell=True, capture_output=True, text=True)
        response = result.stdout.strip()
        error_output = result.stderr.strip()
        
        logger.info(f"InfluxDB command exit code: {result.returncode}")
        if response:
            logger.info(f"InfluxDB response: {response}")
        if error_output:
            logger.info(f"InfluxDB stderr: {error_output}")
        
        # Check if command was successful - returncode 0 means authentication worked
        if result.returncode == 0:
            logger.info("InfluxDB Docker authentication successful.")
            return True
        else:
            logger.error(f"InfluxDB Docker authentication failed with exit code: {result.returncode}")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"InfluxDB Docker login command failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error during InfluxDB Docker login: {e}")
        return False

async def login_to_grafana_docker(port=3000):
    """Login to Grafana running in Docker container on specified port."""
    try:
        # Get Grafana credentials from .env file
        grafana_username, grafana_password = fetch_docker_credentials("grafana")
        
        if not grafana_username or not grafana_password:
            logger.error("Failed to get Grafana credentials from .env file.")
            return False
        
        # For Docker deployment, Grafana is accessible via nginx proxy on HTTPS
        # The nginx service exposes ${GRAFANA_PORT}:443 (HTTPS)
        # Only test HTTPS path - HTTP working would be a security bug
        grafana_url = f"https://localhost:{port}"
        
        logger.info(f"Attempting to login to Grafana at: {grafana_url}")
        
        # Use the existing Grafana login function
        result = await login_to_grafana(grafana_url, grafana_username, grafana_password)
        if result:
            return True
        
        logger.error("Failed to login to Grafana via HTTPS")
        return False
        
    except Exception as e:
        logger.error(f"Error during Grafana Docker login: {e}")
        return False


# ===========================
# Port Utilities
# ===========================

def read_env_file(env_file_path: str):
    """
    Read environment variables from .env file.
    
    Args:
        env_file_path: Path to the .env file
        
    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    
    try:
        with open(env_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        logger.warning(f".env file not found at {env_file_path}")
    
    return env_vars


def get_docker_ports_from_env(project_root: str = None):
    """
    Get Docker port mappings from .env file.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        Dictionary mapping service names to port numbers
    """
    if project_root is None:
        # Default to the wind turbine project directory
        project_root = "/home/user/WW35_NMAP/frameworks.ai.ai-suite-for-timeseries/edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection"
    
    env_file_path = os.path.join(project_root, ".env")
    env_vars = read_env_file(env_file_path)
    
    # Map environment variable names to service names
    port_mapping = {}
    
    # From .env file, we can see:
    # GRAFANA_PORT=3000 -> maps to ia-grafana service
    # OPCUA_SERVER_PORT=30003 -> maps to ia-opcua-server service (but internally uses 4840)
    # Time series analytics uses hardcoded 5000 in docker-compose
    # MQTT broker uses hardcoded 1883 in docker-compose
    
    if 'GRAFANA_PORT' in env_vars:
        port_mapping['grafana'] = int(env_vars['GRAFANA_PORT'])
    
    if 'OPCUA_SERVER_PORT' in env_vars:
        port_mapping['opcua'] = int(env_vars['OPCUA_SERVER_PORT'])
    else:
        port_mapping['opcua'] = constants.OPCUA_SERVER_PORT  # Default internal port for OPC UA server
    
    # These are hardcoded in docker-compose.yml
    port_mapping['mqtt'] = 1883
    port_mapping['time_series_analytics'] = 5000
    
    if 'MR_SERVER_PORT' in env_vars:
        port_mapping['model_registry'] = int(env_vars['MR_SERVER_PORT'])
    
    return port_mapping


def parse_docker_compose_ports(docker_compose_path: str):
    """
    Parse port mappings from docker-compose.yml file.
    
    Args:
        docker_compose_path: Path to docker-compose.yml file
        
    Returns:
        Dictionary mapping service names to list of exposed ports
    """
    ports_by_service = {}
    
    try:
        with open(docker_compose_path, 'r') as file:
            compose_data = yaml.safe_load(file)
        
        if 'services' in compose_data:
            for service_name, service_config in compose_data['services'].items():
                if 'ports' in service_config:
                    service_ports = []
                    for port_mapping in service_config['ports']:
                        # Handle different port mapping formats
                        if isinstance(port_mapping, str):
                            # Format: "5000:5000" or "1883:1883"
                            if ':' in port_mapping:
                                host_port = port_mapping.split(':')[0]
                                # Remove any environment variable syntax
                                host_port = re.sub(r'^\$\{.*\}$', '', host_port)
                                if host_port.isdigit():
                                    service_ports.append(int(host_port))
                        elif isinstance(port_mapping, int):
                            service_ports.append(port_mapping)
                    
                    if service_ports:
                        # Simplify service name (remove ia- prefix)
                        simple_name = service_name.replace('ia-', '').replace('-', '_')
                        ports_by_service[simple_name] = service_ports
    
    except FileNotFoundError:
        logger.warning(f"docker-compose.yml not found at {docker_compose_path}")
    except yaml.YAMLError as e:
        logger.warning(f"Error parsing docker-compose.yml: {e}")
    
    return ports_by_service


def get_docker_ports_from_compose(project_root: str = None):
    """
    Get Docker port mappings by parsing docker-compose.yml and .env files.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        Dictionary mapping service names to port numbers
    """
    if project_root is None:
        project_root = "/home/user/WW35_NMAP/frameworks.ai.ai-suite-for-timeseries/edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection"
    
    docker_compose_path = os.path.join(project_root, "docker-compose.yml")
    env_vars = read_env_file(os.path.join(project_root, ".env"))
    
    # Parse docker-compose.yml for port mappings
    ports_by_service = parse_docker_compose_ports(docker_compose_path)
    
    # Create final port mapping
    port_mapping = {}
    
    # Get ports from parsed compose file
    for service, ports in ports_by_service.items():
        if ports:
            port_mapping[service] = ports[0]  # Take first port if multiple
    
    # Handle environment variable substitutions
    if 'grafana' in port_mapping and 'GRAFANA_PORT' in env_vars:
        port_mapping['grafana'] = int(env_vars['GRAFANA_PORT'])
    
    if 'opcua_server' in port_mapping and 'OPCUA_SERVER_PORT' in env_vars:
        port_mapping['opcua'] = int(env_vars['OPCUA_SERVER_PORT'])
    else:
        port_mapping['opcua'] = constants.OPCUA_SERVER_PORT  # Default internal port for OPC UA server
    
    return port_mapping


def get_dynamic_ports(project_root: str = None):
    """
    Get port numbers dynamically from configuration files.
    This is the main function to use instead of hardcoded ports.
    
    Args:
        project_root: Root directory of the project
    
    Returns:
        Dictionary with port mappings: {'grafana': 3000, 'mqtt': 1883, ...}
    """
    try:
        # Try to get ports from docker-compose and .env files
        ports = get_docker_ports_from_compose(project_root)
        
        # Ensure we have all required ports with fallback values
        default_ports = {
            'grafana': 3000,
            'mqtt': 1883,
            'time_series_analytics': 5000,
            'opcua': 4840  # Internal port, not the exposed port
        }
        
        # Merge with defaults for any missing ports
        for service, default_port in default_ports.items():
            if service not in ports:
                ports[service] = default_port
        
        return ports
        
    except Exception as e:
        logger.warning(f"Could not read dynamic ports, using defaults: {e}")
        # Fallback to default ports
        return {
            'grafana': 3000,
            'mqtt': 1883,
            'time_series_analytics': 5000,
            'opcua': 4840
        }


def get_ports_for_environment(environment: str = "docker", project_root: str = None):
    """
    Get port numbers based on the deployment environment.
    
    Args:
        environment: "docker" or "helm"
        project_root: Root directory of the project
        
    Returns:
        Dictionary or list of port numbers based on environment
    """
    if environment.lower() == "docker":
        # For Docker, return dynamic ports from config files
        return get_dynamic_ports(project_root)
    elif environment.lower() == "helm":
        # For Helm, use the existing function to get exposed ports
        # This would need namespace parameter in real usage
        return []  # Placeholder - would call find_exposed_ports_helm(namespace)
    else:
        logger.error(f"Unknown environment: {environment}")
        return {}
