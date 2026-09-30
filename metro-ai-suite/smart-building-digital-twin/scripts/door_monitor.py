#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Door state monitor — simple open/closed inference for Showcase scene.

Three rules:
  DoubleDoorEntry – count-based: 2 doors detected → CLOSED, fewer than 2 for DEBOUNCE_FRAMES → OPEN
  SideDoorEntry   – displacement-based: door near learned resting position → CLOSED,
                    door displaced from baseline or temporarily missing while people occupy the region → OPEN
  ConferenceDoor  – presence: any door detected → CLOSED (normally open/undetected)
"""

import argparse
import json
import logging
import math
import ssl
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from scene_config import SCENE_ID, REGION_NAMES

logger = logging.getLogger(__name__)

# Derive region UUIDs by name so they stay correct after re-import.
_region_by_name = {v: k for k, v in REGION_NAMES.items()}
REGION_DOUBLE = _region_by_name["DoubleDoorEntry"]
REGION_SIDE   = _region_by_name["SideDoorEntry"]
REGION_CONF   = _region_by_name["ConferenceDoor"]

DEBOUNCE_FRAMES    = 5    # consecutive sub-2-door frames before DoubleDoor → OPEN
N_BASELINE         = 30   # door detections to average for SideDoor baseline
SIDE_DOOR_OPEN_OFFSET_M = 0.25  # door displaced from baseline by this much → OPEN


def _dist2d(a, b):
  return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


class DoorMonitor:
  def __init__(self, broker_host, broker_port, ca_cert, tls_insecure, broker_auth):
    self._broker_host = broker_host
    self._broker_port = broker_port
    self._lock = threading.Lock()

    # DoubleDoorEntry
    self._double_state  = "unknown"
    self._double_absent = 0
    self._double_count  = 0

    # SideDoorEntry — baseline learned from first N detections
    self._side_state    = "unknown"
    self._side_samples  = []    # [[x, y], ...] collected during learning
    self._side_baseline = None  # [x, y] learned resting position of door
    self._side_doors    = []    # [[x, y], ...] currently visible door positions in region
    self._side_persons  = []    # [[x, y], ...] of people currently in region

    # ConferenceDoor (normally open — initialize to open so no spurious alert on startup)
    self._conf_state = "open"

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

  def _on_connect(self, client, userdata, flags, rc):
    logger.info(f"Connected (rc={rc})")
    subs = [
      f"scenescape/data/region/{SCENE_ID}/{REGION_DOUBLE}/door",
      f"scenescape/data/region/{SCENE_ID}/{REGION_SIDE}/door",
      f"scenescape/data/region/{SCENE_ID}/{REGION_SIDE}/person",
      f"scenescape/data/region/{SCENE_ID}/{REGION_CONF}/door",
    ]
    for t in subs:
      client.subscribe(t)
    logger.info(f"Subscribed to {len(subs)} topics")

  def _on_message(self, client, userdata, msg):
    try:
      payload = json.loads(msg.payload.decode())
    except Exception:
      return
    parts    = msg.topic.split("/")
    region   = parts[4]
    category = parts[5]
    objects  = payload.get("objects", [])

    with self._lock:
      if region == REGION_DOUBLE and category == "door":
        self._update_double(objects)

      elif region == REGION_SIDE and category == "person":
        self._side_persons = [o["translation"][:2] for o in objects if "translation" in o]
        self._infer_side()

      elif region == REGION_SIDE and category == "door":
        self._side_doors = [o["translation"][:2] for o in objects if "translation" in o]
        self._learn_side_baseline(objects)
        self._infer_side()

      elif region == REGION_CONF and category == "door":
        self._set("ConferenceDoor", "_conf_state", "closed" if objects else "open")

  # ── DoubleDoorEntry ──────────────────────────────────────────────────────────
  def _update_double(self, objects):
    self._double_count  = len(objects)
    self._double_absent = (self._double_absent + 1) if self._double_count < 2 else 0
    state = "open" if self._double_absent >= DEBOUNCE_FRAMES else "closed"
    self._set("DoubleDoorEntry", "_double_state", state)

  # ── SideDoorEntry – baseline learning ───────────────────────────────────────
  def _learn_side_baseline(self, objects):
    if objects and self._side_baseline is None:
      xy = objects[0]["translation"][:2]
      self._side_samples.append(xy)
      if len(self._side_samples) >= N_BASELINE:
        xs = [p[0] for p in self._side_samples]
        ys = [p[1] for p in self._side_samples]
        self._side_baseline = [sum(xs) / len(xs), sum(ys) / len(ys)]
        logger.info(
          f"[SideDoorEntry] baseline learned: "
          f"({self._side_baseline[0]:.3f}, {self._side_baseline[1]:.3f})"
        )

  # ── SideDoorEntry – inference ────────────────────────────────────────────────
  def _infer_side(self):
    if self._side_baseline is None:
      return  # still collecting baseline samples
    if self._side_doors:
      displaced = any(
        _dist2d(p, self._side_baseline) >= SIDE_DOOR_OPEN_OFFSET_M
        for p in self._side_doors
      )
      self._set("SideDoorEntry", "_side_state", "open" if displaced else "closed")
      return
    self._set("SideDoorEntry", "_side_state", "open" if self._side_persons else "closed")

  # ── State transition + alerting ──────────────────────────────────────────────
  def _set(self, name, attr, new_state):
    if getattr(self, attr) == new_state:
      return
    setattr(self, attr, new_state)
    ts  = time.strftime("%H:%M:%S")
    tag = "⚠ " if new_state == "open" else "✓ "
    lvl = "WARN" if new_state == "open" else "INFO"
    print(f"{ts} [{lvl}] {tag}{name}: {new_state.upper()}", flush=True)

  # ── Periodic status line ─────────────────────────────────────────────────────
  def _watchdog(self):
    while True:
      time.sleep(10)
      with self._lock:
        bl = (
          f"({self._side_baseline[0]:.2f},{self._side_baseline[1]:.2f})"
          if self._side_baseline else "learning"
        )
        near = (
          len(self._side_persons)
          if self._side_baseline else 0
        )
        print(
          f"── Status ── "
          f"Double={self._double_state}(n={self._double_count}) "
          f"Side={self._side_state}(baseline={bl},people={near},doors={len(self._side_doors)}) "
          f"Conference={self._conf_state}",
          flush=True,
        )

  def run(self):
    threading.Thread(target=self._watchdog, daemon=True).start()
    logger.info("Connecting...")
    self.client.connect(self._broker_host, self._broker_port, 60)
    self.client.loop_forever()


def main():
  p = argparse.ArgumentParser(description="Door state monitor — Showcase scene")
  p.add_argument("--broker", default="broker.scenescape.intel.com")
  p.add_argument("--port", type=int, default=1883)
  p.add_argument("--ca-cert", default="/run/secrets/certs/scenescape-ca.pem")
  p.add_argument("--tls-insecure", action="store_true")
  p.add_argument("--broker-auth", default="/run/secrets/controller.auth")
  p.add_argument("--verbose", action="store_true")
  args = p.parse_args()

  logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
  )

  DoorMonitor(
    broker_host=args.broker,
    broker_port=args.port,
    ca_cert=args.ca_cert,
    tls_insecure=args.tls_insecure,
    broker_auth=args.broker_auth,
  ).run()


if __name__ == "__main__":
  main()
