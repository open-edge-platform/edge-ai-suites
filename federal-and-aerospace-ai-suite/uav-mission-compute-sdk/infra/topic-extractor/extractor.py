# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Topic Extractor — reads uav telemetry from MQTT and writes to InfluxDB.

MQTT topics consumed:
  uav/<UAV_ID>/telemetry/#  — sub-topics published by companion-bridge:
    .../telemetry/position  — lat, lon, alt_m, rel_alt_m
    .../telemetry/attitude  — roll, pitch, yaw
    .../telemetry/velocity  — north_m_s, east_m_s, down_m_s
    .../telemetry/battery   — voltage_v, remaining_pct
    .../telemetry/gps       — satellites, fix_type
    .../telemetry/status    — armed, flight_mode, connected

InfluxDB measurements written:
  flight_position   : lat, lon, alt_m, rel_alt_m
  flight_attitude   : roll, pitch, yaw
  flight_velocity   : north_m_s, east_m_s, down_m_s
  flight_battery    : voltage_v, remaining_pct
  flight_gps        : satellites, fix_type
  flight_status     : armed (bool), flight_mode (string tag)

All measurements tagged with: uav_id, host
"""

import json
import logging
import os
import socket
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

WRITE_PRECISION = "ns"

# ── Config ────────────────────────────────────────────────────────────────────
MQTT_HOST     = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT     = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID        = os.environ["UAV_ID"]
INFLUX_URL    = os.environ["INFLUXDB_URL"]
INFLUX_TOKEN  = os.environ["INFLUXDB_TOKEN"]
INFLUX_ORG    = os.environ["INFLUXDB_ORG"]
INFLUX_BUCKET = os.environ["INFLUXDB_BUCKET"]
LOG_LEVEL     = os.getenv("LOG_LEVEL", "INFO")

TELEMETRY_TOPIC = f"uav/{UAV_ID}/telemetry/#"
TELEMETRY_PREFIX = f"uav/{UAV_ID}/telemetry/"
HOST_TAG        = socket.gethostname()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] topic-extractor: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── InfluxDB client ───────────────────────────────────────────────────────────
influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx.write_api(write_options=SYNCHRONOUS)

_msg_count = 0


def _write(points: list):
    try:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
    except Exception as exc:
        log.warning("InfluxDB write error: %s", exc)


def _tags(p: Point) -> Point:
    return p.tag("uav_id", UAV_ID).tag("host", HOST_TAG)


def on_message(client, userdata, msg):
    global _msg_count
    try:
        payload = json.loads(msg.payload)
    except Exception:
        return

    # Extract sub-topic suffix: uav/<id>/telemetry/<suffix>
    suffix = msg.topic[len(TELEMETRY_PREFIX):]
    ts = int(time.time() * 1e9)
    points = []

    if suffix == "position":
        points.append(
            _tags(Point("flight_position").time(ts, WRITE_PRECISION))
            .field("lat", payload["latitude_deg"])
            .field("lon", payload["longitude_deg"])
            .field("alt_m", payload["absolute_altitude_m"])
            .field("rel_alt_m", payload["relative_altitude_m"])
        )

    elif suffix == "attitude":
        points.append(
            _tags(Point("flight_attitude").time(ts, WRITE_PRECISION))
            .field("roll", payload["roll_deg"])
            .field("pitch", payload["pitch_deg"])
            .field("yaw", payload["yaw_deg"])
        )

    elif suffix == "velocity":
        points.append(
            _tags(Point("flight_velocity").time(ts, WRITE_PRECISION))
            .field("north_m_s", payload["north_m_s"])
            .field("east_m_s", payload["east_m_s"])
            .field("down_m_s", payload["down_m_s"])
        )

    elif suffix == "battery":
        points.append(
            _tags(Point("flight_battery").time(ts, WRITE_PRECISION))
            .field("voltage_v", payload["voltage_v"])
            .field("remaining_pct", payload["remaining_percent"])
        )

    elif suffix == "gps":
        fix = str(payload.get("fix_type", ""))
        points.append(
            _tags(Point("flight_gps").time(ts, WRITE_PRECISION))
            .field("satellites", payload["num_satellites"])
            .tag("fix_type", fix)
            .field("fix_numeric", 3 if "3D" in fix else 0)
        )

    elif suffix == "status":
        points.append(
            _tags(Point("flight_status").time(ts, WRITE_PRECISION))
            .tag("flight_mode", str(payload.get("mode", "UNKNOWN")))
            .field("armed", 1 if payload.get("armed") else 0)
            .field("connected", 1 if payload.get("connected") else 0)
        )

    if points:
        _write(points)

    _msg_count += 1
    if _msg_count == 1:
        log.info("First telemetry written to InfluxDB (topic=%s)", suffix)
    elif _msg_count % 60 == 0:
        log.info("Written %d telemetry messages to InfluxDB", _msg_count)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("MQTT connected to %s:%d", MQTT_HOST, MQTT_PORT)
        client.subscribe(TELEMETRY_TOPIC, qos=0)
        log.info("Subscribed to %s", TELEMETRY_TOPIC)
    else:
        log.error("MQTT connection failed rc=%d", rc)


def main():
    log.info("=" * 55)
    log.info("TOPIC EXTRACTOR")
    log.info("=" * 55)
    log.info("MQTT:    %s:%d → %s", MQTT_HOST, MQTT_PORT, TELEMETRY_TOPIC)
    log.info("InfluxDB: %s  bucket=%s", INFLUX_URL, INFLUX_BUCKET)

    # Wait for InfluxDB to be ready
    for attempt in range(30):
        try:
            health = influx.health()
            if health.status == "pass":
                log.info("InfluxDB healthy")
                break
        except Exception as exc:
            log.info("Waiting for InfluxDB... (%d/30) %s", attempt + 1, exc)
            time.sleep(2)

    client = mqtt.Client(client_id="topic-extractor", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
