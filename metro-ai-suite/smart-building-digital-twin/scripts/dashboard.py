#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Dashboard — FastAPI server wiring narrator output into a web UI.

Endpoints:
  GET  /                → index.html
  GET  /stream/narrator → SSE: {text: str} per narrator entry

Run standalone (outside Docker):
  python3 scripts/dashboard.py \
    --broker "$BROKER_HOST" --port 1883 \
    --ca-cert certs/scenescape-ca.pem --tls-insecure \
    --broker-auth certs/controller.auth

Inside Docker: configure via environment variables (see ENV block below).
"""

import argparse
import asyncio
import json
import logging
import os
import re
import socket
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).parent))
from system_telemetry import SystemTelemetry
from track_cache import TrackCache
from narrator import Narrator, NarratorSubscriber
from snapshots import SnapshotClient, parse_cameras_from_alert

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# ── Runtime config (env vars with CLI override) ──────────────────────────────────
_cfg: dict = {}   # filled in main() or from env defaults


def _cfg_get(key: str, default: str) -> str:
  return _cfg.get(key) or os.environ.get(key, default)


def _default_listen_host() -> str:
  env_host = os.environ.get("DASHBOARD_BIND_HOST")
  if env_host:
    return env_host
  return "0.0.0.0"


# ── SSE subscriber queues ────────────────────────────────────────────────────────
_narrator_subs:    list[asyncio.Queue] = []
_scene_state_subs: list[asyncio.Queue] = []
_event_loop:    asyncio.AbstractEventLoop | None = None
_snapshotter:   SnapshotClient | None = None
_stolen_candidate_images: dict[str, dict[str, str]] = {}
_stolen_candidate_lock = threading.Lock()

_STOLEN_ALERT_RE = re.compile(
  r"luggage stolen: (?P<luggage>luggage-\w+).*?companion changed from (?P<old>person-\w+).*?→ (?P<new>person-\w+)",
  re.DOTALL,
)


def _stolen_alert_key(alert_text: str) -> str | None:
  match = _STOLEN_ALERT_RE.search(alert_text)
  if not match:
    return None
  return f"{match.group('luggage')}|{match.group('old')}|{match.group('new')}"


def _push(subs: list[asyncio.Queue], data: dict) -> None:
  """Thread-safe push to all SSE subscriber queues."""
  loop = _event_loop
  if loop is None:
    return
  for q in list(subs):
    loop.call_soon_threadsafe(q.put_nowait, data)


# ── Lifespan ─────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
  global _event_loop, _snapshotter

  _event_loop = asyncio.get_running_loop()

  broker_host = _cfg_get("BROKER_HOST", "broker.scenescape.intel.com")
  broker_port = int(_cfg_get("BROKER_PORT", "1883"))
  ca_cert     = _cfg_get("CA_CERT",     "/run/secrets/certs/scenescape-ca.pem")
  broker_auth = _cfg_get("BROKER_AUTH", "/run/secrets/controller.auth")
  interval    = float(_cfg_get("SNAPSHOT_INTERVAL", "10"))

  # Known cameras — in order so thumbnails display consistently
  camera_ids  = [f"cam-{i}" for i in range(1, 8)]

  cache    = TrackCache()
  narrator = Narrator(cache, snapshot_interval=interval)
  telemetry = SystemTelemetry()

  def _on_narrator_entry(entry: str) -> None:
    _push(_narrator_subs, {"text": entry})

  narrator.add_listener(_on_narrator_entry)
  narrator.start()

  sub = NarratorSubscriber(
    cache, narrator,
    broker_host=broker_host,
    broker_port=broker_port,
    ca_cert=ca_cert,
    tls_insecure=True,
    broker_auth=broker_auth,
  )
  sub.start()
  logger.info(f"MQTT connected to {broker_host}:{broker_port}")

  # Snapshot client — dedicated MQTT connection for getimage requests
  _snapshotter = SnapshotClient(
    all_camera_ids=camera_ids,
    broker_host=broker_host,
    broker_port=broker_port,
    ca_cert=ca_cert,
    tls_insecure=True,
    broker_auth=broker_auth,
    timeout_s=3.0,
  )

  # On every alert, capture snapshots then push text+images together
  def _on_alert(alert_entry: str) -> None:
    def _capture_and_push():
      cam_ids = parse_cameras_from_alert(alert_entry) or None
      images = _snapshotter.capture(cam_ids) if _snapshotter else {}
      stolen_key = _stolen_alert_key(alert_entry)
      if stolen_key:
        with _stolen_candidate_lock:
          handoff_images = _stolen_candidate_images.pop(stolen_key, {})
        if handoff_images or images:
          combined_images = {
            **{f"handoff {cam_id}": src for cam_id, src in sorted(handoff_images.items())},
            **{f"alert {cam_id}": src for cam_id, src in sorted(images.items())},
          }
          images = combined_images
      _push(_narrator_subs, {"text": alert_entry, "images": images, "is_alert": True})
    threading.Thread(target=_capture_and_push, daemon=True).start()

  narrator.add_alert_listener(_on_alert)

  def _on_stolen_candidate(data: dict) -> None:
    def _capture_candidate():
      cam_ids = data.get("camera_ids") or None
      images = _snapshotter.capture(cam_ids) if _snapshotter else {}
      if not images:
        return
      key = data.get("key")
      if not key:
        return
      with _stolen_candidate_lock:
        _stolen_candidate_images[key] = images
        if len(_stolen_candidate_images) > 20:
          oldest_key = next(iter(_stolen_candidate_images))
          _stolen_candidate_images.pop(oldest_key, None)
    threading.Thread(target=_capture_candidate, daemon=True).start()

  narrator.add_stolen_candidate_listener(_on_stolen_candidate)

  def _on_scene_state(state: dict) -> None:
    state_with_telemetry = dict(state)
    state_with_telemetry["telemetry"] = telemetry.snapshot()
    _push(_scene_state_subs, state_with_telemetry)

  narrator.add_state_listener(_on_scene_state)
  logger.info("Dashboard ready")

  yield


app = FastAPI(lifespan=lifespan)


# ── Static ────────────────────────────────────────────────────────────────────────
@app.get("/")
async def index():
  return FileResponse(STATIC_DIR / "index.html")


# ── SSE ───────────────────────────────────────────────────────────────────────────
async def _sse_stream(subs: list[asyncio.Queue]):
  q: asyncio.Queue = asyncio.Queue()
  subs.append(q)
  try:
    while True:
      data = await q.get()
      yield f"data: {json.dumps(data)}\n\n"
  finally:
    try:
      subs.remove(q)
    except ValueError:
      pass


@app.get("/stream/narrator")
async def stream_narrator():
  return StreamingResponse(
    _sse_stream(_narrator_subs),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
  )


@app.get("/stream/scene-state")
async def stream_scene_state():
  return StreamingResponse(
    _sse_stream(_scene_state_subs),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
  )


# ── Entrypoint ────────────────────────────────────────────────────────────────────
def main():
  p = argparse.ArgumentParser(description="Smart Building Dashboard")
  p.add_argument("--broker",       default=None)
  p.add_argument("--port",         type=int, default=None)
  p.add_argument("--ca-cert",      default=None)
  p.add_argument("--tls-insecure", action="store_true")
  p.add_argument("--broker-auth",  default=None)
  p.add_argument("--interval",     type=int, default=None)
  p.add_argument("--listen-host",  default=None)
  p.add_argument("--listen-port",  type=int, default=7000)
  p.add_argument("--verbose",      action="store_true")
  args = p.parse_args()

  logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
  )

  if args.broker:      _cfg["BROKER_HOST"]      = args.broker
  if args.port:        _cfg["BROKER_PORT"]       = str(args.port)
  if args.ca_cert:     _cfg["CA_CERT"]           = args.ca_cert
  if args.broker_auth: _cfg["BROKER_AUTH"]       = args.broker_auth
  if args.interval:    _cfg["SNAPSHOT_INTERVAL"] = str(args.interval)

  listen_host = args.listen_host or _default_listen_host()
  uvicorn.run(app, host=listen_host, port=args.listen_port, log_level="info")


if __name__ == "__main__":
  main()
