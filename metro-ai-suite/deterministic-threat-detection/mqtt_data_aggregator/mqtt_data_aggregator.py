"""
MQTT Data Aggregator and Real-Time Latency Visualizer.

This script connects to multiple MQTT brokers, subscribes to specified topics,
and calculates the end-to-end latency of messages based on PTP timestamps.
It then visualizes these latencies in a real-time web-based dashboard using Dash.

The script is designed to monitor the performance of a Time-Sensitive Networking (TSN)
setup by displaying how network conditions affect data delivery for different
streams (e.g., from cameras and sensors).
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
from collections import deque
from threading import Lock

import dash
import paho.mqtt.client as mqtt
import plotly.graph_objs as go
from dash import dcc, html
from dash.dependencies import Input, Output

# --- Default Configuration ---
DEFAULT_BROKER_PORT = 1883
DEFAULT_TOPICS_BROKERS = [
    "tsn_demo/camera1/inference:localhost",
    "tsn_demo/camera2/inference:localhost",
    "sample/sensor/data:localhost"
]
DEFAULT_WINDOW_SECONDS = 2
DEFAULT_Y_AXIS_MIN = 0
DEFAULT_Y_AXIS_MAX = 5

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global Data Structures ---
data_lock = Lock()
data_store = {}
active_clients = []
last_update_times = {}


# --- Argument Parsing ---
def parse_arguments():
    """Parse command-line arguments for the aggregator and visualizer."""
    parser = argparse.ArgumentParser(
        description="Multi-Broker MQTT Data Aggregator and Visualizer")
    parser.add_argument("--topic-brokers", nargs='+', default=DEFAULT_TOPICS_BROKERS,
                        help="List of 'topic:broker_ip_address' pairs (e.g., 'topic1:broker1_ip' 'topic2:broker2_ip')")
    parser.add_argument("--port", type=int, default=DEFAULT_BROKER_PORT, help="Default MQTT broker port")
    parser.add_argument("--window-seconds", type=int, default=DEFAULT_WINDOW_SECONDS, help="Time window in seconds to display on the plot")
    parser.add_argument("--y-min", type=float, default=DEFAULT_Y_AXIS_MIN, help="Y-axis minimum value")
    parser.add_argument("--y-max", type=float, default=DEFAULT_Y_AXIS_MAX, help="Y-axis maximum value")
    parser.add_argument("--dash-port", type=int, default=8050, help="Port for the Dash web interface")
    return parser.parse_args()


# --- MQTT Callbacks ---
def on_connect_factory(broker_address, topic):
    """
    Factory function to create an on_connect callback for a specific broker and topic.

    This allows each MQTT client to have a unique callback that logs its
    connection status and subscribes to its designated topic.

    Args:
        broker_address (str): The address of the MQTT broker.
        topic (str): The topic to subscribe to upon connection.

    Returns:
        function: The on_connect callback function.
    """
    def on_connect(client, userdata, flags, rc, properties=None):
        """Callback executed when the client connects to the MQTT broker."""
        if rc == 0:
            logging.info(f"Connected to MQTT Broker at {broker_address} for topic {topic}")
            client.subscribe(topic, qos=1)
            logging.info(f"Subscribed to topic: {topic}")
        else:
            logging.error(f"Failed to connect to {broker_address}, return code {rc}")
    return on_connect


def on_disconnect_factory(broker_address):
    """
    Factory function to create an on_disconnect callback.

    Args:
        broker_address (str): The address of the MQTT broker for logging.

    Returns:
        function: The on_disconnect callback function.
    """
    def on_disconnect(client, userdata, rc, properties=None):
        """Callback executed when the client disconnects from the MQTT broker."""
        logging.warning(
            f"Disconnected from MQTT Broker at {broker_address} (code: {rc}).")
    return on_disconnect


def on_message(client, userdata, message):
    """
    Callback executed when a message is received from an MQTT broker.

    It calculates the latency from the timestamp in the message payload
    and stores it for visualization.
    """
    try:
        current_time = time.time()
        payload = json.loads(message.payload)
        topic = message.topic

        if "sensor" in topic:
            timestamp = payload.get('timestamp')
        else:
            timestamp = payload.get('metadata', {}).get('ptp_timestamp')

        if timestamp is None:
            logging.warning(f"Timestamp not found in message on topic {topic}")
            return

        latency = (current_time - timestamp)

        with data_lock:
            if topic in data_store:
                data_store[topic]["timestamps"].append(current_time)
                data_store[topic]["latencies"].append(latency)
                last_update_times[topic] = current_time

    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error processing message on topic {message.topic}: {e}")


# --- Dash App ---
def create_dash_app(args):
    """
    Create and configure the Dash application for real-time visualization.

    Args:
        args: The parsed command-line arguments.

    Returns:
        dash.Dash: The configured Dash application instance.
    """
    app = dash.Dash(__name__)
    app.layout = html.Div([
        html.H1("Real-Time TSN Latency Monitor"),
        dcc.Graph(id='latency-plot'),
        dcc.Interval(id='interval-update', interval=1000, n_intervals=0)
    ])

    @app.callback(Output('latency-plot', 'figure'), Input('interval-update', 'n_intervals'))
    def update_plot(n):
        """
        Callback to update the latency plot at regular intervals.

        This function is triggered by the dcc.Interval component. It prunes old
        data, redraws the plot with the latest latency information, and adjusts
        the y-axis dynamically to fit the data.

        Args:
            n (int): The number of intervals that have passed (not used).

        Returns:
            dict: A dictionary representing the updated Plotly figure.
        """
        traces = []
        current_time = time.time()
        start_time = current_time - args.window_seconds
        max_latency = 0
        
        with data_lock:
            for topic, data in data_store.items():
                # Prune data older than the time window
                while data["timestamps"] and data["timestamps"][0] < start_time:
                    data["timestamps"].popleft()
                    data["latencies"].popleft()

                # Find the max latency in the current window for this topic
                for lat in data["latencies"]:
                    if lat is not None and lat > max_latency:
                        max_latency = lat

                # Create a consistent set of timestamps for plotting
                plot_timestamps = [start_time] + list(data["timestamps"]) + [current_time]
                plot_latencies = [None] + list(data["latencies"]) + [None]

                traces.append(go.Scatter(
                    x=plot_timestamps,
                    y=plot_latencies,
                    mode='lines+markers',
                    name=topic,
                    connectgaps=False # This is important to show breaks
                ))
        
        # Determine the y-axis range
        y_axis_range = [args.y_min, args.y_max]
        if max_latency > args.y_max:
            y_axis_range[1] = max_latency * 1.1  # Add 10% buffer

        return {
            'data': traces,
            'layout': go.Layout(
                xaxis={'title': 'Time', 'range': [start_time, current_time]},
                yaxis={'title': 'End-to-End Latency (seconds)', 'range': y_axis_range},
                legend={'x': 0.01, 'y': 0.99, 'bgcolor': 'rgba(255,255,255,0.8)', 'bordercolor': 'black', 'borderwidth': 1},
                margin={'l': 60, 'r': 40, 't': 40, 'b': 40}
            )
        }
    return app


# --- Main Execution ---
def main(args):
    """
    Main function to set up MQTT clients and run the Dash application.

    Initializes data storage, configures and connects MQTT clients for each
    specified topic-broker pair, and starts the web server for the
    Dash visualization dashboard.

    Args:
        args: The parsed command-line arguments.
    """
    # Initialize data storage
    for item in args.topic_brokers:
        topic, broker = item.split(':')
        if topic not in data_store:
            data_store[topic] = {
                "timestamps": deque(),
                "latencies": deque()
            }
            last_update_times[topic] = 0

    # Setup and connect MQTT clients
    for item in args.topic_brokers:
        topic, broker_address = item.split(':')
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect_factory(broker_address, topic)
        client.on_disconnect = on_disconnect_factory(broker_address)
        client.on_message = on_message
        client.reconnect_delay_set(min_delay=1, max_delay=120)
        
        try:
            client.connect_async(broker_address, args.port, 60)
            client.loop_start()
            active_clients.append(client)
            logging.info(f"Initiating connection to {broker_address} for topic {topic}")
        except (ConnectionRefusedError, OSError) as e:
            logging.error(f"Fatal: Could not connect to {broker_address}. {e}")

    # Create and run Dash app
    app = create_dash_app(args)
    app.run(debug=False, host='0.0.0.0', port=args.dash_port, use_reloader=False)

    # Cleanup on exit
    for client in active_clients:
        client.loop_stop()
        client.disconnect()
    logging.info("Application finished.")


def signal_handler(sig, frame):
    """
    Handle termination signals (SIGINT, SIGTERM) for graceful shutdown.

    Args:
        sig: The signal number.
        frame: The current stack frame.
    """
    logging.info("Termination signal received. Shutting down...")
    os.kill(os.getpid(), signal.SIGTERM)


if __name__ == '__main__':
    args = parse_arguments()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main(args)

