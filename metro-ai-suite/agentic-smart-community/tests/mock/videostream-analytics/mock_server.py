#!/usr/bin/env python3
"""Mock videostream-analytics service.

Implements both:
  1. The videostream-analytics RESTful API (source lifecycle management)
  2. A background thread that sends real webhook events to MCP server using
     actual video clips from data/motion_events/

RESTful API endpoints (in-memory state, no persistence):
  POST /register_source
  DELETE /sources/{id}
  GET  /sources
  GET  /sources/{id}/status
  POST /sources/{id}/pause
  POST /sources/{id}/resume
  POST /sources/{id}/keepalive  (TODO: analytics-side)

Usage:
  python mock_server.py [options]

Options:
  --port          Listen port for RESTful API (default: 8999)
  --events-url    MCP server webhook URL (default: http://localhost:3101/events)
  --data-dir      Root dir containing per-camera motion_events (default: data/motion_events)
  --interval      Seconds between webhook events per camera (default: 60)
  --monitor       Camera IDs to simulate, space-separated (default: all found under data-dir)

Camera strategies:
  cam_fridge          : no prefilter fields in payload
  cam_child           : prefilter with *_input.mp4 crop; ~20% of events have passed=0
  cam_elder_bedroom   : prefilter (no crop); ~20% passed=0
  cam_elder_bedroom_2 : same as cam_elder_bedroom
"""

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# In-memory source registry
# ---------------------------------------------------------------------------

class SourceRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._sources: Dict[str, dict] = {}

    def register(self, source_id: str, data: dict) -> None:
        with self._lock:
            self._sources[source_id] = {**data, "status": "running", "source_id": source_id}

    def delete(self, source_id: str) -> bool:
        with self._lock:
            if source_id in self._sources:
                del self._sources[source_id]
                return True
            return False

    def get(self, source_id: str) -> Optional[dict]:
        with self._lock:
            return self._sources.get(source_id)

    def list_all(self) -> List[dict]:
        with self._lock:
            return list(self._sources.values())

    def set_status(self, source_id: str, status: str) -> bool:
        with self._lock:
            if source_id in self._sources:
                self._sources[source_id]["status"] = status
                return True
            return False

    def is_running(self, source_id: str) -> bool:
        with self._lock:
            src = self._sources.get(source_id)
            return src is not None and src.get("status") == "running"


registry = SourceRegistry()


