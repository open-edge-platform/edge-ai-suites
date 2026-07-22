# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""MQTT subscriber — reacts to "batch-complete" events published by the
detection layer (see detection-service's ``mqtt_publisher.py``).

This is the *only* way the agent-service learns that new detections are
ready to reason over. It never talks to DL Streamer or any other detector
directly, and never subscribes to raw detection data — it only reads
detections back from the storage-service, bounded by the id window carried
in the event, once told a batch is ready.
"""

import json
import logging
import os
import threading

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

_MQTT_HOST        = os.environ.get("MQTT_HOST", "mqtt-broker")
_MQTT_PORT        = int(os.environ.get("MQTT_PORT", "1883"))
_MQTT_BATCH_TOPIC = os.environ.get("MQTT_BATCH_TOPIC", "apm/batch-complete")

# Callback invoked for every batch-complete event: fn(event: dict) -> None.
# Wired up by main.py to `_handle_batch_complete_event`.
_on_batch_complete = None


def set_on_batch_complete(fn):
    global _on_batch_complete
    _on_batch_complete = fn


def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(_MQTT_BATCH_TOPIC)
        log.info("MQTT connected; subscribed to %s", _MQTT_BATCH_TOPIC)
    else:
        log.error("MQTT connection failed with rc=%s", rc)


def _on_message(client, userdata, msg):
    try:
        event = json.loads(msg.payload.decode("utf-8"))
    except Exception as exc:
        log.error("Could not parse batch-complete event: %s", exc)
        return

    if _on_batch_complete is None:
        log.warning("Received batch-complete event but no handler is registered: %s", event)
        return

    try:
        _on_batch_complete(event)
    except Exception as exc:
        log.error("Error handling batch-complete event %s: %s", event.get("run_id"), exc)


def start_subscriber() -> mqtt.Client:
    """Start the MQTT subscriber in a background daemon thread.

    Returns the mqtt.Client so callers can access it if needed.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _on_connect
    client.on_message = _on_message

    client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=60)

    thread = threading.Thread(target=client.loop_forever, daemon=True)
    thread.start()
    log.info("Batch-complete event subscriber started (host=%s port=%d topic=%s)",
              _MQTT_HOST, _MQTT_PORT, _MQTT_BATCH_TOPIC)
    return client
