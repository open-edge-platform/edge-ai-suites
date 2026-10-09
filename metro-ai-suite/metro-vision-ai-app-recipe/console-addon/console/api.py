#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""HTTP API surface."""

import time

import requests
from flask import jsonify, render_template, request

from config import (DETECTIONS_TOPIC_PREFIX, DEVICES, LOCK,
                    LOG, LOITER_THRESHOLD_S, MQTT_STATE, PIPELINE_SERVER_URL,
                    PROMETHEUS_URL, SESSIONS, SOURCES, _parse_zone, app, default_zone)
from snapshot import _stream_snapshot
from catalog import discover_models
from api_pipelines import _launch, _stop
from ingest import _reconcile_sessions
from metrics import collect_metrics


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    return jsonify({
        "sources": SOURCES,
        "devices": [{"id": d, "available": d in DEVICES} for d in ("CPU", "GPU", "NPU")],
        "default_zone": default_zone(),
        "loiter_threshold_s": LOITER_THRESHOLD_S,
        "topic_prefix": DETECTIONS_TOPIC_PREFIX,
    })


@app.route("/api/models")
def api_models():
    force = request.args.get("refresh") == "1"
    return jsonify(discover_models(force=force))


@app.route("/api/pipelines")
def api_pipelines():
    try:
        r = requests.get(f"{PIPELINE_SERVER_URL}/pipelines/status", timeout=5)
        r.raise_for_status()
        return jsonify(r.json())
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": str(exc), "pipelines": []})


@app.route("/api/zone", methods=["POST"])
def api_zone():
    """Apply a new evaluation zone by relaunching the affected session(s).

    gvaanalytics has no live-update path for its zones: a zone already in
    effect (from `analytics_zones_json` at the prior start) is not cleanly
    replaced by a later property set with the same id (confirmed live — the
    original geometry kept winning). The only way a new zone reliably takes
    effect is a fresh start, so this stops each affected session's instance
    and starts a new one with the same source/model/device and the new zone.
    A zone applied here entirely replaces whatever the session was
    evaluating before - the deployment's own file zones included - rather
    than being added alongside them; see `analytics_zones_json`. Without
    "peer_id" the zone is applied to every live stream, so a zone drawn
    while comparing models applies to all panels at once.
    """
    body = request.get_json(silent=True) or {}
    zone = _parse_zone(body.get("zone"))
    if zone is None:
        return jsonify({"error": "zone must be 'x,y,w,h' or at least three '(x,y)' vertices"}), 400
    peer_id = body.get("peer_id")
    with LOCK:
        targets = [peer_id] if peer_id else list(SESSIONS.keys())
        targets = [pid for pid in targets if pid in SESSIONS]
    if peer_id and not targets:
        return jsonify({"error": "unknown peer_id"}), 404

    relaunched = []
    for pid in targets:
        with LOCK:
            old = SESSIONS.get(pid)
        if old is None:
            continue
        _stop(pid)
        try:
            new_session = _launch(old["source"], old["model"], old["device"], zone, old.get("rtsp"))
        except (ValueError, requests.RequestException) as exc:
            LOG.error("zone reapply failed for %s: %s", pid, exc)
            continue
        relaunched.append({"old_peer_id": pid, **new_session})

    return jsonify({"zone": zone, "updated": relaunched, "count": len(relaunched)})


@app.route("/api/events")
def api_events():
    _reconcile_sessions()
    now = time.time()
    with LOCK:
        streams = [_stream_snapshot(peer_id, sess, now) for peer_id, sess in SESSIONS.items()]
    return jsonify({"streams": streams})


@app.route("/api/metrics")
def api_metrics():
    try:
        return jsonify(collect_metrics())
    except Exception:  # noqa: BLE001 - degrade rather than fail
        LOG.exception("metrics collection failed")
        return jsonify({
            "cpu": {"percent": None, "freq_mhz": None},
            "gpu": {"percent": None, "engines": {}, "mem_used_bytes": None, "mem_total_bytes": None,
                    "freq_mhz": None, "power_w": None},
            "npu": {"percent": None, "mem_used_bytes": None, "power_w": None},
            "mem": {"percent": None, "used_bytes": None, "total_bytes": None},
        })


@app.route("/api/health")
def api_health():
    pipeline_reachable = False
    try:
        r = requests.get(f"{PIPELINE_SERVER_URL}/pipelines/status", timeout=3)
        pipeline_reachable = r.ok
    except requests.RequestException:
        pass
    prometheus_reachable = False
    try:
        r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": "up"}, timeout=3)
        prometheus_reachable = r.ok
    except requests.RequestException:
        pass
    return jsonify({
        "ok": True,
        "mqtt_connected": MQTT_STATE["connected"],
        "pipeline_server_reachable": pipeline_reachable,
        "prometheus_reachable": prometheus_reachable,
    })


# --------------------------------------------------------------------------
# 8. WHEP proxy (BACKEND-SPEC.md §4)
# --------------------------------------------------------------------------

_WHEP_METHODS = ["OPTIONS", "GET", "POST", "PATCH", "DELETE"]
