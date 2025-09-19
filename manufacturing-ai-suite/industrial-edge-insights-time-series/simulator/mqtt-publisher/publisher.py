#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Sample MQTT publisher to publish the input data.
"""

import json
import time
import argparse
import re
import sys
import os
from multiprocessing import Process
import ssl
import socket
import glob
import paho.mqtt.client as mqtt
import pandas as pd


SERVICE = 'mqtt'
SAMPLING_RATE = 10  # 500.0 # 2msecdd
SUBSAMPLE = 1  # 1:every row, 500: every 500 rows (ie. every 1 sec)
POINTSPERPROCESS = 350
HOST = 'localhost'
PROCS = []
DATA_PUBLISH_WAIT_PERIOD = 10


def g_tick(period=1):
    """generate the tick
    """
    start_time = time.time()
    period_count = 0
    while True:
        period_count += 1
        yield max(start_time + period_count * period - time.time(), 0)


def parse_args():
    """Parse command line arguments.
    """
    a_p = argparse.ArgumentParser()
    a_p.add_argument('--host', default='localhost', help='MQTT broker host')
    a_p.add_argument('--port', default=1883, type=int,
                     help='MQTT broker port')
    a_p.add_argument('--qos', default=1, type=int, help='MQTT publish qos')
    a_p.add_argument('--interval', default=1, type=float,
                     help='MQTT publication interval')
    a_p.add_argument('--csv', default=None, type=str,
                     help='CSV file to publish to MQTT broker')
    a_p.add_argument('--topic', default=None, type=str,
                     help='MQTT topic name to publish to')
    a_p.add_argument('--json', default=None, type=str,
                     help='folder containing json file(s) to publish'
                     'to MQTT broker')
    a_p.add_argument('--subsample', default=SUBSAMPLE, type=float)
    a_p.add_argument('--sampling_rate', default=SAMPLING_RATE, type=float,
                     help='Data Sampling Rate')
    a_p.add_argument('--streams', default=1, type=int,
                     help='Number of MQTT streams to send.'
                     'This should correspond to the number of brokers running')
    a_p.add_argument('--output', default=None, type=str,
                     help='Output file path')
    a_p.add_argument('--service', default=SERVICE, type=str,
                     help='service tool for publish data')
    return a_p.parse_args()


def stream_csv(mqttc, topic, subsample, sampling_rate, filename):
    """
    Stream the csv file
    """
    continous_simulator_ingestion = os.getenv("CONTINUOUS_SIMULATOR_INGESTION", "true").lower()

    print(f"\nMQTT Topic - {topic}\nSubsample - {subsample}\nSampling Rate - \
          {sampling_rate}\nFilename - {filename}\n")
    jencoder = json.JSONEncoder()
    csv_data = pd.read_csv(filename, nrows=0)
    columns = csv_data.columns.tolist()
    chunk_size = 1000
    while True:
        start_time = time.time()
        row_served = 0

        tick = g_tick(float(subsample) / float(sampling_rate))

        for chunk in pd.read_csv(filename, chunksize=chunk_size):
            for _, row in chunk.iterrows():

                if subsample > 1 and (row_served % subsample) != 0:
                    row_served += 1
                    continue

                try:
                    msg = jencoder.encode({col: row[col] for col in columns})
                    print("Publishing message", msg)
                    mqttc.publish(topic, msg)
                except (ValueError, IndexError):
                    print(f"Skipping row {row_served}- {row} due to ValueError: {ValueError} \
                          or IndexError: {IndexError}")
                    continue

                row_served += 1
                time.sleep(next(tick))
                if row_served % max(1, int(sampling_rate) // max(1, int(subsample))) == 0:
                    print(f'{row_served} rows served in {time.time() - start_time:.2f} seconds')

        print(f'{filename} Done! {row_served} rows served in {time.time() - start_time:.2f} \
              seconds')
        if continous_simulator_ingestion == "false":
            print("End of data reached.")
            while True:
                time.sleep(1)


def send_json_cb(instance_id, host, port, topic, data, qos, service):
    """ Send JSON
    """
    if service == "benchmarking":
        client = mqtt.Client(str(port))
    else:
        client = mqtt.Client(str(instance_id))
    client.on_disconnect = on_disconnect
    client.on_connect = on_connect
    client.connect(host, port, 60)
    client.loop_start()
    if service == "benchmarking":
        for _ in range(0, POINTSPERPROCESS):
            t_s = time.time()
            for value in data:
                msg = {'ts': t_s, 'value': value}
                client.publish(topic, json.dumps(msg), qos=qos)
                time.sleep(instance_id)
    else:
        try:
            while True:
                t_s = time.time()
                for value in data:
                    msg = {'ts': t_s, 'value': value}
                    client.publish(topic, json.dumps(msg), qos=qos)
                    time.sleep(1)
        except KeyboardInterrupt:
            client.loop_stop()


def publish_json(mqttc, topic, path, qos, argsinterval, streams, host, port, service):
    """ Publish the JSON file
    """
    data = []
    path = path.replace("\\*", "*")
    files = glob.glob(path)
    for file in files:
        with open(file) as fpd:
            data.append(fpd.read())
    print("Publishing json files to mqtt in loop")
    if service == "benchmarking":
        print("Path :", path, " files: ", files)
        totalpoints = streams * POINTSPERPROCESS * len(data)
        processes = []
        print("streams: ", streams, "topic: ", topic, " pointsperprocess: ", POINTSPERPROCESS,
               " length of data: ", len(data))
        try:
            for i in range(0, streams):
                port = port + i
                processes.append(Process(target=send_json_cb, args=(argsinterval, host, port,
                                                                    topic, data, qos, service)))
                processes[i].start()
            for process in processes:
                process.join()
            print("Success: ", totalpoints, " points sent!")
            time.sleep(DATA_PUBLISH_WAIT_PERIOD)
        except Exception as e:
            print("Exception occured while publishing the points", e)
    else:
        if streams == 1:
            while True:
                t_s = time.time()
                for value in data:
                    msg = {'ts': t_s, 'value': value}
                    mqttc.publish(topic, json.dumps(msg), qos=qos)
                    msg.clear()
                    time.sleep(1)
        else:
            for i in range(0, streams):
                PROCS.append(Process(target=send_json_cb, args=(i, host, port,
                                                            topic, data, qos, service)))
                PROCS[i].start()


def on_disconnect(client, userdata, rc):
    """ Callback for MQTT disconnection"""
    print("MQTT disconnected:\nclient: ", client, "\n userdata: ", userdata,
          "\n rc: ", rc)


def on_connect(client, userdata, rc):
    """ Callback for MQTT connection"""
    print("MQTT Connected:\nclient: ", client, "\n userdata: ", userdata,
          "\n rc: ", rc)
MQTTversion = mqtt.MQTTv31
TLS_protocol_version = ssl.PROTOCOL_TLSv1_2
def main():
    """Main method
    """
    args = parse_args()
    if not args.service == "benchmarking":
        args.host = os.getenv('HOST_IP', 'localhost')
    args.port = os.getenv('PORT', '1883')
    args.port = int(args.port)
    updated_topics = {}
    sample_app = os.getenv('SAMPLE_APP')
    if args.topic is not None:
        topic = args.topic
    else:
        if sample_app is None:
            sys.exit("Error: SAMPLE_APP environment variable is not set.")
        topic = sample_app.split("anomaly")[0] + "data"

    if args.csv is not None:
        csv_file_path = args.csv
    else:
        csv_file_path = "/" + sample_app + ".csv"
    client = None
    if int(args.streams) == 1:
        client = mqtt.Client(client_id = '', clean_session = True, userdata = None,
                             protocol = MQTTversion, transport="tcp" )
        secure_mode = os.getenv('SECURE_MODE', 'false')
        if secure_mode.lower() == "true":
            context = ssl.SSLContext(protocol = TLS_protocol_version)
            context.load_verify_locations(cafile="/run/secrets/ca_certificate.pem")
            client.tls_set_context(context)
            client.tls_insecure_set(True)
        client.connect(args.host, args.port, 60)
        client.loop_start()

    try:
        if args.json is not None:
            publish_json(client,
                         args.topic,
                         args.json,
                         args.qos,
                         args.interval,
                         args.streams,
                         args.host,
                         args.port,
                         args.service)
        elif csv_file_path is not None:
            stream_csv(client,
                       topic,
                       args.subsample,
                       args.sampling_rate,
                       csv_file_path)

        else:
            if not updated_topics:
                sys.exit("Arguments are missing")

    except KeyboardInterrupt:
        print('-- Quitting')
        if args.streams == 1:
            client.loop_stop()
        else:
            for i in range(0, args.streams):
                PROCS[i].close()
                client[i].loop_stop()

def is_port_accessible():
    """
    Check if a port is accessible on a given host.

    :param host: The hostname or IP address to check.
    :param port: The port number to check.
    :param timeout: The timeout in seconds for the connection attempt.
    :return: True if the port is accessible, False otherwise.
    """
    host = os.getenv("TS_MS_SERVER", "ia-time-series-analytics-microservice")
    port = int(os.getenv("TS_MS_PORT", "9092"))
    print(f"Waiting for {host} accessible...")
    while True:
        try:
            # Create a socket object
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Set the timeout for the connection attempt
                sock.settimeout(5)
                # Attempt to connect to the host and port
                sock.connect((host, port))
            print(f"{host} is accessible...")
            return True
        except (socket.timeout, socket.error):
            pass
        time.sleep(1)

if __name__ == '__main__':
    is_port_accessible()
    time.sleep(5)  # Wait for 5 seconds before starting the server to avoid the sync issue
    main()
