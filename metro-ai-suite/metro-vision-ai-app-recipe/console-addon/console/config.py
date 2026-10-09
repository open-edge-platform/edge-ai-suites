#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Environment, shared state and the Flask application object.

Owned here rather than in app.py so that modules never import the entry
point. Running `python app.py` makes that module `__main__`; a
`from app import ...` would then load a second, independent copy of the
session table.
"""

import json
import logging
import os
import re
import threading

from flask import Flask

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("loitering-detection")

PIPELINE_SERVER_URL = os.environ.get("PIPELINE_SERVER_URL", "http://dlstreamer-pipeline-server:8080")
MQTT_HOST = os.environ.get("MQTT_HOST", "broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090/prometheus")
MEDIAMTX_URL = os.environ.get("MEDIAMTX_URL", "http://mediamtx-server:8889")
MODEL_ROOT = os.environ.get("MODEL_ROOT", "/home/pipeline-server/models")
DETECTIONS_TOPIC_PREFIX = os.environ.get("DETECTIONS_TOPIC_PREFIX", "object_tracking")
LOITER_THRESHOLD_S = float(os.environ.get("LOITER_THRESHOLD_S", "5.0"))
ZONE_VACANT_GRACE_S = float(os.environ.get("ZONE_VACANT_GRACE_S", "3.0"))
TRACK_TTL_S = float(os.environ.get("TRACK_TTL_S", "30.0"))
# Rows not refreshed within this window are withheld from the loiter table.
# Mirrors stale_track_timeout_s in the application's Node-RED flow so the
# console and the application dashboard agree on what counts as stale.
TABLE_STALE_S = float(os.environ.get("TABLE_STALE_S", "10.0"))
# Flat, dashboard-ready republication of the loiter table (see ingest.py).
TABLE_TOPIC = os.environ.get("TABLE_TOPIC", "loitering_table")
TABLE_PUBLISH_INTERVAL_S = float(os.environ.get("TABLE_PUBLISH_INTERVAL_S", "1.0"))
UI_PORT = int(os.environ.get("UI_PORT", "9443"))
TLS_CERT = os.environ.get("TLS_CERT", "/app/certs/console.crt")
TLS_KEY = os.environ.get("TLS_KEY", "/app/certs/console.key")


def _probe_devices():
    # Fallback only: this container does not have the accelerator device
    # nodes mapped, so this reports GPU/NPU absent on every host. DEVICES,
    # supplied by the deployment at deploy time, is the source of truth.
    found = ["CPU"]
    if os.path.exists("/dev/dri"):
        found.append("GPU")
    if os.path.exists("/dev/accel"):
        found.append("NPU")
    return found


_devices_env = os.environ.get("DEVICES", "").strip()
DEVICES = [d.strip().upper() for d in _devices_env.split(",") if d.strip()] if _devices_env else _probe_devices()


def _parse_zone(raw):
    """Parse a zone specification into a normalised zone object.

    Two notations are accepted, both in source-image pixels:

      rectangle  "x,y,w,h"                       -> 4 integers
      polygon    "(x1,y1) (x2,y2) (x3,y3) ..."   -> >= 3 vertex pairs

    Parentheses, semicolons and whitespace are optional separators, so
    "120,100 1,312 23,23 43,43" and "(120,100) (1,312) (23,23) (43,43)"
    are equivalent. A polygon is retained verbatim under "points" and is
    also reduced to its axis-aligned bounding box so that every consumer
    that expects x/y/w/h keeps working unchanged.
    """
    if not raw:
        return None
    if isinstance(raw, dict):
        pts = raw.get("points")
        if pts:
            return _zone_from_points([(float(p[0]), float(p[1])) for p in pts])
        try:
            x, y, w, h = int(raw["x"]), int(raw["y"]), int(raw["w"]), int(raw["h"])
        except (KeyError, TypeError, ValueError):
            return None
        return None if w <= 0 or h <= 0 else {"x": x, "y": y, "w": w, "h": h, "points": None}
    if isinstance(raw, (list, tuple)):
        nums = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                nums.extend([item[0], item[1]])
            else:
                nums.append(item)
        raw = ",".join(str(n) for n in nums)
    try:
        nums = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?", str(raw))]
    except (TypeError, ValueError):
        return None
    if len(nums) == 4:
        x, y, w, h = (int(round(n)) for n in nums)
        if w <= 0 or h <= 0:
            return None
        return {"x": x, "y": y, "w": w, "h": h, "points": None}
    if len(nums) >= 6 and len(nums) % 2 == 0:
        return _zone_from_points([(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)])
    return None


def _zone_from_points(points):
    """Reduce a vertex list to a zone object carrying both polygon and bbox."""
    if len(points) < 3:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x, y = int(round(min(xs))), int(round(min(ys)))
    w, h = int(round(max(xs) - min(xs))), int(round(max(ys) - min(ys)))
    if w <= 0 or h <= 0:
        return None
    return {"x": x, "y": y, "w": w, "h": h,
            "points": [[int(round(px)), int(round(py))] for px, py in points]}


# The single zone id every session uses. gvaanalytics will not cleanly replace
# a same-id zone loaded from a config= file, so the pipelines bake none and
# every start supplies exactly one under this id.
ZONE_ID = "OperatorZone"


def zone_to_analytics_json(zone, object_retention=None):
    """Render a zone as gvaanalytics' inline `zones` value.

    A rectangle is sent as its 4-corner polygon; "polygon" is the only
    documented zone type.
    """
    if not zone:
        return None
    if zone.get("points"):
        points = [{"x": int(round(p[0])), "y": int(round(p[1]))} for p in zone["points"]]
    else:
        x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]
        points = [{"x": x, "y": y}, {"x": x + w, "y": y},
                  {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]
    retention = ZONE_VACANT_GRACE_S if object_retention is None else object_retention
    zones = [{
        "id": ZONE_ID,
        "type": "polygon",
        "points": points,
        "track-dwell-time": True,
        "object-retention": retention,
        "thickness": 3,
    }]
    return json.dumps(zones)


def _zone_from_config_file(path):
    """Default zone from the deployment's own zone file, shared with the CLI.

    Its zone is kept rectangular so the rail's x/y/w/h fields represent it
    exactly; a polygon would be silently replaced by its bounding box on edit.
    This is only ever used to pre-fill the rail - see `_load_file_zones`
    below for what the pipeline itself is actually given.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            zones = json.load(fh).get("zones") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    for zone in zones:
        points = zone.get("points") or []
        if len(points) >= 3:
            return _zone_from_points([(p["x"], p["y"]) for p in points])
    return None


