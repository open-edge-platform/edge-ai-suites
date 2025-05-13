#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from influxdb import InfluxDBClient
import os
import matplotlib.pyplot as plt
import pandas as pd
import urllib3
urllib3.disable_warnings()


mode = os.getenv('SECURE_MODE')
secure_mode = mode.lower() == "true"
host = os.getenv('INFLUX_SERVER')
username = os.getenv('INFLUXDB_USERNAME')
password = os.getenv('INFLUXDB_PASSWORD')
database = os.getenv('INFLUXDB_DB')

if secure_mode:
    print("Secure mode is enabled. Using SSL for InfluxDB connection.")
    client = InfluxDBClient(host=host, port=8086, username=username, password=password, database=database,ssl=True)
else:
    print("Secure mode is not enabled.")
    client = InfluxDBClient(host=host, port=8086, username=username, password=password, database=database)

def query_influxdb():
    query = 'SELECT "wind_speed", "grid_active_power","anomaly_status" FROM "wind_turbine_anomaly_data" WHERE time > now() - 15m '
    result = client.query(query)
    points = list(result.get_points())
    df = pd.DataFrame(points)
    return df


def get_total_processed_pts():
    query = 'SELECT count(wind_speed) FROM "wind_turbine_anomaly_data"'
    result = client.query(query)
    points = list(result.get_points())
    count = 0
    if points:
        count = points[0]['count'] 
    return count

def get_total_ingested_pts():
    query = 'SELECT count(wind_speed) FROM "wind_turbine_data"'
    result = client.query(query)
    points = list(result.get_points())
    count = 0
    if points:
        count = points[0]['count'] 
    return count

def get_total_anomaly_pts():
    query = 'SELECT count(wind_speed) FROM "wind_turbine_anomaly_data" WHERE anomaly_status > 0'
    result = client.query(query)
    points = list(result.get_points())
    count = 0
    if points:
        count = points[0]['count'] 
    return count


def get_anomaly_count_by_status(anomaly_status):
    query = f'SELECT count(wind_speed) FROM "wind_turbine_anomaly_data" WHERE anomaly_status = {anomaly_status}'
    result = client.query(query)
    points = list(result.get_points())
    count = 0
    if points:
        count = points[0]['count']
    return count

def get_live_barplot():
    # Simulate dynamic data
    labels = ["Low", "Medium", "High"]
    anomaly_statuses = [0.3, 0.6, 1.0]
    count_value = [get_anomaly_count_by_status(status) for status in anomaly_statuses]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(labels, count_value, color=["green", "orange", "red"])
    ax.set_title("Live Anomaly Counts")
    ax.set_xlabel("Anomaly Type")
    ax.set_ylabel("Count")
    return fig