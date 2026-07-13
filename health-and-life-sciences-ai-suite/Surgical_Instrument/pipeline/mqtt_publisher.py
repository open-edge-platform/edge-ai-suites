"""gvapython callback for publishing detection metadata to MQTT.

Called for every frame by the DL Streamer pipeline. Extracts the JSON metadata
that gvametaconvert already attached, then publishes it to the configured
broker via paho-mqtt.

Why not gvametapublish method=mqtt?
    The DLS 2026.1 image's gvametapublish MQTT plugin never opens a TCP
    connection to the broker (`Connect failed, rc -1` at start, no traffic
    reaches the broker even with tcp:// scheme + reachable IP). paho-python
    from the same container works fine, so we go through gvapython instead.
"""
from __future__ import annotations

import json
import logging
import os
import threading

import paho.mqtt.client as mqtt

log = logging.getLogger("mqtt_publisher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class MQTTPublisher:
    """gvapython callback class. Instantiated once at pipeline start."""

    def __init__(self, host: str | None = None, port: int = 1883,
                 topic: str = "surgical/detections",
                 client_id: str = "surgical-pipeline") -> None:
        self._host = host or os.environ.get("MQTT_HOST", "surgical-mqtt")
        self._port = int(os.environ.get("MQTT_PORT", str(port)))
        self._topic = os.environ.get("MQTT_TOPIC", topic)
        self._client = mqtt.Client(client_id=client_id)
        self._connected = threading.Event()
        self._client.on_connect = self._on_connect
        self._client.connect_async(self._host, self._port, keepalive=30)
        self._client.loop_start()
        log.info("MQTTPublisher: connecting to %s:%d topic=%s",
                 self._host, self._port, self._topic)

    def _on_connect(self, _c, _u, _f, rc):
        if rc == 0:
            self._connected.set()
            log.info("MQTTPublisher: connected")
        else:
            log.error("MQTTPublisher: connect failed rc=%s", rc)

    def process_frame(self, frame) -> bool:
        """gvapython invokes this per buffer. Return True to keep the buffer."""
        try:
            messages = list(frame.messages())
        except Exception as exc:  # noqa: BLE001
            log.debug("frame.messages() failed: %s", exc)
            return True
        for payload in messages:
            try:
                # gvametaconvert format=json emits JSON strings directly.
                self._client.publish(self._topic, payload, qos=0)
            except Exception as exc:  # noqa: BLE001
                log.error("publish failed: %s", exc)
        return True
