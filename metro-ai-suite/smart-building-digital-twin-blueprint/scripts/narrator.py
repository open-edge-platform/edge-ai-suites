#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Scene narrator — converts raw track + event data into a rolling text window.

Two input streams:
  1. Periodic regulated snapshot (every SNAPSHOT_INTERVAL_S seconds)
     → state block: who is where, posture, companions, door counts
  2. Discrete events (tripwire crossings, region enter/exit)
     → event lines: stamped, factual, no interpretation

Label registries (reset on each video loop):
  person_labels : track_uid   → "person-1", "person-2", ...
  luggage_labels: track_uid   → "luggage-1", ...

Person identity is tracked by track UUID, labelled "person-N" in order of
first appearance. Labels reset on each video loop. Badge/face credentials
are not used for identity as they are not reliably persistent.

Posture (for persons) is smoothed over POSTURE_WINDOW recent bounding boxes
using majority vote on aspect-ratio bucket to suppress noisy single frames.

Importable:
  from narrator import Narrator
  narrator = Narrator(cache)
  narrator.start()          # background snapshot thread
  text = narrator.window_text()

Standalone:
  BROKER_HOST=broker python3 narrator.py [--interval 5] [--print-window]
"""

import argparse
import datetime
import json
import logging
import math
import ssl
import sys
import threading
import time
from collections import deque, Counter
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).parent))
from track_cache import TrackCache, TrackSubscriber, REG_TOPIC, _now, _iso, SCENE_ID
from scene_config import (
  REGION_NAMES, FURNITURE_REGIONS, INERT_CATEGORIES, SENSOR_NAMES, TRIPWIRE_NAMES,
  CHECKPOINT_TRIPWIRE, ENTRY_TRIPWIRE,
  region_name, sensor_name, tripwire_name,
)

logger = logging.getLogger(__name__)

# ── Tunable ────────────────────────────────────────────────────────────────────
SNAPSHOT_INTERVAL_S = 5      # seconds between periodic state snapshots
WINDOW_MAX          = 300    # max text entries in rolling window
LIVE_TRACK_MAX_AGE_S = 3.0   # seconds — person/door tracks can coast briefly between regulated updates
INERT_TRACK_MAX_AGE_S = 0.75  # seconds — inert tracks should disappear quickly when occluded/lost
DISPLAY_INERT_TRACK_MAX_AGE_S = 3.0  # seconds — dashboard snapshots can coast luggage longer than security logic
COMPANION_DIST_M    = 1.5    # meters — closer than this = companions
STATIONARY_SPEED    = 0.08   # m/s — slower than this = stationary
INERT_GHOST_RECENT_N = 5     # recent inert samples to inspect for sticky moving ghosts
INERT_GHOST_FREEZE_M = 0.10  # meters — near-zero position spread with non-zero speed is untrusted
INERT_GHOST_SPEED_M = 0.12   # m/s — moving faster than this while spatially frozen is contradictory
POSTURE_WINDOW      = 10     # last N bounding-box samples for majority vote
FALL_MAX_SPEED_MS   = 0.35   # m/s — allow a small amount of motion-estimate jitter during fall confirmation
FALL_CONFIRM_S      = 2.0    # seconds — fall-like posture must persist before alerting
FALL_TRIGGER_PREVIOUS_POSTURES = {"upright", "partially upright", "compact", "wide"}
FALL_SUSTAIN_POSTURES = {"horizontal", "wide"}
FALL_RECOVERY_POSTURES = {"upright", "partially upright", "compact"}
GHOST_FREEZE_M      = 0.05   # meters — position spread below this = ghost track
GHOST_RECENT_N      = 30     # number of recent entries to inspect for ghost detection
GHOST_SPEED_THRESH  = 0.02   # m/s — reported speed below this = genuinely stationary, not a ghost
UNATTENDED_THRESH_S = 30     # seconds luggage must be alone before unattended alert
ABANDONMENT_DIST_M  = 4.0    # meters — former companion beyond this = abandonment
SWITCH_MATCH_WINDOW_S = 45.0  # look back this long for reciprocal swaps across ticks
SWITCH_MAX_SEPARATION_M = 3.0  # reciprocal switch candidates must occur near each other
STOLEN_MIN_PREV_COMPANION_S = 3.0  # previous companion must have been established, not just a brief walk-by
STOLEN_MIN_NEW_COMPANION_S = 0.75  # new companion must stay attached briefly before theft is credible

# Camera frame dimensions (pixels) — derived from intrinsics cx/cy in Showcase.json
# cx=640, cy=360 → principal point at center of 1280×720 frame
CAM_FRAME_W = 1280
CAM_FRAME_H = 720
EDGE_MARGIN = 10              # pixels — treat near-edge boxes as cropped to avoid false prone posture votes

# Door regions and expected door counts when closed
DOOR_REGIONS: dict[str, int] = {
  "DoubleDoorEntry": 2,
  "SideDoorEntry":   1,
  "ConferenceDoor":  1,
}

SIDE_DOOR_BASELINE_SAMPLES = 20
SIDE_DOOR_OPEN_OFFSET_M = 0.25


# ── Posture helpers ────────────────────────────────────────────────────────────

def _aspect_label(w: float, h: float) -> str:
  """Classify bounding box aspect ratio into a posture label."""
  if w <= 0 or h <= 0:
    return "unknown"
  ratio = h / w
  if ratio > 2.0:
    return "upright"
  if ratio > 1.2:
    return "partially upright"
  if ratio > 0.8:
    return "compact"
  if ratio > 0.5:
    return "wide"     # squat, crouch, or camera angle — not reliably prone
  return "horizontal"   # very wide bbox — likely prone


def _is_cropped(cb: dict) -> bool:
  """True if the bounding box touches the frame edge (partial view — unreliable aspect ratio)."""
  x, y = cb.get("x", 0), cb.get("y", 0)
  w, h = cb.get("width", 0), cb.get("height", 0)
  return (
    x <= EDGE_MARGIN or
    y <= EDGE_MARGIN or
    x + w >= CAM_FRAME_W - EDGE_MARGIN or
    y + h >= CAM_FRAME_H - EDGE_MARGIN
  )


def _smooth_posture(bounds_history: list[dict]) -> str:
  """Majority-vote posture using per-camera smoothing across recent history.

  Each camera first votes across its own recent bounding boxes, then the
  narrator combines those camera-level votes. This makes posture less sensitive
  to one camera briefly jittering between horizontal and wide while the track is
  otherwise stable.

  Boxes that touch the frame edge are excluded — a person walking toward the
  camera produces a vertically-cropped box whose aspect ratio shifts toward
  horizontal even though they are upright.
  """
  labels_by_camera: dict[str, list[str]] = {}
  for bounds in bounds_history:
    for cam_id, cam_bounds in bounds.items():
      if _is_cropped(cam_bounds):
        continue
      w = cam_bounds.get("width", 0)
      h = cam_bounds.get("height", 0)
      labels_by_camera.setdefault(cam_id, []).append(_aspect_label(w, h))

  if not labels_by_camera:
    return "unknown"

  camera_votes = [
    Counter(labels).most_common(1)[0][0]
    for labels in labels_by_camera.values()
    if labels
  ]
  if not camera_votes:
    return "unknown"
  return Counter(camera_votes).most_common(1)[0][0]


def _speed(vx: float, vy: float) -> float:
  """Return planar speed from x/y velocity components."""
  return math.sqrt(vx**2 + vy**2)


# ── Narrator ───────────────────────────────────────────────────────────────────

class Narrator:
  """Converts TrackCache state + live events into a rolling text window."""

  def __init__(self, cache: TrackCache, snapshot_interval: float = SNAPSHOT_INTERVAL_S):
    self._cache    = cache
    self._interval = snapshot_interval
    self._lock     = threading.Lock()

    # Rolling window of text lines/blocks
    self._window: deque[str] = deque(maxlen=WINDOW_MAX)

    # Companion pair → wall-clock time first seen close
    self._companion_since: dict[tuple, float] = {}
    # Track uid → wall-clock time first seen stationary
    self._stationary_since: dict[str, float] = {}
    # Previous nearest person uid per luggage uid
    self._prev_nearest: dict[str, str] = {}
    # Previous posture per track uid (for CHANGE detection)
    self._prev_posture: dict[str, str] = {}
    # Track uid → wall-clock time when a fall-like episode first qualified
    self._fall_candidate_since: dict[str, float] = {}
    # Track uid → posture observed before the current fall-like episode began
    self._fall_candidate_prev_posture: dict[str, str | None] = {}
    # Track uids already alerted for the current horizontal low-speed episode
    self._fall_alerted: set[str] = set()

    # Loop count mirror (to detect resets)
    self._last_loop = 0

    # External listeners — called with each emitted entry string
    self._listeners: list = []
    # Alert listeners — called only when a security alert is emitted
    self._alert_listeners: list = []

    # Credential → person uid (detect badge/face switching between persons)
    # Rebuilt each loop from the first observed face association for each badge.
    self._badge_face_baseline: dict[str, str] = {}  # badge_val → face_val
    # Badge values already alerted as switched this loop (cleared on loop reset)
    self._badge_switch_alerted: set[str] = set()
    # Badge values already warned on outbound tripwire crossings this loop
    self._badge_switch_warned: set[str] = set()
    # Luggage uid → wall-clock time it lost its companion
    self._luggage_alone_since: dict[str, float] = {}
    # Luggage uids already alerted as unattended (suppress repeats until companion returns)
    self._unattended_alerted: set[str] = set()
    # frozenset({uid_a, uid_b}) pairs already alerted as a coordinated companion swap
    self._luggage_switch_alerted: set[tuple] = set()
    # (luggage_uid, new_companion_uid) pairs already alerted as stolen (single-bag companion change)
    self._luggage_stolen_alerted: set[tuple] = set()
    # Last confirmed companion per luggage uid (persists after they leave companion zone)
    self._last_companion: dict[str, str] = {}
    # Luggage uids already alerted as abandoned (active companion walked away)
    self._abandonment_alerted: set[str] = set()
    # Recent confirmed transitions for cross-tick switch matching:
    # luggage_uid → (from_uid, to_uid, confirmed_wall_t, label, latest_entry, region_str)
    self._recent_transitions: dict[str, tuple] = {}
    # SideDoorEntry door baseline for open/closed inference in the dashboard state panel
    self._side_door_samples: list[tuple[float, float]] = []
    self._side_door_baseline: tuple[float, float] | None = None
    self._side_door_state = "unknown"
    self._side_door_learning_enabled = False
    # When the current/last established companion relationship began for each luggage uid
    self._last_companion_started: dict[str, float] = {}
    # Stolen-candidate listeners — called when a same-uid handoff becomes theft-credible.
    self._stolen_candidate_listeners: list = []
    # (luggage_uid, new_companion_uid) pairs already emitted as stolen candidates this loop.
    self._stolen_candidate_emitted: set[tuple[str, str]] = set()
    # State listeners — called with a dict on every tick
    self._state_listeners: list = []

  # ── Helpers ──────────────────────────────────────────────────

  def add_listener(self, cb) -> None:
    """Register a callback(entry: str) called on every emitted entry."""
    self._listeners.append(cb)

  def add_alert_listener(self, cb) -> None:
    """Register a callback(entry: str) called only on security alert entries."""
    self._alert_listeners.append(cb)

  def add_state_listener(self, cb) -> None:
    """Register a callback(state: dict) called on every tick with scene state."""
    self._state_listeners.append(cb)

  def add_stolen_candidate_listener(self, cb) -> None:
    """Register a callback(data: dict) for early stolen-handoff evidence capture."""
    self._stolen_candidate_listeners.append(cb)

  def _emit_state(self, state: dict) -> None:
    for cb in self._state_listeners:
      try:
        cb(state)
      except Exception:
        logger.exception("State listener error")

  def _emit_stolen_candidate(self, data: dict) -> None:
    for cb in self._stolen_candidate_listeners:
      try:
        cb(data)
      except Exception:
        logger.exception("Stolen candidate listener error")

  def _emit(self, entry: str) -> None:
    """Append entry to rolling window, print it, and notify listeners."""
    with self._lock:
      self._window.append(entry)
    print(entry, flush=True)
    for cb in self._listeners:
      try:
        cb(entry)
      except Exception:
        logger.exception("Narrator listener error")

  def _emit_alert(self, entry: str) -> None:
    """Emit a security alert — goes to window + print, then ONLY alert listeners.

    The generic listeners are intentionally skipped so that the alert is not
    pushed to the SSE stream twice (the alert listener in dashboard.py captures
    camera snapshots first and then pushes one combined message).  If no alert
    listeners are registered, fall back to generic listeners so standalone usage
    still works.
    """
    with self._lock:
      self._window.append(entry)
    print(entry, flush=True)

    if self._alert_listeners:
      for cb in self._alert_listeners:
        try:
          cb(entry)
        except Exception:
          logger.exception("Alert listener error")
    else:
      # No alert listeners — fall back to generic so standalone mode works
      for cb in self._listeners:
        try:
          cb(entry)
        except Exception:
          logger.exception("Narrator listener error")

  @staticmethod
  def _person_label(uid: str) -> str:
    return f"person-{uid[:3]}" if uid else "person-???"

  @staticmethod
  def _luggage_label(uid: str) -> str:
    return f"luggage-{uid[:3]}" if uid else "luggage-???"

  @staticmethod
  def _extract_val(sensor_data) -> str | None:
    """Normalize both pre-processed (scalar) and raw ({"values":[...]}) formats."""
    if sensor_data is None:
      return None
    if isinstance(sensor_data, dict):
      vals = sensor_data.get("values", [])
      return str(vals[-1][1]) if vals else None
    return str(sensor_data)

  def _cred_annot(self, sensors: dict) -> str:
    """Return ' [badge-4c4, face-a6e]' from sensor dict, or '' if no credentials."""
    b = self._extract_val(sensors.get("badge-001"))
    f = self._extract_val(sensors.get("faceid-001"))
    parts = []
    if b:
      parts.append(f"badge-{b[:3]}")
    if f:
      parts.append(f"face-{f[:3]}")
    return " [" + ", ".join(parts) + "]" if parts else ""

  @staticmethod
  def _pos_str(x: float, y: float) -> str:
    return f" @ ({x:.2f}, {y:.2f})"

  @staticmethod
  def _cam_str(cameras: list[str]) -> str:
    """Return a formatted camera suffix from a list of camera IDs."""
    cams = sorted(cameras)
    return f" [cams: {', '.join(cams)}]" if cams else ""

  def _motion_text(self, uid: str, speed: float, now: float) -> str:
    """Return snapshot motion text while maintaining stationary durations."""
    if speed < STATIONARY_SPEED:
      if uid not in self._stationary_since:
        self._stationary_since[uid] = now
      duration = int(now - self._stationary_since[uid])
      return f"stationary ({duration}s)"

    self._stationary_since.pop(uid, None)
    return f"moving {speed:.1f}m/s"

  @staticmethod
  def _person_position_tuple(entry: dict) -> tuple:
    """Return the normalized person tuple used by companion logic."""
    return (
      entry["x"],
      entry["y"],
      entry["sensors"],
      entry.get("vx", 0.0),
      entry.get("vy", 0.0),
      entry.get("cameras", []),
    )

  def _person_positions(self, persons: dict) -> dict[str, tuple]:
    """Build the latest visible person positions for companion inference and snapshots."""
    positions = {}
    for uid, trk in persons.items():
      entry = list(trk["entries"])[-1]
      positions[uid] = self._person_position_tuple(entry)
    return positions

  @staticmethod
  def _is_ghost(entries: list) -> bool:
    """True if the object's position is frozen but its reported speed is non-trivial.

    A real stationary object (e.g. a door sensor) reports near-zero velocity AND
    doesn't move — that is legitimate and should NOT be filtered.
    A ghost track reports non-zero velocity but its position never changes —
    that contradiction is the signal we filter on.
    """
    recent = entries[-GHOST_RECENT_N:]
    if len(recent) < 2:
      return False
    # If the reported speed is genuinely near-zero, trust the object as stationary
    avg_speed = sum(_speed(e["vx"], e["vy"]) for e in recent) / len(recent)
    if avg_speed < GHOST_SPEED_THRESH:
      return False
    # Speed is non-trivial but position isn't moving → ghost
    xs = [e["x"] for e in recent]
    ys = [e["y"] for e in recent]
    return (max(xs) - min(xs)) < GHOST_FREEZE_M and (max(ys) - min(ys)) < GHOST_FREEZE_M

  @staticmethod
  def _ts_str(ts: str = "") -> str:
    """ISO 8601 UTC timestamp. Uses payload string if given, else current clock."""
    if ts:
      return ts
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

  def _cam_str_for(self, uid: str) -> str:
    """Return ' [cams: cam-1, cam-2]' from latest cache entry for uid, or ''."""
    with self._cache._lock:
      trk     = self._cache._tracks.get(uid, {})
      entries = trk.get("entries")
      cams    = sorted(entries[-1].get("cameras", [])) if entries else []
    return f" [cams: {', '.join(cams)}]" if cams else ""

  def _sync_loop_state(self) -> None:
    """Apply loop resets before consuming either snapshots or streaming updates."""
    lc = self._cache._loop_count
    if lc != self._last_loop:
      self._last_loop = lc
      self.on_loop_clear()

  def _person_state(self, uid: str, entries: list[dict]) -> dict:
    """Derive the current person state from cached regulated entries."""
    latest = entries[-1]
    speed = _speed(latest["vx"], latest["vy"])
    regions = [region_name(r) for r in latest["regions"] if r != "showcase_light"]
    region_str = ", ".join(regions) if regions else "open area"
    recent_bounds = [e["cam_bounds"] for e in entries[-POSTURE_WINDOW:] if e["cam_bounds"]]
    posture = _smooth_posture(recent_bounds)
    return {
      "latest": latest,
      "entries": entries,
      "speed": speed,
      "region_str": region_str,
      "posture": posture,
      "cam_str": self._cam_str(latest.get("cameras", [])),
      "pos": self._pos_str(latest["x"], latest["y"]),
      "in_furniture": any(region_name(r) in FURNITURE_REGIONS for r in latest["regions"]),
    }

  def _clear_inert_state(self, uid: str) -> None:
    """Drop derived state for an inert track that is no longer considered live."""
    self._stationary_since.pop(uid, None)
    self._luggage_alone_since.pop(uid, None)
    self._abandonment_alerted.discard(uid)
    self._unattended_alerted.discard(uid)
    self._companion_since = {
      pair: since for pair, since in self._companion_since.items()
      if pair[0] != uid
    }

  @staticmethod
  def _nearest_person(latest: dict, person_positions: dict) -> tuple[str | None, float]:
    """Return the nearest visible person to the inert object, if any."""
    nearest_uid, nearest_dist = None, float("inf")
    for puid, (px, py, _sensors, _vx, _vy, _pcams) in person_positions.items():
      distance = math.sqrt((latest["x"] - px)**2 + (latest["y"] - py)**2)
      if distance < nearest_dist:
        nearest_uid, nearest_dist = puid, distance
    return nearest_uid, nearest_dist

  @staticmethod
  def _trusted_inert_track(entries: list[dict], speed: float, nearest_dist: float) -> bool:
    """True when an inert track is physically plausible enough for security logic.

    Inert objects cannot move on their own. A track that reports non-trivial
    motion while its position is effectively frozen is a sticky ghost and
    should be ignored.
    """
    recent = entries[-INERT_GHOST_RECENT_N:]
    if len(recent) >= 2:
      avg_speed = sum(
        math.sqrt(entry["vx"]**2 + entry["vy"]**2) for entry in recent
      ) / len(recent)
      xs = [entry["x"] for entry in recent]
      ys = [entry["y"] for entry in recent]
      spread = max(max(xs) - min(xs), max(ys) - min(ys))
      if spread < INERT_GHOST_FREEZE_M and avg_speed > INERT_GHOST_SPEED_M:
        return False
    return True

  def _current_live_tracks(
    self,
    now: float,
    inert_max_age_s: float = INERT_TRACK_MAX_AGE_S,
    clear_stale_inert_state: bool = True,
  ) -> tuple[dict, dict, dict]:
    """Return current live persons, inert objects, and doors from the cache."""
    with self._cache._lock:
      live = {
        uid: trk for uid, trk in self._cache._tracks.items()
        if trk.get("entries") and (
          now - trk["last_t"]
        ) < (
          inert_max_age_s
          if trk.get("category") in INERT_CATEGORIES
          else LIVE_TRACK_MAX_AGE_S
        )
      }
      all_inert_uids = {
        uid for uid, trk in self._cache._tracks.items()
        if trk.get("category") in INERT_CATEGORIES and trk.get("entries")
      }

    live = {
      uid: trk for uid, trk in live.items()
      if not self._is_ghost(list(trk["entries"]))
    }

    live_inert_uids = {
      uid for uid, trk in live.items()
      if trk["category"] in INERT_CATEGORIES
    }
    if clear_stale_inert_state:
      for uid in all_inert_uids - live_inert_uids:
        self._clear_inert_state(uid)

    persons = {uid: t for uid, t in live.items() if t["category"] == "person"}
    inerts = {uid: t for uid, t in live.items() if t["category"] in INERT_CATEGORIES}
    doors = {uid: t for uid, t in live.items() if t["category"] == "door"}
    return persons, inerts, doors

  def _infer_side_door_state(self, persons: dict, luggages: dict, doors: dict) -> tuple[str, int, int]:
    """Infer SideDoorEntry state from door displacement, not person occupancy alone."""
    side_door_positions = []
    for trk in doors.values():
      latest = list(trk["entries"])[-1]
      if any(region_name(r) == "SideDoorEntry" for r in latest.get("regions", [])):
        side_door_positions.append((latest["x"], latest["y"]))

    if self._side_door_learning_enabled and self._side_door_baseline is None and side_door_positions:
      self._side_door_samples.extend(side_door_positions)
      if len(self._side_door_samples) >= SIDE_DOOR_BASELINE_SAMPLES:
        xs = [pos[0] for pos in self._side_door_samples]
        ys = [pos[1] for pos in self._side_door_samples]
        self._side_door_baseline = (sum(xs) / len(xs), sum(ys) / len(ys))
        self._side_door_samples.clear()

    side_occupancy = 0
    for trk in {**persons, **luggages}.values():
      latest = list(trk["entries"])[-1]
      if any(region_name(r) == "SideDoorEntry" for r in latest.get("regions", [])):
        side_occupancy += 1

    if self._side_door_baseline and side_door_positions:
      displacement = max(
        math.sqrt((x - self._side_door_baseline[0])**2 + (y - self._side_door_baseline[1])**2)
        for x, y in side_door_positions
      )
      self._side_door_state = "open" if displacement >= SIDE_DOOR_OPEN_OFFSET_M else "closed"
    elif side_occupancy > 0:
      self._side_door_state = "open"
    elif self._side_door_state == "unknown":
      self._side_door_state = "closed"

    return self._side_door_state, len(side_door_positions), 1

  def _process_badge_security(
    self,
    sensors: dict,
    relt: str,
    subject_label: str,
    pos: str,
    cam_str: str,
    context_label: str,
    tripwire_name: str,
    inbound: bool,
  ) -> None:
    """Process badge/face baseline learning and badge-switch alerts from tripwire events."""
    b_val = self._extract_val(sensors.get("badge-001"))
    f_val = self._extract_val(sensors.get("faceid-001"))
    if not (b_val and f_val):
      return

    clabel = f"badge-{b_val[:3]}"
    if b_val not in self._badge_face_baseline:
      self._badge_face_baseline[b_val] = f_val
      logger.info(
        f"Badge baseline learned: {clabel} → face-{f_val[:3]}"
      )
      return

    if f_val != self._badge_face_baseline[b_val]:
      orig_face = self._badge_face_baseline[b_val]
      monitored_tripwire = tripwire_name in (CHECKPOINT_TRIPWIRE, ENTRY_TRIPWIRE)
      if inbound and monitored_tripwire and b_val not in self._badge_switch_alerted:
        self._emit_alert(
          f"[ALERT {relt}]  badge switch: {clabel}\n"
          f"  {subject_label}{pos}{cam_str} [{context_label}]"
          f" — badge originally paired with face-{orig_face[:3]}, now on face-{f_val[:3]}"
        )
        self._badge_switch_alerted.add(b_val)
      elif not inbound and monitored_tripwire and b_val not in self._badge_switch_warned:
        self._emit_alert(
          f"[WARN {relt}]  possible badge switch: {clabel}\n"
          f"  {subject_label}{pos}{cam_str} [{context_label}]"
          f" — badge originally paired with face-{orig_face[:3]}, now on face-{f_val[:3]} during outbound crossing"
        )
        self._badge_switch_warned.add(b_val)

  def _process_inert_security(self, now: float, relt: str, persons: dict, inerts: dict) -> None:
    """Process inert-object companion inference and security alerts at stream cadence."""
    person_positions = self._person_positions(persons)
    companion_transitions: dict = {}
    current_companions: dict[str, str] = {}
    for uid, trk in inerts.items():
      label = self._luggage_label(uid)
      entries = list(trk["entries"])
      latest = entries[-1]
      speed = _speed(latest["vx"], latest["vy"])
      recently_mobile = any(
        _speed(entry["vx"], entry["vy"]) >= STATIONARY_SPEED
        for entry in entries[-INERT_GHOST_RECENT_N:]
      )
      region_str = ", ".join(region_name(r) for r in latest["regions"] if r != "showcase_light") or "open area"
      nearest_uid, nearest_dist = self._nearest_person(latest, person_positions)
      if not self._trusted_inert_track(entries, speed, nearest_dist):
        self._clear_inert_state(uid)
        continue
      prev_near = self._prev_nearest.get(uid)
      prior_companion = prev_near or self._last_companion.get(uid)
      prior_companion_started = (
        self._last_companion_started.get(uid)
        if self._last_companion.get(uid) == prior_companion
        else None
      )

      existing_companion = next(
        (puid for (luid, puid) in self._companion_since if luid == uid), None
      )
      allow_companion_inference = recently_mobile
      companion_uid = None
      companion_dist = float("inf")

      if existing_companion:
        if existing_companion in person_positions:
          px, py, _, _vx, _vy, _pcams = person_positions[existing_companion]
          distance = math.sqrt((latest["x"] - px)**2 + (latest["y"] - py)**2)
          if distance < COMPANION_DIST_M:
            companion_uid = existing_companion
            companion_dist = distance
          else:
            self._companion_since.pop((uid, existing_companion), None)
        else:
          self._companion_since.pop((uid, existing_companion), None)

      if companion_uid is None and allow_companion_inference:
        for puid, (px, py, _, _vx, _vy, _pcams) in person_positions.items():
          distance = math.sqrt((latest["x"] - px)**2 + (latest["y"] - py)**2)
          if distance < companion_dist:
            companion_dist, companion_uid = distance, puid
        if companion_dist >= COMPANION_DIST_M:
          companion_uid = None

      if companion_uid:
        current_companions[uid] = companion_uid
        pair = (uid, companion_uid)
        if pair not in self._companion_since:
          self._companion_since[pair] = now
        if self._last_companion.get(uid) != companion_uid:
          self._last_companion_started[uid] = now
        self._luggage_alone_since.pop(uid, None)
        self._unattended_alerted.discard(uid)
        self._abandonment_alerted.discard(uid)
        self._last_companion[uid] = companion_uid
      else:
        last_cmp = self._last_companion.get(uid)
        if last_cmp and last_cmp in person_positions and uid not in self._abandonment_alerted:
          px, py, _, pvx, pvy, pcams = person_positions[last_cmp]
          p_speed = _speed(pvx, pvy)
          dist_away = math.sqrt((latest["x"] - px)**2 + (latest["y"] - py)**2)
          if dist_away >= ABANDONMENT_DIST_M and p_speed > STATIONARY_SPEED:
            plabel = self._person_label(last_cmp)
            pcred = self._cred_annot(person_positions[last_cmp][2])
            cams_combined = sorted(set(latest.get("cameras", [])) | set(pcams))
            cam_ab = self._cam_str(cams_combined)
            self._emit_alert(
              f"[ALERT {relt}]  luggage abandoned: {label}\n"
              f"  {plabel}{pcred} walked away {dist_away:.1f}m at {p_speed:.1f}m/s"
              f"{self._pos_str(latest['x'], latest['y'])}{cam_ab} [{region_str}]"
            )
            self._abandonment_alerted.add(uid)

        if uid not in self._luggage_alone_since:
          self._luggage_alone_since[uid] = now
        alone_s = int(now - self._luggage_alone_since[uid])
        if alone_s >= UNATTENDED_THRESH_S and uid not in self._unattended_alerted:
          cams_a = sorted(latest.get("cameras", []))
          cam_a = self._cam_str(cams_a)
          self._emit_alert(
            f"[ALERT {relt}]  unattended luggage: {label}\n"
            f"  no companion for {alone_s}s"
            f"{self._pos_str(latest['x'], latest['y'])}{cam_a} [{region_str}]"
          )
          self._unattended_alerted.add(uid)

      if allow_companion_inference and prior_companion and companion_uid and prior_companion != companion_uid:
        prior_companion_age = (
          now - prior_companion_started
          if prior_companion_started is not None
          else 0.0
        )
        logger.info(
          "Luggage transition %s: %s -> %s age=%.1fs at (%.2f, %.2f)",
          label,
          prior_companion[:8],
          companion_uid[:8],
          prior_companion_age,
          latest["x"],
          latest["y"],
        )
        companion_transitions[uid] = (
          prior_companion,
          companion_uid,
          label,
          latest,
          region_str,
          prior_companion_age,
        )
      if companion_uid is not None:
        self._prev_nearest[uid] = companion_uid

    recent_candidates = {
      uid: (prev, new, lbl, lat, rs, prev_age)
      for uid, (prev, new, t, lbl, lat, rs, prev_age) in self._recent_transitions.items()
      if (now - t) <= SWITCH_MATCH_WINDOW_S and uid not in companion_transitions
    }
    all_transition_candidates = {**recent_candidates, **companion_transitions}
    all_candidates = list(all_transition_candidates.items())
    emitted_as_switch: set[str] = set()
    for i, (uid_a, (prev_a, new_a, label_a, latest_a, rs_a, _prev_age_a)) in enumerate(all_candidates):
      for uid_b, (prev_b, new_b, label_b, latest_b, rs_b, _prev_age_b) in all_candidates[i + 1:]:
        if prev_a == new_b and prev_b == new_a:
          same_tick_pair = uid_a in companion_transitions and uid_b in companion_transitions
          if not same_tick_pair:
            switch_dist = math.sqrt((latest_a["x"] - latest_b["x"])**2 + (latest_a["y"] - latest_b["y"])**2)
            if switch_dist > SWITCH_MAX_SEPARATION_M:
              continue
          switch_pair = tuple(sorted([uid_a, uid_b]))
          if switch_pair not in self._luggage_switch_alerted:
            cams_all = sorted(set(latest_a.get("cameras", [])) | set(latest_b.get("cameras", [])))
            cam_s = self._cam_str(cams_all)
            pa_label = self._person_label(prev_a)
            pa_cred = self._cred_annot(person_positions[prev_a][2]) if prev_a in person_positions else ""
            pb_label = self._person_label(new_a)
            pb_cred = self._cred_annot(person_positions[new_a][2]) if new_a in person_positions else ""
            self._emit_alert(
              f"[ALERT {relt}]  luggage switch: {label_a} ↔ {label_b}\n"
              f"  {label_a}: {pa_label}{pa_cred} → {pb_label}{pb_cred}"
              f"{self._pos_str(latest_a['x'], latest_a['y'])}{cam_s} [{rs_a}]\n"
              f"  {label_b}: {pb_label}{pb_cred} → {pa_label}{pa_cred}"
              f"{self._pos_str(latest_b['x'], latest_b['y'])} [{rs_b}]"
            )
            self._luggage_switch_alerted.add(switch_pair)
          emitted_as_switch.add(uid_a)
          emitted_as_switch.add(uid_b)

    pending_stolen_candidates = {
      uid: (prev, new, transition_t, label, latest, rs, prev_age)
      for uid, (prev, new, transition_t, label, latest, rs, prev_age) in self._recent_transitions.items()
      if (now - transition_t) <= SWITCH_MATCH_WINDOW_S
    }
    for uid, (prev, new, label, latest, rs, prev_age) in companion_transitions.items():
      pending_stolen_candidates[uid] = (prev, new, now, label, latest, rs, prev_age)

    for uid, (prev, new, label, latest, _rs, prev_age) in companion_transitions.items():
      if uid in emitted_as_switch or prev_age < STOLEN_MIN_PREV_COMPANION_S:
        continue
      candidate_key = (uid, new)
      if candidate_key in self._stolen_candidate_emitted:
        continue
      cam_ids = set(latest.get("cameras", []))
      if prev in person_positions:
        cam_ids.update(person_positions[prev][5])
      if new in person_positions:
        cam_ids.update(person_positions[new][5])
      self._emit_stolen_candidate({
        "key": f"{label}|{self._person_label(prev)}|{self._person_label(new)}",
        "camera_ids": sorted(cam_ids),
      })
      self._stolen_candidate_emitted.add(candidate_key)

    for uid, (prev, new, transition_t, label, latest, rs, prev_age) in pending_stolen_candidates.items():
      if uid in emitted_as_switch:
        self._recent_transitions.pop(uid, None)
        continue
      if current_companions.get(uid) != new:
        continue
      if prev_age < STOLEN_MIN_PREV_COMPANION_S:
        continue
      attachment_started = self._companion_since.get((uid, new), transition_t)
      if (now - attachment_started) < STOLEN_MIN_NEW_COMPANION_S:
        continue
      stolen_key = (uid, new)
      if stolen_key not in self._luggage_stolen_alerted:
        cams_l = sorted(latest.get("cameras", []))
        cam_l = self._cam_str(cams_l)
        old_label = self._person_label(prev)
        old_cred = self._cred_annot(person_positions[prev][2]) if prev in person_positions else ""
        new_cred = self._cred_annot(person_positions[new][2]) if new in person_positions else ""
        self._emit_alert(
          f"[ALERT {relt}]  luggage stolen: {label}\n"
          f"  companion changed from {old_label}{old_cred} → {self._person_label(new)}{new_cred}"
          f"{self._pos_str(latest['x'], latest['y'])}{cam_l} [{rs}]"
        )
        self._luggage_stolen_alerted.add(stolen_key)

    for uid, (prev, new, lbl, lat, rs, prev_age) in companion_transitions.items():
      if uid in emitted_as_switch:
        self._recent_transitions.pop(uid, None)
        continue
      self._recent_transitions[uid] = (prev, new, now, lbl, lat, rs, prev_age)
    self._recent_transitions = {
      uid: transition for uid, transition in self._recent_transitions.items()
      if (now - transition[2]) <= SWITCH_MATCH_WINDOW_S
    }

  def _describe_inert_companion(self, uid: str, latest: dict, person_positions: dict) -> str:
    """Return the current companion/nearest-person description for snapshot output."""
    existing_companion = next(
      (puid for (luid, puid) in self._companion_since if luid == uid), None
    )
    if existing_companion and existing_companion in person_positions:
      px, py, sensors, _vx, _vy, _pcams = person_positions[existing_companion]
      distance = math.sqrt((latest["x"] - px)**2 + (latest["y"] - py)**2)
      if distance < COMPANION_DIST_M:
        together = int(_now() - self._companion_since.get((uid, existing_companion), _now()))
        return (
          f" — companion: {self._person_label(existing_companion)}"
          f"{self._cred_annot(sensors)} {distance:.1f}m (together {together}s)"
        )

    nearest_uid, nearest_dist = None, float("inf")
    for puid, (px, py, sensors, _vx, _vy, _pcams) in person_positions.items():
      distance = math.sqrt((latest["x"] - px)**2 + (latest["y"] - py)**2)
      if distance < nearest_dist:
        nearest_uid, nearest_dist = puid, distance

    if nearest_uid:
      return (
        f" — nearest person: {self._person_label(nearest_uid)}"
        f"{self._cred_annot(person_positions[nearest_uid][2])} {nearest_dist:.1f}m away"
      )
    return " — no person nearby"

  def _maybe_emit_fall_alert(self, uid: str, relt: str, person_state: dict, now: float) -> None:
    """Run fall detection for one person on the streaming regulated cadence."""
    posture = person_state["posture"]
    speed = person_state["speed"]
    prev_p = self._prev_posture.get(uid)
    self._prev_posture[uid] = posture

    is_fall_candidate = (
      posture == "horizontal"
      and speed < FALL_MAX_SPEED_MS
      and not person_state["in_furniture"]
    )
    if (
      not is_fall_candidate
      and uid in self._fall_candidate_since
      and posture in FALL_SUSTAIN_POSTURES
      and speed < FALL_MAX_SPEED_MS
      and not person_state["in_furniture"]
    ):
      is_fall_candidate = True
    if is_fall_candidate:
      if uid not in self._fall_candidate_since:
        self._fall_candidate_since[uid] = now
        self._fall_candidate_prev_posture[uid] = prev_p
        logger.info(
          "Fall candidate started for %s: prev_posture=%s posture=%s speed=%.2f region=%s",
          self._person_label(uid), prev_p, posture, speed, person_state["region_str"],
        )
      candidate_age = now - self._fall_candidate_since[uid]
      candidate_prev_p = self._fall_candidate_prev_posture.get(uid)
      if (
        uid not in self._fall_alerted
        and candidate_age >= FALL_CONFIRM_S
        and candidate_prev_p in FALL_TRIGGER_PREVIOUS_POSTURES
      ):
        detail = (
          f"posture changed {candidate_prev_p} → horizontal and persisted for {candidate_age:.1f}s"
          if candidate_prev_p and candidate_prev_p != posture
          else f"horizontal posture persisted for {candidate_age:.1f}s while motion stayed below fall threshold"
        )
        self._emit_alert(
          f"[ALERT {relt}]  possible fall detected\n"
          f"  {self._person_label(uid)}{person_state['pos']}{person_state['cam_str']} "
          f"[{person_state['region_str']}] {detail} (not in furniture region)"
        )
        logger.info(
          "Fall alert emitted for %s after %.2fs: posture=%s speed=%.2f region=%s",
          self._person_label(uid), candidate_age, posture, speed, person_state["region_str"],
        )
        self._fall_alerted.add(uid)
    else:
      if uid in self._fall_candidate_since:
        candidate_age = now - self._fall_candidate_since[uid]
        logger.info(
          "Fall candidate reset for %s after %.2fs: posture=%s speed=%.2f in_furniture=%s region=%s",
          self._person_label(uid), candidate_age, posture, speed,
          person_state["in_furniture"], person_state["region_str"],
        )
      self._fall_candidate_since.pop(uid, None)
      self._fall_candidate_prev_posture.pop(uid, None)
      if uid in self._fall_alerted and (
        person_state["in_furniture"] or posture in FALL_RECOVERY_POSTURES
      ):
        self._fall_alerted.discard(uid)

  def on_regulated(self, payload: dict):
    """Process regulated scene updates that require frame-rate cadence analytics."""
    self._sync_loop_state()
    now = _now()
    relt = self._ts_str(payload.get("timestamp", ""))
    persons, inerts, _doors = self._current_live_tracks(now)

    for uid, trk in persons.items():
      entries = list(trk["entries"])
      person_state = self._person_state(uid, entries)
      self._maybe_emit_fall_alert(uid, relt, person_state, now)

    self._process_inert_security(now, relt, persons, inerts)

  # ── Loop clear ────────────────────────────────────────────────────────────────

  def on_loop_clear(self):
    """Called when the video loop resets — clear all per-loop state."""
    with self._lock:
      if not self._side_door_learning_enabled:
        self._side_door_learning_enabled = True
        self._side_door_samples.clear()
        self._side_door_baseline = None
        self._side_door_state = "unknown"
        logger.info("Narrator: SideDoorEntry baseline learning enabled after initial loop")
      self._companion_since.clear()
      self._stationary_since.clear()
      self._prev_nearest.clear()
      self._prev_posture.clear()
      self._fall_candidate_since.clear()
      self._fall_candidate_prev_posture.clear()
      self._fall_alerted.clear()
      self._window.clear()
      self._badge_face_baseline.clear()
      self._badge_switch_alerted.clear()
      self._badge_switch_warned.clear()
      self._luggage_alone_since.clear()
      self._unattended_alerted.clear()
      self._luggage_switch_alerted.clear()
      self._luggage_stolen_alerted.clear()
      self._stolen_candidate_emitted.clear()
      self._last_companion.clear()
      self._last_companion_started.clear()
      self._abandonment_alerted.clear()
      self._unattended_alerted.clear()
      self._recent_transitions.clear()
      logger.info("Narrator: loop reset")
    self._emit(f"[event {self._ts_str()}]  video loop restarted")

  # ── Periodic snapshot ─────────────────────────────────────────────────────────

  def tick(self):
    """Produce one state snapshot from the current cache and append to window."""
    self._sync_loop_state()
    now   = _now()
    relt  = self._ts_str()
    persons, luggages, doors = self._current_live_tracks(
      now,
      inert_max_age_s=DISPLAY_INERT_TRACK_MAX_AGE_S,
      clear_stale_inert_state=False,
    )

    lines = [f"[snapshot {relt}]  "
             f"{len(persons)} person(s)  {len(luggages)} luggage  {len(doors)} door(s)"]

    # ── Persons ────────────────────────────────────────────────────────────────
    for uid, trk in persons.items():
      entries = list(trk["entries"])
      person_state = self._person_state(uid, entries)
      latest  = person_state["latest"]
      motion  = self._motion_text(uid, person_state["speed"], now)

      region_str = person_state["region_str"]
      posture = person_state["posture"]

      plabel  = self._person_label(uid)
      cred    = self._cred_annot(latest["sensors"])
      pos     = person_state["pos"]
      cam_str = person_state["cam_str"]

      lines.append(
        f"  {plabel}{cred}{pos}{cam_str} [{region_str}] [{posture}] {motion}"
      )

    # ── Inert Objects ─────────────────────────────────────────────────────────
    person_positions = self._person_positions(persons)

    for uid, trk in luggages.items():
      label   = self._luggage_label(uid)
      entries = list(trk["entries"])
      latest  = entries[-1]
      speed   = _speed(latest["vx"], latest["vy"])
      motion  = self._motion_text(uid, speed, now)
      regions    = [region_name(r) for r in latest["regions"] if r != "showcase_light"]
      region_str = ", ".join(regions) if regions else "open area"
      companion_str = self._describe_inert_companion(uid, latest, person_positions)

      cam_str = self._cam_str(latest.get("cameras", []))
      lines.append(
        f"  {label}{self._pos_str(latest['x'], latest['y'])}{cam_str} [{region_str}] {motion}{companion_str}"
      )

    # ── Regions & scene occupancy ──────────────────────────────────────────────
    # Build a dict: region_name → {persons: [(label,dwell)], luggage: [...], doors: int}
    region_summary: dict[str, dict] = {}

    for uid, trk in {**persons, **luggages}.items():
      is_person = trk["category"] == "person"
      latest_e  = list(trk["entries"])[-1]
      label     = self._person_label(uid) if is_person else self._luggage_label(uid)
      rv        = trk.get("regions_visited", {})
      for r in latest_e["regions"]:
        rn = region_name(r)
        if rn in ("ShowcaseLight", "showcase_light"):
          continue
        if rn not in region_summary:
          region_summary[rn] = {"persons": [], "luggage": [], "doors": 0}
        # Dwell = seconds since first entered this region (from cache)
        entered_iso = rv.get(r, "")
        dwell = int(now - _iso(entered_iso)) if entered_iso else 0
        if is_person:
          region_summary[rn]["persons"].append((label, dwell))
        else:
          region_summary[rn]["luggage"].append((label, dwell))

    for uid, trk in doors.items():
      latest_e = list(trk["entries"])[-1]
      for r in latest_e["regions"]:
        rn = region_name(r)
        if rn in ("ShowcaseLight", "showcase_light"):
          continue
        if rn not in region_summary:
          region_summary[rn] = {"persons": [], "luggage": [], "doors": 0}
        region_summary[rn]["doors"] += 1

    lines.append(f"  scene: {len(persons)} person(s)  {len(luggages)} luggage  (total occupancy)")
    for rn in sorted(region_summary):
      rd = region_summary[rn]
      parts = []
      if rd["doors"]:
        parts.append(f"{rd['doors']} door(s)")
      for plabel, dwell in rd["persons"]:
        parts.append(f"{plabel} {dwell}s")
      for llabel, dwell in rd["luggage"]:
        parts.append(f"{llabel} {dwell}s")
      lines.append(f"  {rn}: " + ", ".join(parts) if parts else f"  {rn}: empty")

    self._emit("\n".join(lines))

    # ── Scene state (for dashboard state panel) ───────────────────────────────
    if self._state_listeners:
      state_counts: dict[str, int] = {}
      state_regions: dict[str, dict[str, int]] = {}
      for uid, trk in {**persons, **luggages, **doors}.items():
        cat = trk["category"]
        state_counts[cat] = state_counts.get(cat, 0) + 1
        latest_e = list(trk["entries"])[-1]
        for r in latest_e.get("regions", []):
          rn = region_name(r)
          if rn in ("ShowcaseLight", "showcase_light"):
            continue
          if rn not in state_regions:
            state_regions[rn] = {}
          state_regions[rn][cat] = state_regions[rn].get(cat, 0) + 1

      state_doors: dict[str, dict] = {}
      for dr, expected in DOOR_REGIONS.items():
        if dr == "SideDoorEntry":
          state, count, expected_count = self._infer_side_door_state(persons, luggages, doors)
          state_doors[dr] = {
            "state": state,
            "count": count,
            "expected": expected_count,
          }
        else:
          count = state_regions.get(dr, {}).get("door", 0)
          state_doors[dr] = {
            "state":    "closed" if count >= expected else "open",
            "count":    count,
            "expected": expected,
          }

      self._emit_state({
        "timestamp": relt,
        "counts":  state_counts,
        "regions": state_regions,
        "doors":   state_doors,
      })

  # ── Discrete events ───────────────────────────────────────────────────────────

  def on_tripwire(self, payload: dict):
    """Process a tripwire crossing event."""
    tw_name = payload.get("tripwire_name") or tripwire_name(payload.get("tripwire_id",""))
    ts      = payload.get("timestamp", "")
    relt    = self._ts_str(ts)
    counts  = payload.get("counts", {})
    count_str = "  ".join(f"{v} {k}" for k, v in counts.items() if v)

    event_lines = [f"[event {relt}]  tripwire '{tw_name}' crossed  ({count_str})"]

    for obj in payload.get("objects", []):
      inbound   = obj.get("direction", 1) > 0
      direction = "inbound" if inbound else "outbound"
      cat       = obj.get("category", "object")
      speed     = math.sqrt(sum(v**2 for v in obj.get("velocity", [0,0,0])[:2]))
      tr        = obj.get("translation", [])
      pos       = self._pos_str(tr[0], tr[1]) if len(tr) >= 2 else ""
      cam_str   = self._cam_str_for(obj.get("id", ""))
      if cat == "person":
        obj_label = self._person_label(obj.get("id", ""))
        # The tripwire event's sensors field reflects the track state at crossing
        # time. Use it directly — Scenescape keeps sensors sticky on the track so
        # a badge read near the reader persists through the Checkpoint crossing.
        # If the field is absent (Scenescape version difference), fall back to the
        # latest entry in our track cache which mirrors the regulated topic state.
        sensors = obj.get("sensors") or {}
        if not sensors:
          uid = obj.get("id", "")
          with self._cache._lock:
            trk = self._cache._tracks.get(uid, {})
            entries = trk.get("entries")
            if entries:
              sensors = entries[-1].get("sensors", {})
        cred = self._cred_annot(sensors)
        self._process_badge_security(
          sensors,
          relt,
          obj_label,
          pos,
          cam_str,
          f"tripwire {tw_name}",
          tw_name,
          inbound,
        )
        if tw_name == CHECKPOINT_TRIPWIRE and inbound and not cred:
          # Emit a dedicated alert with a descriptive title — separate from the event log
          self._emit_alert(
            f"[ALERT {relt}]  Checkpoint crossed without badge credential\n"
            f"  {obj_label}{pos}{cam_str} crossed inbound at {speed:.1f}m/s — no badge detected"
          )
          event_lines.append(f"  {obj_label}{pos}{cam_str} crossed {direction} at {speed:.1f}m/s  ⚠ no badge credential")
        elif tw_name == ENTRY_TRIPWIRE and inbound and cred:
          event_lines.append(f"  {obj_label}{cred}{pos}{cam_str} crossed {direction} at {speed:.1f}m/s  ℹ credentials present at Entry (before readers)")
        else:
          event_lines.append(f"  {obj_label}{cred}{pos}{cam_str} crossed {direction} at {speed:.1f}m/s")
      elif cat == "luggage":
        obj_label = self._luggage_label(obj.get("id", ""))
        event_lines.append(f"  {obj_label}{pos}{cam_str} crossed {direction} at {speed:.1f}m/s")
      else:
        event_lines.append(f"  {cat}{pos}{cam_str} crossed {direction} at {speed:.1f}m/s")

    self._emit("\n".join(event_lines))

  def on_region_event(self, payload: dict):
    """Process a region enter/exit count event."""
    rname = payload.get("region_name") or region_name(payload.get("region_id",""))
    ts    = payload.get("timestamp", "")
    relt  = self._ts_str(ts)

    # showcase_light is a scene-wide environmental sensor region — skip
    if rname in ("showcase_light", "ShowcaseLight"):
      return

    # Filter to objects currently visible in at least one camera.
    # Objects with no cameras are Scenescape ghost tracks (known bug) — skip them.
    def _visible(o):
      return bool(o.get("cameras"))

    entered = [o for o in payload.get("entered", []) if _visible(o)]
    exited  = [o for o in payload.get("exited",  [])
               if _visible(o if "category" in o else o.get("object", o))]

    if not entered and not exited:
      return  # no transitions (or all ghosts) — skip

    lines = [f"[event {relt}]  region '{rname}'"]

    for obj in entered:
      cat     = obj.get("category", "object")
      tr      = obj.get("translation", [])
      pos     = self._pos_str(tr[0], tr[1]) if len(tr) >= 2 else ""
      cam_str = self._cam_str_for(obj.get("id", ""))
      if cat == "person":
        label = self._person_label(obj.get("id", ""))
        cred  = self._cred_annot(obj.get("sensors", {}))
        lines.append(f"  entered: {label}{cred}{pos}{cam_str}")
      elif cat == "luggage":
        lines.append(f"  entered: {self._luggage_label(obj.get('id', ''))}{pos}{cam_str}")
      else:
        lines.append(f"  entered: {cat}{pos}{cam_str}")

    for item in exited:
      obj     = item if "category" in item else item.get("object", item)
      dwell   = item.get("dwell", 0) if "dwell" in item else 0
      cat     = obj.get("category", "object")
      tr      = obj.get("translation", [])
      pos     = self._pos_str(tr[0], tr[1]) if len(tr) >= 2 else ""
      cam_str = self._cam_str_for(obj.get("id", ""))
      if cat == "person":
        label = self._person_label(obj.get("id", ""))
        cred  = self._cred_annot(obj.get("sensors", {}))
        lines.append(f"  exited: {label}{cred}{pos}{cam_str}  dwell={dwell:.1f}s")
      elif cat == "luggage":
        lines.append(f"  exited: {self._luggage_label(obj.get('id', ''))}{pos}{cam_str}  dwell={dwell:.1f}s")
      else:
        lines.append(f"  exited: {cat}{pos}{cam_str}  dwell={dwell:.1f}s")

    # Credential value for sensor regions (badge/faceid)
    cred_val = payload.get("value")
    if cred_val:
      lines.append(f"  credential value: {cred_val}")

    self._emit("\n".join(lines))

  # ── Window access ─────────────────────────────────────────────────────────────

  def window_text(self) -> str:
    with self._lock:
      return "\n\n".join(self._window)

  def window_len(self) -> int:
    with self._lock:
      return len(self._window)

  # ── Background snapshot thread ────────────────────────────────────────────────

  def start(self):
    def _loop():
      while True:
        time.sleep(self._interval)
        try:
          self.tick()
        except Exception:
          logger.exception("Narrator tick error")
    threading.Thread(target=_loop, daemon=True).start()
    logger.info(f"Narrator started (snapshot every {self._interval}s)")


# ── MQTT subscriber extension ──────────────────────────────────────────────────

class NarratorSubscriber(TrackSubscriber):
  """Extends TrackSubscriber to also feed tripwire/region events to a Narrator."""

  def __init__(self, cache: TrackCache, narrator: Narrator, **kwargs):
    self._narrator = narrator
    super().__init__(cache, **kwargs)

  def _on_connect(self, client, userdata, flags, rc):
    super()._on_connect(client, userdata, flags, rc)
    # Add event topics
    client.subscribe(f"scenescape/event/tripwire/{SCENE_ID}/+/objects")
    client.subscribe(f"scenescape/event/region/{SCENE_ID}/+/count")
    logger.info("Subscribed: tripwire + region event topics")

  def _on_message(self, client, userdata, msg):
    try:
      payload = json.loads(msg.payload.decode())
    except Exception:
      return

    topic = msg.topic
    try:
      if "/event/tripwire/" in topic:
        self._narrator.on_tripwire(payload)
      elif "/event/region/" in topic:
        self._narrator.on_region_event(payload)
      else:
        super()._on_message(client, userdata, msg)
        if topic == REG_TOPIC:
          self._narrator.on_regulated(payload)
    except Exception:
      # A single malformed message must never kill the ingest thread, which
      # would silently freeze the dashboard (no tracks/alerts).
      logger.exception("Failed to process message on %s", topic)


# ── Standalone entry point ─────────────────────────────────────────────────────

def main():
  p = argparse.ArgumentParser(description="Scene narrator — rolling text window")
  p.add_argument("--broker",       default="broker.scenescape.intel.com")
  p.add_argument("--port",         type=int, default=1883)
  p.add_argument("--ca-cert",      default="/run/secrets/certs/scenescape-ca.pem")
  p.add_argument("--tls-insecure", action="store_true")
  p.add_argument("--broker-auth",  default="/run/secrets/controller.auth")
  p.add_argument("--interval",     type=int, default=SNAPSHOT_INTERVAL_S)
  p.add_argument("--print-window", action="store_true",
                 help="Print full window after each snapshot")
  p.add_argument("--verbose",      action="store_true")
  args = p.parse_args()

  logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
  )

  cache    = TrackCache()
  narrator = Narrator(cache, snapshot_interval=args.interval)
  narrator.start()

  sub = NarratorSubscriber(
    cache, narrator,
    broker_host=args.broker,
    broker_port=args.port,
    ca_cert=args.ca_cert,
    tls_insecure=args.tls_insecure,
    broker_auth=args.broker_auth,
  )

  def _watchdog():
    while True:
      time.sleep(args.interval)
      print(f"── window entries={narrator.window_len()}", flush=True)
      if args.print_window:
        print("\n" + "═"*70)
        print(narrator.window_text())
        print("═"*70 + "\n", flush=True)

  threading.Thread(target=_watchdog, daemon=True).start()
  sub.run_forever()


if __name__ == "__main__":
  main()