def _load_file_zones(path):
    """The deployment's own zones (e.g. Pathway/Driveway), verbatim.

    Pipelines no longer bake `gvaanalytics config=...`: every start now sets
    the `zones` property itself, either with this file's zones (nothing
    customised yet) or with the operator's own rectangle in place of them
    (see `analytics_zones_json`) - gvaanalytics has no notion of "add to the
    file's zones", so the two are mutually exclusive by construction.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            zones = json.load(fh).get("zones") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    return zones if isinstance(zones, list) else []


ZONE_CONFIG_FILE = os.environ.get("ZONE_CONFIG_FILE", "/home/pipeline-server/configs/loitering_analytics_config.json")


def _file_zones_json():
    # Read fresh on every call, not cached at import time - editing the
    # zone file should take effect on the next pipeline start without
    # needing to restart this service, same as sample_start.sh's CLI path.
    zones = _load_file_zones(ZONE_CONFIG_FILE)
    return json.dumps(zones) if zones else "[]"


def default_zone():
    # Same freshness reasoning as _file_zones_json() - re-derived from the
    # zone file on every call rather than snapshotted once at import time.
    return (_parse_zone(os.environ.get("DEFAULT_ZONE"))
            or _zone_from_config_file(ZONE_CONFIG_FILE)
            or {"x": 0, "y": 200, "w": 300, "h": 400, "points": None})


def analytics_zones_json(zone):
    """What to set gvaanalytics' `zones` property to for this session.

    `zone` is None until the operator customises it (the rail is only
    pre-filled with the file's own bounding box for convenience - starting
    without touching it keeps the file's zones, unmodified, as-is). Once a
    zone is supplied - by editing the rail, drawing on video, or applying -
    it entirely replaces the file's zones rather than being added alongside
    them, matching the "it is now a new config" mental model: a deployment
    is either watching its own pre-configured zones or an operator's own
    rectangle, never a mix of both.
    """
    return zone_to_analytics_json(zone) if zone else _file_zones_json()


try:
    SOURCES = json.loads(os.environ.get("SOURCES_JSON", "[]"))
    if not isinstance(SOURCES, list):
        SOURCES = []
except (json.JSONDecodeError, TypeError):
    SOURCES = []

LOCK = threading.RLock()
SESSIONS = {}
MQTT_STATE = {"connected": False}
MODEL_CACHE = {"ts": 0.0, "data": None}
MODEL_CACHE_TTL_S = 30.0

app = Flask(__name__)
