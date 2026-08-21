#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Track memory cache for Showcase scene analytics.

Subscribes to:
  scenescape/regulated/scene/<scene_id>          — fused object tracks
  scenescape/data/sensor/badge-001               — badge swipe events
  scenescape/data/sensor/faceid-001              — face-id events
  scenescape/data/sensor/showcase_light          — light sensor events

For each tracked UUID, stores a time-indexed history of its position,
velocity, region membership, camera bounding boxes, and associated sensor
readings.  Sensor events are also kept in a global log for correlation.

Retention window: RETENTION_S seconds (default 600 = 10 minutes).

Importable module
-----------------
  from track_cache import TrackCache, TrackSubscriber

  cache = TrackCache()
  sub   = TrackSubscriber(cache, broker_host=..., ...)
  sub.start()           # non-blocking, background loop_start()
  ...
  snap  = cache.snapshot()   # dict ready for JSON / LLM

Standalone
----------
  python3 track_cache.py [broker options] [--dump]
  # Prints a periodic stats summary and optionally dumps the full snapshot.
"""

import argparse
import json
import logging
import math
import ssl
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from scene_config import SCENE_ID

logger = logging.getLogger(__name__)

# ── Scene / topics ─────────────────────────────────────────────────────────────
REG_TOPIC   = f"scenescape/regulated/scene/{SCENE_ID}"
CAM5_TOPIC  = "scenescape/data/camera/cam-5"   # loop boundary detector
SENSOR_TOPICS = [
  "scenescape/data/sensor/badge-001",
  "scenescape/data/sensor/faceid-001",
  "scenescape/data/sensor/showcase_light",
]

# ── Tunable ────────────────────────────────────────────────────────────────────
RETENTION_S   = 600   # seconds of history to keep per track (10 min ≈ 1 loop)
MAX_ENTRIES   = 6000  # hard cap per track (@ ~10 fps × 600 s)
SENSOR_LOG_N  = 2000  # max global sensor events to keep


# ── Helper ─────────────────────────────────────────────────────────────────────
def _now() -> float:
  return time.time()

def _iso(ts: str) -> float:
  """Parse ISO-8601 timestamp → Unix float."""
  try:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
  except Exception:
    return _now()


def _region_entered(info) -> str:
  """Extract a region's 'entered' timestamp, tolerating dict or list shapes.

  The controller usually sends region info as {"entered": "<iso>"}, but it
  occasionally emits a list of such dicts. A single unexpected list here used
  to crash the whole MQTT ingest thread, silently freezing the dashboard."""
  if isinstance(info, dict):
    return info.get("entered", "")
  if isinstance(info, list):
    for item in info:
      if isinstance(item, dict) and item.get("entered"):
        return item["entered"]
  return ""


# ── Data model ─────────────────────────────────────────────────────────────────
# One point in a track's history.
# Stored as a plain dict to keep things simple and JSON-serializable.
#
#   t            : float  Unix epoch seconds
#   x, y, z      : float  world-space translation (metres)
#   vx, vy, vz   : float  velocity (m/s)
#   confidence   : float
#   regions      : list[str]   region UUIDs the object is currently inside
#   cameras      : list[str]   cameras currently seeing the object
#   cam_bounds   : dict  cam_id → {x,y,width,height} pixel bounding box
#   sensors      : dict  sensor_id → latest value at this frame

def _make_entry(t: float, obj: dict) -> dict:
  tr  = obj.get("translation", [0, 0, 0])
  vel = obj.get("velocity",    [0, 0, 0])
  # Latest sensor value per sensor (most recent reading)
  sensors_snap = {}
  for sid, sdata in obj.get("sensors", {}).items():
    # sdata may be {"values": [[iso, val], ...]} or the bare [[iso, val], ...] list
    if isinstance(sdata, dict):
      vals = sdata.get("values", [])
    elif isinstance(sdata, list):
      vals = sdata
    else:
      vals = []
    if vals:
      sensors_snap[sid] = vals[-1][1]   # [ISO, value] → value

  return {
    "t": t,
    "x": tr[0], "y": tr[1], "z": tr[2],
    "vx": vel[0], "vy": vel[1], "vz": vel[2],
    "regions": list(obj.get("regions", {}).keys()),
    "cameras": obj.get("visibility", []),
    "cam_bounds": obj.get("camera_bounds", {}),
    "sensors": sensors_snap,
  }


# ── TrackCache ─────────────────────────────────────────────────────────────────
class TrackCache:
  """Thread-safe in-memory store for all tracked object histories."""

  def __init__(self, retention_s: float = RETENTION_S):
    self.retention_s  = retention_s
    self._lock        = threading.Lock()
    # UUID → track record
    self._tracks: dict[str, dict] = {}
    # Global ordered log of sensor events (not per-object)
    self._sensor_log: deque = deque(maxlen=SENSOR_LOG_N)
    # Stats
    self._msg_count  = 0
    self._start_time = _now()
    self._loop_count = 0
    # Loop detection state (dark → live edge on cam-5)
    self._cam5_dark  = False

  # ── Ingestion ────────────────────────────────────────────────────────────────

  def ingest_regulated(self, payload: dict):
    """Process one regulated scene message."""
    ts_str = payload.get("timestamp", "")
    t = _iso(ts_str) if ts_str else _now()

    with self._lock:
      self._msg_count += 1
      seen_ids = set()
      for obj in payload.get("objects", []):
        uid = obj.get("id")
        if not uid:
          continue
        seen_ids.add(uid)
        self._upsert(uid, obj, t)
      # Prune old entries (time-based) — do it lazily every 100 messages
      if self._msg_count % 100 == 0:
        self._prune_old(t)

  def ingest_sensor(self, topic: str, payload: dict):
    """Store a raw sensor event in the global log."""
    sensor_id = topic.rstrip("/").split("/")[-1]
    t = _now()
    with self._lock:
      self._sensor_log.append({
        "t": t,
        "sensor": sensor_id,
        "topic": topic,
        "payload": payload,
      })

  def ingest_cam5(self, payload: dict):
    """Detect video loop boundary (dark→live edge) and clear the cache."""
    objects = payload.get("objects", {})
    is_dark = not bool(objects)
    with self._lock:
      if self._cam5_dark and not is_dark:
        # Rising edge: dark frame followed by live frame = new loop
        self._loop_count += 1
        logger.info(f"Video loop #{self._loop_count} detected — clearing cache")
        self._tracks.clear()
        self._sensor_log.clear()
      self._cam5_dark = is_dark

  def clear(self):
    """Discard all track history and sensor events."""
    with self._lock:
      self._tracks.clear()
      self._sensor_log.clear()

  # ── Internal ─────────────────────────────────────────────────────────────────

  def _upsert(self, uid: str, obj: dict, t: float):
    """Insert or update a track entry (call with lock held)."""
    if uid not in self._tracks:
      self._tracks[uid] = {
        "uid": uid,
        "category": obj.get("category", "unknown"),
        "first_seen": _iso(obj["first_seen"]) if obj.get("first_seen") else t,
        "entries": deque(maxlen=MAX_ENTRIES),
        # Region visit log: region_id → first_entered ISO
        "regions_visited": {
          r: _region_entered(info)
          for r, info in obj.get("regions", {}).items()
        },
      }
    track = self._tracks[uid]
    # Accumulate region visit times
    for r, info in obj.get("regions", {}).items():
      if r not in track["regions_visited"]:
        track["regions_visited"][r] = _region_entered(info)
    track["entries"].append(_make_entry(t, obj))
    track["last_t"] = t

  def _prune_old(self, now: float):
    """Remove stale entries from all tracks (call with lock held)."""
    cutoff = now - self.retention_s
    dead = []
    for uid, track in self._tracks.items():
      entries = track["entries"]
      # Trim from the left (oldest)
      while entries and entries[0]["t"] < cutoff:
        entries.popleft()
      if not entries:
        # Track has no recent entries — keep metadata but mark stale
        if now - track.get("last_t", now) > self.retention_s:
          dead.append(uid)
    for uid in dead:
      del self._tracks[uid]

  # ── Query API ────────────────────────────────────────────────────────────────

  def snapshot(self) -> dict:
    """Return a JSON-serializable dict summarising the full cache state.
    Suitable for passing directly to an LLM prompt."""
    now = _now()
    with self._lock:
      tracks_out = []
      for uid, track in self._tracks.items():
        entries = list(track["entries"])
        if not entries:
          continue
        latest = entries[-1]
        first  = entries[0]
        age_s  = now - track["first_seen"]
        duration_s = latest["t"] - first["t"]

        # Speed stats
        speeds = [math.sqrt(e["vx"]**2 + e["vy"]**2) for e in entries]
        avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
        max_speed = max(speeds) if speeds else 0.0

        # Path extent (bounding box of trajectory)
        xs = [e["x"] for e in entries]
        ys = [e["y"] for e in entries]
        extent = {
          "x_min": min(xs), "x_max": max(xs),
          "y_min": min(ys), "y_max": max(ys),
        }

        tracks_out.append({
          "uid": uid,
          "category": track["category"],
          "age_s": round(age_s, 1),
          "duration_s": round(duration_s, 1),
          "sample_count": len(entries),
          "current": {
            "x": round(latest["x"], 3),
            "y": round(latest["y"], 3),
            "vx": round(latest["vx"], 3),
            "vy": round(latest["vy"], 3),
            "speed_m_s": round(math.sqrt(latest["vx"]**2 + latest["vy"]**2), 3),
            "regions": latest["regions"],
            "cameras": latest["cameras"],
            "sensors": latest["sensors"],
          },
          "stats": {
            "avg_speed_m_s": round(avg_speed, 3),
            "max_speed_m_s": round(max_speed, 3),
            "extent": {k: round(v, 2) for k, v in extent.items()},
          },
          "regions_visited": track["regions_visited"],
          # Downsampled path: every 10th entry (max 60 points)
          "path": [
            {"t": round(e["t"], 2), "x": round(e["x"], 2), "y": round(e["y"], 2)}
            for e in entries[::max(1, len(entries)//60)]
          ],
        })

      recent_sensors = [
        {
          "t": round(e["t"], 2),
          "sensor": e["sensor"],
          "payload": e["payload"],
        }
        for e in list(self._sensor_log)[-100:]
      ]

      return {
        "scene_id": SCENE_ID,
        "snapshot_time": now,
        "retention_s": self.retention_s,
        "uptime_s": round(now - self._start_time, 1),
        "msg_count": self._msg_count,
        "track_count": len(tracks_out),
        "tracks": tracks_out,
        "recent_sensor_events": recent_sensors,
      }

  def stats_line(self) -> str:
    """One-line summary for periodic console output."""
    now = _now()
    with self._lock:
      cats: dict[str, int] = {}
      total_entries = 0
      for track in self._tracks.values():
        c = track["category"]
        cats[c] = cats.get(c, 0) + 1
        total_entries += len(track["entries"])
      uptime = round(now - self._start_time)
      cat_str = " ".join(f"{c}={n}" for c, n in sorted(cats.items()))
      return (
        f"uptime={uptime}s  loop={self._loop_count}  "
        f"tracks={len(self._tracks)} [{cat_str}]  "
        f"entries={total_entries}  msgs={self._msg_count}  "
        f"sensor_events={len(self._sensor_log)}"
      )


# ── MQTT subscriber ────────────────────────────────────────────────────────────
class TrackSubscriber:
  """Wraps a paho MQTT client that feeds a TrackCache."""

  def __init__(self, cache: TrackCache, broker_host: str, broker_port: int,
               ca_cert: str | None, tls_insecure: bool, broker_auth: str | None):
    self.cache = cache

    if hasattr(mqtt, "CallbackAPIVersion"):
      self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
      self.client = mqtt.Client()

    if broker_auth and Path(broker_auth).exists():
      with open(broker_auth) as f:
        creds = json.load(f)
      self.client.username_pw_set(creds["user"], creds["password"])
      logger.info(f"Auth as '{creds['user']}'")

    if ca_cert and Path(ca_cert).exists():
      self.client.tls_set(
        ca_certs=ca_cert,
        cert_reqs=ssl.CERT_NONE,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
      )
      self.client.tls_insecure_set(tls_insecure)

    self.client.on_connect = self._on_connect
    self.client.on_message = self._on_message
    self.client.connect(broker_host, broker_port, 60)

  def start(self):
    """Non-blocking background loop (for use as a library)."""
    self.client.loop_start()

  def run_forever(self):
    """Blocking loop (for standalone use)."""
    self.client.loop_forever()

  def _on_connect(self, client, userdata, flags, rc):
    logger.info(f"Connected (rc={rc})")
    client.subscribe(REG_TOPIC)
    client.subscribe(CAM5_TOPIC)
    logger.info(f"Subscribed: {REG_TOPIC}")
    logger.info(f"Subscribed: {CAM5_TOPIC}  (loop detection)")
    for t in SENSOR_TOPICS:
      client.subscribe(t)
      logger.info(f"Subscribed: {t}")

  def _on_message(self, client, userdata, msg):
    try:
      payload = json.loads(msg.payload.decode())
    except Exception:
      return
    try:
      if msg.topic == REG_TOPIC:
        self.cache.ingest_regulated(payload)
      elif msg.topic == CAM5_TOPIC:
        self.cache.ingest_cam5(payload)
      else:
        self.cache.ingest_sensor(msg.topic, payload)
    except Exception:
      # A single malformed message must never kill the ingest thread, which
      # would silently freeze the dashboard (no tracks → no alerts).
      logger.exception("Failed to ingest message on %s", msg.topic)


# ── Standalone entry point ─────────────────────────────────────────────────────
def main():
  p = argparse.ArgumentParser(description="Track cache — Showcase scene analytics feed")
  p.add_argument("--broker",     default="broker.scenescape.intel.com")
  p.add_argument("--port",       type=int, default=1883)
  p.add_argument("--ca-cert",    default="/run/secrets/certs/scenescape-ca.pem")
  p.add_argument("--tls-insecure", action="store_true")
  p.add_argument("--broker-auth",  default="/run/secrets/controller.auth")
  p.add_argument("--retention",  type=int, default=RETENTION_S,
                 help="Track history retention in seconds (default 600)")
  p.add_argument("--interval",   type=int, default=15,
                 help="Stats print interval in seconds (default 15)")
  p.add_argument("--dump",       action="store_true",
                 help="Dump full JSON snapshot on each stats interval")
  p.add_argument("--verbose",    action="store_true")
  args = p.parse_args()

  logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
  )

  cache = TrackCache(retention_s=args.retention)
  sub   = TrackSubscriber(
    cache,
    broker_host=args.broker,
    broker_port=args.port,
    ca_cert=args.ca_cert,
    tls_insecure=args.tls_insecure,
    broker_auth=args.broker_auth,
  )

  # Stats watchdog
  def _watchdog():
    while True:
      time.sleep(args.interval)
      print(f"── TrackCache  {cache.stats_line()}", flush=True)
      if args.dump:
        snap = cache.snapshot()
        print(json.dumps(snap, indent=2), flush=True)

  threading.Thread(target=_watchdog, daemon=True).start()
  logger.info(f"Track cache running  retention={args.retention}s")
  sub.run_forever()


if __name__ == "__main__":
  main()
