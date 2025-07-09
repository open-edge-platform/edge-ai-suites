#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from asyncua.sync import Server
from asyncua import ua
from datetime import datetime
import time
import pandas as pd
import logging
import os
import socket

# Configure logging

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)
logger = logging.getLogger(__name__)


def is_port_accessible():
    """
    Check if a port is accessible on a given host.

    :param host: The hostname or IP address to check.
    :param port: The port number to check.
    :param timeout: The timeout in seconds for the connection attempt.
    :return: True if the port is accessible, False otherwise.
    """
    host = os.getenv("TS_MS_SERVER", "ia-time-series-analytics-microservice")
    port = int(os.getenv("TS_MS_PORT", 9092))
    logger.info(f"Waiting for {host} accessible...")
    while(True):
        try:
            # Create a socket object
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Set the timeout for the connection attempt
                sock.settimeout(5)
                # Attempt to connect to the host and port
                sock.connect((host, port))
            logger.info(f"{host} is accessible...")
            return True
        except (socket.timeout, socket.error) as e:
            pass
        time.sleep(1)
is_port_accessible()

time.sleep(5)  # Wait for 5 seconds before starting the server to avoid the sync issue
# Create OPC UA server instance
server = Server()

# Set server endpoint (URL for clients to connect)
server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
# Set server name
server.set_server_name("OPCUA Test Server")

# Check if secure mode is enabled
if (os.getenv("SECURE_MODE", "false")).lower() == "true":
    server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
    server.load_certificate("/run/secrets/opcua-server_Server_server_certificate.pem")
    server.load_private_key("/run/secrets/opcua-server_Server_server_key.pem")

else:
    server.set_security_policy([
        ua.SecurityPolicyType.NoSecurity,
    ])

continous_simulator_ingestion = (os.getenv("CONTINUOUS_SIMULATOR_INGESTION", "true")).lower()

# Create a new namespace for your objects
uri = "urn:freeopcua:python:server"
idx = server.register_namespace(uri)

data = pd.read_csv('./windturbine_data.csv')

# Add a new object to the server
myobj = server.nodes.objects.add_object(idx, "MyObject")

# Add variables to the object
grid_active_power = myobj.add_variable(idx, "grid_active_power", data['grid_active_power'][0])
wind_speed = myobj.add_variable(idx, "wind_speed", data['wind_speed'][0])
alert_message = myobj.add_variable(idx, "alert_message", "")

# Allow writing to variables
grid_active_power.set_writable()
wind_speed.set_writable()
alert_message.set_writable()

# Start the server
server.start()

logger.info(f"grid_active_power Node ID:{grid_active_power.nodeid}")
logger.info(f"wind_speed Node ID:, {wind_speed.nodeid}")
logger.info(f"alert_message Node ID:, {alert_message.nodeid}")

# logger.info("Server started at {}".format(server.endpoint))
i = 0
try:
    while True:
        # Update variable values
        grid_active_power.set_value(data['grid_active_power'][i])
        logger.debug(f"grid_active_power updated {grid_active_power.get_value()}")
        wind_speed.set_value(data['wind_speed'][i])
        logger.debug(f"wind_speed updated {wind_speed.get_value()}")

        time.sleep(1)  # 1-second delay
        i += 1
        if i >= len(data):
            if continous_simulator_ingestion == "false":
                logger.info("End of data reached.")
                grid_active_power.delete()
                wind_speed.delete()
                break
            i = 0

except KeyboardInterrupt:
    print("Server is shutting down...")
    server.stop()

