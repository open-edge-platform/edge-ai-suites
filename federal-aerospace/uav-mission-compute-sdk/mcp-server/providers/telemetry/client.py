# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""UAV telemetry client — subscribes to MQTT telemetry topics and caches state."""

import json
import os
import threading
from typing import Any

import paho.mqtt.client as mqtt

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1884"))
UAV_ID = os.getenv("UAV_ID", "uav-1")


class TelemetryClient:
    """MQTT-based telemetry client. Subscribes to uav telemetry topics."""

    def __init__(self):
        self._telemetry: dict[str, Any] = {"connected": False}
        self._lock = threading.Lock()

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"mcp-server-{UAV_ID}",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
        self._client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe(f"uav/{UAV_ID}/telemetry/#", qos=0)

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) < 4 or parts[2] != "telemetry":
            return

        topic_type = parts[3]

        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            return

        with self._lock:
            if topic_type == "position":
                self._telemetry["position"] = payload
            elif topic_type == "attitude":
                self._telemetry["attitude_deg"] = payload
            elif topic_type == "battery":
                self._telemetry["battery"] = payload
            elif topic_type == "velocity":
                self._telemetry["velocity_ned_m_s"] = payload
            elif topic_type == "gps":
                self._telemetry["gps"] = payload
            elif topic_type == "status":
                self._telemetry["connected"] = payload.get("connected", False)
                self._telemetry["armed"] = payload.get("armed", False)
                self._telemetry["mode"] = payload.get("mode", "UNKNOWN")
                self._telemetry["stale"] = payload.get("stale", False)
                self._telemetry["flight_time_s"] = payload.get("flight_time_s", 0.0)
                self._telemetry["timestamp"] = payload.get("timestamp")

    def get_telemetry(self) -> dict[str, Any]:
        """Get current telemetry snapshot from MQTT cache."""
        with self._lock:
            return dict(self._telemetry)


# Singleton client instance
client = TelemetryClient()
