"""
Simulated Sensor Data Producer for MQTT.

This script simulates a sensor device that generates and publishes data to an MQTT
broker at a specified rate. The data is sent as a JSON payload containing a
timestamp, a sample number, and a simulated sensor value.

It is intended for use in testing and demonstrating data pipelines, particularly
in scenarios like the Time-Sensitive Networking (TSN) use case where a stream of
time-stamped data is required.
"""

# 
# Copyright (C) 2026 Intel Corporation. 
# 
# SPDX-License-Identifier: Apache-2.0 
#

import argparse
import json
import logging
import os
import signal
import time
import paho.mqtt.client as mqtt

# Default Configuration
DEFAULT_BROKER = "localhost"
DEFAULT_PORT = 1883
DEFAULT_TOPIC = "sample/sensor/data"
DEFAULT_RATE_HZ = 30

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global State
running = True

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback executed when the client successfully connects to the MQTT broker."""
    if rc == 0:
        logging.info("Connected to MQTT Broker!")
    else:
        logging.error(f"Failed to connect, return code {rc}\n")

def on_disconnect(client, userdata, rc, properties=None):
    """Callback executed when the client disconnects from the MQTT broker."""
    logging.warning(
        f"Disconnected from MQTT Broker with result code {rc}. Reconnecting...")


def parse_arguments():
    """
    Parse command-line arguments for the data producer.

    Allows configuration of the MQTT broker address, port, topic, and the
    publishing rate. Values can also be set via environment variables.

    Returns:
        argparse.Namespace: An object containing the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="MQTT Sensor Data Producer")
    parser.add_argument("--broker", type=str, default=os.getenv("MQTT_BROKER", DEFAULT_BROKER),
                        help=f"MQTT broker address (default: {DEFAULT_BROKER})")
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", DEFAULT_PORT)),
                        help=f"MQTT broker port (default: {DEFAULT_PORT})")
    parser.add_argument("--topic", type=str, default=os.getenv("MQTT_TOPIC", DEFAULT_TOPIC),
                        help=f"MQTT topic to publish to (default: {DEFAULT_TOPIC})")
    parser.add_argument("--rate", type=float, default=float(os.getenv("PUBLISH_RATE_HZ", DEFAULT_RATE_HZ)),
                        help=f"Publishing rate in Hz (default: {DEFAULT_RATE_HZ})")
    return parser.parse_args()

def signal_handler(sig, frame):
    """
    Handle termination signals (SIGINT, SIGTERM) for graceful shutdown.

    Sets a global flag to signal the main loop to exit cleanly.

    Args:
        sig: The signal number.
        frame: The current stack frame.
    """
    global running
    logging.info("Termination signal received. Shutting down...")
    running = False

def run_producer(args):
    """
    Main function to connect to MQTT and run the data production loop.

    This function initializes the MQTT client, connects to the broker, and enters
    a loop to publish simulated sensor data at a precise rate determined by the
    '--rate' argument. It handles connection errors and ensures a clean shutdown.

    Args:
        args: An object containing the parsed command-line arguments.
    """
    global running
    interval = 1.0 / args.rate

    # Initialize Client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Enable automatic reconnect
    client.reconnect_delay_set(min_delay=1, max_delay=120)

    try:
        client.connect(args.broker, args.port, 60)
    except (ConnectionRefusedError, OSError) as e:
        logging.error(f"Connection to MQTT broker failed: {e}")
        return

    client.loop_start()

    logging.info(f"Publishing JSON to topic '{args.topic}' at {args.rate} Hz...")

    count = 0
    next_time = time.perf_counter()

    while running:
        try:
            # 1. Create a structured data dictionary
            data = {
                "id": "sensor_01",
                "timestamp": time.time(),
                "sample_no": count,
                "value": 22.5 + (count % 10) * 0.1  # Example dynamic data
            }

            # 2. Convert dictionary to JSON string
            json_payload = json.dumps(data)

            # 3. Publish
            result = client.publish(args.topic, payload=json_payload, qos=0)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logging.warning(f"Failed to publish message: {mqtt.error_string(result.rc)}")


            count += 1

            # 4. Precise Timing Loop
            next_time += interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.1: # Reset timing if we're too far behind
                next_time = time.perf_counter() + interval


        except Exception as e:
            logging.error(f"An error occurred in the main loop: {e}")
            time.sleep(1) # Avoid rapid-fire errors

    logging.info("Exiting main loop.")
    client.loop_stop()
    client.disconnect()
    logging.info("MQTT client disconnected.")

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Parse arguments and run the producer
    args = parse_arguments()
    run_producer(args)
    logging.info("Application finished.")

