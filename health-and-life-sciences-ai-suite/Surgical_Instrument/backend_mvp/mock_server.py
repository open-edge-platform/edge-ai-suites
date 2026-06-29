"""Mock backend for offline UI development and CI smoke.

Surface matches the production backend (Phase 3) so the UI is byte-for-byte
identical against either. Emits SSE `status` + `metrics` events, serves a
synthesized MJPEG so the video panel exercises its real <img> path.

Run:
    cd Surgical_Instrument
    python -m venv .venv && . .venv/bin/activate
    pip install -r backend_mvp/requirements-mock.txt
    python -m backend_mvp.mock_server

Then in another terminal:
    cd ui && npm run dev
    # → http://localhost:5173 (Vite proxies to 127.0.0.1:5001)
"""

from __future__ import annotations

import io
import json
import math
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Generator, Iterable

from flask import Flask, Response, jsonify, request
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Lifecycle state
# ---------------------------------------------------------------------------

LIFECYCLE_TRANSITIONS = {
    "UNKNOWN":      "READY",
    "INITIALIZING": "READY",
    "PREPARING":    "READY",
    "READY":        "READY",
    "STARTING":     "RUNNING",
    "RUNNING":      "RUNNING",
    "STOPPING":     "READY",
    "ERROR":        "READY",
}


@dataclass
class MockState:
    lifecycle: str = "READY"
    message: str = "mock backend"
    instance_id: str | None = None
    device: str = "GPU"
    source: str = "file"
    threshold: float = 0.5

    # Pub-sub for SSE: each subscriber gets its own queue.
    subscribers: list["queue.Queue[tuple[str, dict[str, Any]]]"] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: float = field(default_factory=time.time)

    def snapshot(self) -> dict[str, Any]:
        return {
            "lifecycle": self.lifecycle,
            "message": self.message,
            "pipeline_instance_id": self.instance_id,
            "device": self.device,
            "source": self.source,
            "threshold": self.threshold,
        }


STATE = MockState()


def publish(event: str, payload: dict[str, Any]) -> None:
    with STATE.lock:
        dead: list[queue.Queue] = []
        for q in STATE.subscribers:
            try:
                q.put_nowait((event, payload))
            except queue.Full:
                dead.append(q)
        for q in dead:
            STATE.subscribers.remove(q)


def set_lifecycle(new: str, message: str = "") -> None:
    with STATE.lock:
        STATE.lifecycle = new
        if message:
            STATE.message = message
    publish("status", STATE.snapshot())


# ---------------------------------------------------------------------------
# Synthetic metrics generator
# ---------------------------------------------------------------------------


def metrics_loop(stop_event: threading.Event) -> None:
    t = 0.0
    frames = 0
    detections = 0
    while not stop_event.is_set():
        running = STATE.lifecycle == "RUNNING"
        if running:
            frames += 6  # ~24 fps with 250 ms tick
            if int(t * 4) % 6 == 0:
                detections += 1

        # Pipeline KPIs: sinusoidal around credible POC numbers.
        fps           = 24.0 + 4.0 * math.sin(t * 0.4) if running else 0.0
        p50           = 9.5  + 1.5 * math.sin(t * 0.7) if running else 0.0
        p95           = 13.0 + 2.0 * math.sin(t * 0.5) if running else 0.0
        p99           = 14.0 + 2.5 * math.sin(t * 0.3) if running else 0.0
        late_pct      = max(0.0, 0.4 + 0.3 * math.sin(t * 0.2)) if running else 0.0
        confidence    = 0.55 + 0.30 * abs(math.sin(t * 0.6)) if running else 0.0

        cpu = 12.0 + 18.0 * abs(math.sin(t * 0.25)) + (35.0 if running else 0.0)
        gpu = 70.0 + 20.0 * math.sin(t * 0.45) if running else 5.0 + 3.0 * abs(math.sin(t * 0.6))
        npu = 0.0
        mem_total = 32.0
        mem_used  = 6.5 + 1.5 * abs(math.sin(t * 0.15))

        publish("metrics", {
            "pipeline": {
                "fps": round(fps, 1),
                "latencyP50Ms": round(p50, 2),
                "latencyP95Ms": round(p95, 2),
                "latencyP99Ms": round(p99, 2),
                "lateFramePct": round(late_pct, 2),
                "framesProcessed": frames,
                "detectionCount": detections,
                "lastConfidence": round(confidence, 2),
            },
            "system": {
                "cpuPct": round(max(0.0, min(100.0, cpu)), 1),
                "gpuPct": round(max(0.0, min(100.0, gpu)), 1),
                "npuPct": round(npu, 1),
                "memUsedGib": round(mem_used, 2),
                "memTotalGib": round(mem_total, 2),
            },
        })
        t += 0.25
        stop_event.wait(0.25)