# ---------------------------------------------------------------------------
# HTTP server (RESTful API)
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access log

    def _respond(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw)

    def do_GET(self):
        if self.path == "/sources":
            self._respond(200, registry.list_all())
        elif self.path.startswith("/sources/") and self.path.endswith("/status"):
            source_id = self.path.split("/")[2]
            src = registry.get(source_id)
            if src:
                self._respond(200, src)
            else:
                self._respond(404, {"error": f"source {source_id} not found"})
        elif self.path == "/health":
            self._respond(200, {"status": "healthy"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/register_source":
            body = self._read_body()
            source_id = body.get("source_id")
            if not source_id:
                self._respond(400, {"error": "source_id required"})
                return
            registry.register(source_id, body)
            print(f"  [analytics] registered source: {source_id}")
            self._respond(200, {"status": "ok", "source_id": source_id})
        elif self.path.startswith("/sources/") and self.path.endswith("/pause"):
            source_id = self.path.split("/")[2]
            if registry.set_status(source_id, "paused"):
                print(f"  [analytics] paused source: {source_id}")
                self._respond(200, {"status": "paused"})
            else:
                self._respond(404, {"error": f"source {source_id} not found"})
        elif self.path.startswith("/sources/") and self.path.endswith("/resume"):
            source_id = self.path.split("/")[2]
            if registry.set_status(source_id, "running"):
                print(f"  [analytics] resumed source: {source_id}")
                self._respond(200, {"status": "running"})
            else:
                self._respond(404, {"error": f"source {source_id} not found"})
        elif self.path.startswith("/sources/") and self.path.endswith("/keepalive"):
            source_id = self.path.split("/")[2]
            if registry.get(source_id):
                self._respond(200, {"status": "ok"})
            else:
                self._respond(404, {"error": f"source {source_id} not found"})
        else:
            self._respond(404, {"error": "not found"})

    def do_DELETE(self):
        if self.path.startswith("/sources/"):
            source_id = self.path.split("/")[2]
            if registry.delete(source_id):
                print(f"  [analytics] deleted source: {source_id}")
                self._respond(200, {"status": "deleted"})
            else:
                self._respond(404, {"error": f"source {source_id} not found"})
        else:
            self._respond(404, {"error": "not found"})


# ---------------------------------------------------------------------------
# Video clip discovery
# ---------------------------------------------------------------------------

def discover_clips(data_dir: Path, monitor_id: str) -> List[Path]:
    """Return sorted list of original (non-_input) mp4 files under <data_dir>/<monitor_id>/."""
    cam_dir = data_dir / monitor_id
    if not cam_dir.exists():
        return []
    return sorted(f for f in cam_dir.rglob("*.mp4") if not f.name.endswith("_input.mp4"))


def find_crop(clip: Path) -> Optional[Path]:
    """Return the corresponding *_input.mp4 crop file if it exists."""
    stem = clip.stem
    crop = clip.parent / f"{stem}_input.mp4"
    return crop if crop.exists() else None


# ---------------------------------------------------------------------------
# Webhook sender
# ---------------------------------------------------------------------------

PREFILTER_CAMERAS = {"cam_child", "cam_elder_bedroom", "cam_elder_bedroom_2"}
PREFILTER_FAIL_RATE = 0.2  # ~20% of events have prefilter_passed=0


def hardlink_into(target_root: Path, monitor_id: str, src: Path) -> Path:
    """Hardlink src into <target_root>/<monitor_id>/<YYYY-MM-DD>/<filename>; idempotent."""
    day = datetime.now().strftime("%Y-%m-%d")
    dst_dir = target_root / monitor_id / day
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if not dst.exists():
        os.link(src, dst)
    return dst


def send_webhook(events_url: str, target_root: Path, monitor_id: str, clip: Path, index: int, total: int) -> bool:
    """Send a motion event webhook to MCP server."""
    has_prefilter = monitor_id in PREFILTER_CAMERAS
    prefilter_passed = 1
    if has_prefilter and random.random() < PREFILTER_FAIL_RATE:
        prefilter_passed = 0

    # Hardlink the source clip (and crop, if present) into the SmartBuilding convention
    # layout so multilevel-video-understanding's bind-mount (host data dir → /data) can
    # see them after MCP server's path_remap. Hardlinks share the inode — no copy, no
    # symlink container-boundary issues.
    linked_clip = hardlink_into(target_root, monitor_id, clip)
    crop = find_crop(clip)
    linked_crop = hardlink_into(target_root, monitor_id, crop) if crop else None
    summary_clip_input = str(linked_crop or linked_clip)

    now = datetime.now().isoformat()
    payload: dict = {
        "event_file_path": str(linked_clip),
        "summary_clip_input": summary_clip_input,
        "start_time": now,
        "end_time": now,
        "duration_seconds": 15.0,
    }
    if has_prefilter:
        payload["prefilter_passed"] = prefilter_passed
        payload["prefilter_classes"] = '["person"]'
        payload["prefilter_confidence"] = 0.9
        payload["trajectory_region"] = "50,50,300,400"

    event = {
        "sourceId": monitor_id,
        "type": "motion",
        "timestamp": now,
        "payload": payload,
    }

    try:
        data = json.dumps(event).encode()
        req = urllib.request.Request(
            events_url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_icon = "✓" if prefilter_passed else "✗(prefilter)"
            print(f"  [{monitor_id}] event {index+1}/{total} → {status_icon} {clip.name} "
                  f"(HTTP {resp.status})", flush=True)
            return resp.status == 200
    except Exception as e:
        print(f"  [{monitor_id}] event {index+1}/{total} → failed: {e}", flush=True)
        return False


# ---------------------------------------------------------------------------
# Per-monitor event sender thread
# ---------------------------------------------------------------------------

class MonitorEventSender(threading.Thread):
    def __init__(self, monitor_id: str, data_dir: Path, target_root: Path, events_url: str, interval: float):
        super().__init__(daemon=True)
        self.monitor_id = monitor_id
        self.data_dir = data_dir
        self.target_root = target_root
        self.events_url = events_url
        self.interval = interval
        self._stop = threading.Event()

    def run(self):
        clips = discover_clips(self.data_dir, self.monitor_id)
        if not clips:
            print(f"  [{self.monitor_id}] no clips found under {self.data_dir / self.monitor_id}, skipping", flush=True)
            return

        total = len(clips)
        print(f"  [{self.monitor_id}] {total} clips found, sending every {self.interval}s", flush=True)
        idx = 0
        warned_waiting = False
        while not self._stop.is_set():
            if registry.is_running(self.monitor_id):
                if warned_waiting:
                    print(f"  [{self.monitor_id}] now registered as running, starting webhook sends", flush=True)
                    warned_waiting = False
                send_webhook(self.events_url, self.target_root, self.monitor_id, clips[idx % total], idx, total)
                idx += 1
            else:
                if not warned_waiting:
                    print(f"  [{self.monitor_id}] waiting for source to be registered (POST /register_source)…", flush=True)
                    warned_waiting = True
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Mock videostream-analytics service")
    parser.add_argument("--port", type=int, default=8999)
    parser.add_argument("--events-url", default="http://localhost:3101/events")
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parents[3] / "data" / "motion_events"),
        help="Root directory containing per-monitor clip fixtures: looks for "
             "<data-dir>/<monitor_id>/motion_events/*.mp4, then <data-dir>/<monitor_id>/*.mp4. "
             "Default: repo's data/motion_events.",
    )
    parser.add_argument(
        "--target-root",
        default=str(Path.home() / ".mcp-smartbuilding" / "segments" / "mock"),
        help="Where to hardlink emitted clips. Convention: $SMARTBUILDING_DATA_DIR/segments/mock. "
             "Per-event layout is <target-root>/<monitor_id>/<YYYY-MM-DD>/<clip>.mp4.",
    )
    parser.add_argument("--interval", type=float, default=60.0,
                        help="Seconds between webhook events per camera (default: 60)")
    parser.add_argument("--monitor", nargs="*", dest="monitors",
                        help="Camera IDs to simulate (default: all found under data-dir)")
    parser.add_argument("--auto-register", action="store_true", default=True,
                        help="Auto-register listed monitors as running on startup (so standalone runs send "
                             "webhooks without waiting for MCP server's POST /register_source). Default: on.")
    parser.add_argument("--no-auto-register", action="store_false", dest="auto_register",
                        help="Disable auto-register; only send when MCP server registers the source first.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: data-dir {data_dir} does not exist", file=sys.stderr)
        sys.exit(1)
    target_root = Path(args.target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    # Discover monitors
    if args.monitors:
        monitors = args.monitors
    else:
        monitors = sorted(d.name for d in data_dir.iterdir() if d.is_dir())

    print("╔════════════════════════════════════════════╗")
    print("║  Mock videostream-analytics                ║")
    print("╚════════════════════════════════════════════╝")
    print(f"  API port:    {args.port}")
    print(f"  Events URL:  {args.events_url}")
    print(f"  Data dir:    {data_dir}")
    print(f"  Target root: {target_root}  (hardlinks)")
    print(f"  Interval:    {args.interval}s")
    print(f"  Monitors:    {', '.join(monitors)}")
    print()

    # Auto-register so standalone runs (no MCP server in the loop) don't sit idle waiting
    # for POST /register_source. Disable with --no-auto-register to exercise the real flow.
    if args.auto_register:
        for monitor_id in monitors:
            registry.register(monitor_id, {"auto_registered": True})
        print(f"  Auto-registered as running: {', '.join(monitors)}")

    # Start per-monitor event senders
    senders = []
    for monitor_id in monitors:
        sender = MonitorEventSender(monitor_id, data_dir, target_root, args.events_url, args.interval)
        sender.start()
        senders.append(sender)

    # Start HTTP server
    httpd = HTTPServer(("", args.port), Handler)
    print(f"  REST API listening on http://localhost:{args.port}")
    print("  (Ctrl+C to stop)\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        for s in senders:
            s.stop()


if __name__ == "__main__":
    main()
