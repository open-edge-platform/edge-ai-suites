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
                    MQTT_STATE, PIPELINE_SERVER_URL, SESSIONS, TABLE_TOPIC,
                    TABLE_PUBLISH_INTERVAL_S)
from analytics import _resolve_frame_time, _update_zone_analytics

_last_table_publish = {}
# (camera, object_id) -> wall clock of first sighting. Deriving entry time from
# now-minus-dwell on every publish makes it creep as both values advance.
_entry_times = {}


def _publish_table_rows(topic, objects, now):
    """Republish gvaanalytics dwell data as flat, one-row-per-object messages.

    A dashboard cannot turn frame-rate nested metadata into a per-object table
    without the stateful aggregation the removed Node-RED flow provided. This
    restores it for every stream, console-started or not.
    """
    if now - _last_table_publish.get(topic, 0.0) < TABLE_PUBLISH_INTERVAL_S:
        return
    _last_table_publish[topic] = now
    if mqtt_client is None:
        return
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        for dwell in obj.get("dwell_times") or []:
            if not isinstance(dwell, dict):
                continue
            dwell_s = round(float(dwell.get("dwell_time_sec") or 0.0), 2)
            key = (topic, obj.get("id"))
            # Recorded once, on first sight, then reused for the whole track.
            entry_wall = _entry_times.get(key)
            if entry_wall is None:
                entry_wall = now - dwell_s
                _entry_times[key] = entry_wall
            row = {
                "camera": topic,
                "object_id": obj.get("id"),
                "type": obj.get("roi_type") or "object",
                "entry_time": time.strftime("%H:%M:%S", time.localtime(entry_wall)),
                "dwell_s": dwell_s,
            }
            try:
                mqtt_client.publish(TABLE_TOPIC, json.dumps(row))
            except (ValueError, TypeError, RuntimeError):
                LOG.exception("could not publish a loiter table row")

    # Bound the cache: drop entries for tracks that stopped reporting.
    if len(_entry_times) > 2000:
        cutoff = now - 3600
        for k, v in list(_entry_times.items()):
            if v < cutoff:
                del _entry_times[k]


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


# --------------------------------------------------------------------------
# 5. Utilisation (BACKEND-SPEC.md §7)
# --------------------------------------------------------------------------

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
        # Published for every stream, including CLI-started ones the console
        # holds no session for.
        _publish_table_rows(topic, objects, now)
        with LOCK:
            sess = next((s for s in SESSIONS.values() if s["topic"] == topic), None)
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


# --------------------------------------------------------------------------
# 7. Routes
# --------------------------------------------------------------------------