# ---------------------------------------------------------------------------
# Synthetic MJPEG stream
# ---------------------------------------------------------------------------

W, H = 960, 540
BOUNDARY = "frame"


def _font() -> ImageFont.ImageFont:
    # PIL's default font is bitmap-only and always available.
    return ImageFont.load_default()


def _render_frame(idx: int) -> bytes:
    img = Image.new("RGB", (W, H), color=(8, 12, 20))
    d = ImageDraw.Draw(img)
    # Moving horizon bar
    y = int(H * 0.5 + 80 * math.sin(idx * 0.06))
    d.rectangle([(0, y - 2), (W, y + 2)], fill=(0, 104, 181))
    # Bounding-box analogue
    bx = int(W * 0.5 + 100 * math.sin(idx * 0.08))
    by = int(H * 0.5 + 60  * math.cos(idx * 0.08))
    d.rectangle([(bx - 60, by - 40), (bx + 60, by + 40)], outline=(0, 200, 120), width=3)
    d.text((bx - 56, by - 60), "polyp 0.82", fill=(0, 200, 120), font=_font())
    # HUD
    hud = f"MOCK FRAME {idx:05d}  state={STATE.lifecycle}"
    d.text((12, 12), hud, fill=(180, 200, 220), font=_font())
    d.text((12, H - 24), "NOT FOR CLINICAL USE", fill=(255, 217, 168), font=_font())

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72)
    return buf.getvalue()


def mjpeg_stream() -> Generator[bytes, None, None]:
    idx = 0
    while True:
        running = STATE.lifecycle == "RUNNING"
        frame = _render_frame(idx if running else 0)
        idx += 1 if running else 0
        yield (
            b"--" + BOUNDARY.encode() + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
            + frame + b"\r\n"
        )
        time.sleep(0.040 if running else 0.5)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.get("/health")
def health() -> Response:
    return jsonify({
        "status": "ok",
        "build_sha": os.environ.get("BUILD_SHA", "dev-mock"),
        "uptime_s": int(time.time() - STATE.started_at),
    })


@app.get("/readiness")
def readiness() -> Response:
    return jsonify({"ready": True})


@app.get("/status")
def status() -> Response:
    return jsonify(STATE.snapshot())


@app.post("/start")
def start() -> Response:
    body = request.get_json(silent=True) or {}
    with STATE.lock:
        STATE.device    = body.get("device", STATE.device)
        STATE.source    = body.get("source", STATE.source)
        STATE.threshold = float(body.get("threshold", STATE.threshold))
        STATE.instance_id = f"mock-{int(time.time())}"
    set_lifecycle("STARTING", "transitioning to RUNNING")
    # Simulate async start
    threading.Timer(0.6, lambda: set_lifecycle("RUNNING", "pipeline ticking")).start()
    return jsonify({"ok": True, "instance_id": STATE.instance_id})


@app.post("/stop")
def stop() -> Response:
    set_lifecycle("STOPPING", "stopping pipeline")
    threading.Timer(0.4, lambda: set_lifecycle("READY", "idle")).start()
    return jsonify({"ok": True})


@app.get("/events")
def events() -> Response:
    q: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue(maxsize=64)
    with STATE.lock:
        STATE.subscribers.append(q)
    # Seed with current status so late subscribers don't see a blank UI.
    q.put_nowait(("status", STATE.snapshot()))

    def stream() -> Iterable[bytes]:
        try:
            while True:
                try:
                    event, payload = q.get(timeout=15)
                except queue.Empty:
                    yield b": keep-alive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()
        finally:
            with STATE.lock:
                if q in STATE.subscribers:
                    STATE.subscribers.remove(q)

    return Response(stream(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/video/stream")
def video_stream() -> Response:
    return Response(
        mjpeg_stream(),
        mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )


@app.get("/frame/latest")
def frame_latest() -> Response:
    idx = int(time.time() * 10) % 100000
    return Response(_render_frame(idx), mimetype="image/jpeg")


# Surgical-internal metrics passthrough so UI does not 404 when polling.
@app.get("/api/metrics/system")
def metrics_system() -> Response:
    # Last-published values are kept in the SSE generator; for HTTP we
    # synthesize a single point so the endpoint shape is honoured.
    return jsonify({"cpuPct": 0, "gpuPct": 0, "npuPct": 0, "memUsedGib": 0, "memTotalGib": 0})


def main() -> None:
    port = int(os.environ.get("PORT", "5001"))
    stop_event = threading.Event()
    t = threading.Thread(target=metrics_loop, args=(stop_event,), daemon=True)
    t.start()
    try:
        # threaded=True so SSE + MJPEG + REST all coexist on dev server.
        app.run(host="0.0.0.0", port=port, threaded=True, debug=False, use_reloader=False)
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
