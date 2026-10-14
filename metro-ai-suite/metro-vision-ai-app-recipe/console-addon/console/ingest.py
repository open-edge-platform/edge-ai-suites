#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""MQTT ingestion and reconciliation of sessions against pipeline state."""

import json
import threading
import time
import uuid

import requests

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - the image always installs this
    mqtt = None

from config import (DETECTIONS_TOPIC_PREFIX, LOCK, LOG, MQTT_HOST, MQTT_PORT,
                    MQTT_STATE, PIPELINE_SERVER_URL, SESSIONS)
from analytics import _resolve_frame_time, _update_zone_analytics


def _reconcile_sessions():
    """Drop any session whose instance is no longer RUNNING or QUEUED.

    A pipeline that reaches the end of its media, or aborts, stops
    publishing; without this the panel displays a frozen reading that is
    indistinguishable from a live stream of an idle scene.
    """
    try:
        r = requests.get(f"{PIPELINE_SERVER_URL}/pipelines/status", timeout=5)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return  # keep sessions untouched when the server is unreachable

    items = data if isinstance(data, list) else data.get("pipelines", []) if isinstance(data, dict) else []
    running_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        state = str(item.get("state", "")).upper()
        iid = item.get("id") or item.get("instance_id")
        if state in ("RUNNING", "QUEUED") and iid is not None:
            running_ids.add(iid)

    with LOCK:
        for peer_id in list(SESSIONS.keys()):
            sess = SESSIONS[peer_id]
            if sess["instance_id"] in running_ids:
                sess["state"] = "RUNNING"
            else:
                del SESSIONS[peer_id]

def _on_mqtt_connect(client, _userdata, _flags, rc, *_args):
    MQTT_STATE["connected"] = (rc == 0)
    # The published topic contains no path separator, so a hierarchical
    # wildcard ("<prefix>_#") does not match it. Subscribe to everything and
    # filter by prefix in the callback instead.
    client.subscribe("#")


def _on_mqtt_disconnect(_client, _userdata, *_args):
    MQTT_STATE["connected"] = False


def _on_mqtt_message(_client, _userdata, msg):
    try:
        topic = msg.topic
        if not topic.startswith(DETECTIONS_TOPIC_PREFIX):
            return
        payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        # Read the object list from metadata.objects when present and from
        # a top-level "objects" otherwise; an implementation reading only
        # the top level receives nothing in the deployment's operating mode.
        if isinstance(metadata.get("objects"), list):
            objects = metadata["objects"]
        elif isinstance(payload.get("objects"), list):
            objects = payload["objects"]
        else:
            objects = []
        now = time.time()
        with LOCK:
            sess = next((s for s in SESSIONS.values() if s["topic"] == topic), None)
            if sess is None:
                sess = next(
                    (s for s in SESSIONS.values()
                     if topic.startswith(s["topic"] + "_") or topic.startswith(s["topic"] + "/")),
                    None,
                )
        if sess is None:
            return
        frame_ts = _resolve_frame_time(sess, payload, metadata, now)
        with LOCK:
            _update_zone_analytics(sess, objects, metadata, frame_ts, now)
    except Exception:  # noqa: BLE001 - never let a bad message kill the loop
        LOG.exception("failed to process a detection message")


mqtt_client = None
if mqtt is not None:
    mqtt_client = mqtt.Client(client_id=f"loitering-console-{uuid.uuid4().hex[:8]}")
    mqtt_client.on_connect = _on_mqtt_connect
    mqtt_client.on_disconnect = _on_mqtt_disconnect
    mqtt_client.on_message = _on_mqtt_message


def _mqtt_loop():
    backoff = 1.0
    while True:
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
            backoff = 1.0
            mqtt_client.loop_forever()
        except Exception:  # noqa: BLE001 - reconnect with backoff
            MQTT_STATE["connected"] = False
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


if mqtt_client is not None:
    threading.Thread(target=_mqtt_loop, name="mqtt-loop", daemon=True).start()
