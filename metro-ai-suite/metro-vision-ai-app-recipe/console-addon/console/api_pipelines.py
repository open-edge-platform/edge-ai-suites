#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Pipeline lifecycle: start and stop."""

import time
import uuid
from collections import deque

import requests
from flask import jsonify, request

from config import (DETECTIONS_TOPIC_PREFIX, LOCK, MQTT_HOST,
                    MQTT_PORT, PIPELINE_SERVER_URL, SESSIONS, _parse_zone, app,
                    analytics_zones_json, attachroi_rect)
from catalog import (_extract_instance_id, _model_instance_id,
                     _resolve_source_uri, _select_pipeline, discover_models)


def _launch(source_id, model_id, device, zone, rtsp=None):
    """Start one pipeline instance. Raises ValueError with a user-facing
    message on any input/DLSPS error; returns the new session dict on success.

    `zone` is None until the operator customises it, in which case the
    pipeline keeps evaluating the deployment's own zones from
    loitering_analytics_config.json unmodified; a provided zone entirely
    replaces them (see `analytics_zones_json`).
    """
    source_uri = _resolve_source_uri(source_id, rtsp)
    if not source_uri:
        raise ValueError("unknown source")

    catalogue = discover_models()
    model_entry = next((m for m in catalogue["models"] if m["id"] == model_id), None)
    if model_entry is None:
        raise ValueError("unknown model")

    pipeline = _select_pipeline(device)
    if pipeline is None:
        raise ValueError(f"no pipeline available for device {device}")

    peer_id = f"console-{uuid.uuid4().hex[:12]}"
    topic = f"{DETECTIONS_TOPIC_PREFIX}_{peer_id}"
    detection_props = {
        "model": model_entry["model"],
        "device": device,
        "model-instance-id": _model_instance_id(model_entry["model"], device),
    }
    if model_entry.get("model_proc"):
        detection_props["model_proc"] = model_entry["model_proc"]

    zone = zone or None
    analytics_props = {"zones": analytics_zones_json(zone)}
    # Physically restricts gvadetect to this rectangle - the reliable way
    # to keep an object from ever being detected, let alone drawn, outside
    # the zone (see config.attachroi_rect for why per-object suppression
    # after the fact does not work in this DLStreamer version). No zone
    # anywhere (file or custom) is the one case nothing should be cropped.
    attachroi_props = {"roi": attachroi_rect(zone) or "0,0,100000,100000"}

    payload = {
        "source": {"uri": source_uri, "type": "uri"},
        "destination": {
            "metadata": {"type": "mqtt", "host": MQTT_HOST, "port": MQTT_PORT, "topic": topic},
            "frame": {"type": "webrtc", "peer-id": peer_id},
        },
        "parameters": {"detection-properties": detection_props,
                       "analytics-properties": analytics_props,
                       "attachroi-properties": attachroi_props},
    }

    url = f"{PIPELINE_SERVER_URL}/pipelines/{pipeline.get('name')}/{pipeline.get('version')}"
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    instance_id = _extract_instance_id(r)

    now = time.time()
    session = {
        "instance_id": instance_id,
        "topic": topic,
        "source": source_id,
        "rtsp": rtsp,
        "model": model_id,
        "device": device,
        "zone": zone,
        "tracks": {},
        "msg_times": deque(maxlen=120),
        "time_key": None,
        "last_frame_ts": None,
        "frame_time_source": "wallclock",
        "state": "RUNNING",
        "detection_state": "no-data",
        "last_activity": now,
        "created": now,
    }
    with LOCK:
        SESSIONS[peer_id] = session

    return {
        "peer_id": peer_id,
        "instance_id": instance_id,
        "whep_url": f"whep/{peer_id}",
        "topic": topic,
        "model": model_id,
        "device": device,
        "zone": zone,
        "compatibility": model_entry.get("compatibility"),
        "compatibility_detail": model_entry.get("compatibility_detail"),
    }


def _stop(peer_id):
    with LOCK:
        sess = SESSIONS.pop(peer_id, None)
    if sess is None:
        return None
    try:
        requests.delete(f"{PIPELINE_SERVER_URL}/pipelines/{sess['instance_id']}", timeout=10)
    except requests.RequestException:
        pass  # the instance may already be gone; nothing further to do
    return sess


@app.route("/api/pipelines/start", methods=["POST"])
def api_pipelines_start():
    body = request.get_json(force=True, silent=True) or {}
    if not body.get("source") and not body.get("rtsp"):
        return jsonify({"error": "source or rtsp is required"}), 400
    if not body.get("model"):
        return jsonify({"error": "model is required"}), 400
    device = str(body.get("device") or "CPU").upper()
    if device not in ("CPU", "GPU", "NPU"):
        return jsonify({"error": "device must be one of CPU, GPU, NPU"}), 400
    zone = _parse_zone(body.get("zone"))
    try:
        result = _launch(body.get("source"), body.get("model"), device, zone, body.get("rtsp"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except requests.RequestException as exc:
        return jsonify({"error": f"pipeline start failed: {exc}"}), 502
    return jsonify(result)


@app.route("/api/pipelines/stop", methods=["POST"])
def api_pipelines_stop():
    body = request.get_json(force=True, silent=True) or {}
    peer_id = body.get("peer_id")
    sess = _stop(peer_id)
    if sess is None:
        return jsonify({"error": "unknown peer_id"}), 404
    return jsonify({"stopped": peer_id})
