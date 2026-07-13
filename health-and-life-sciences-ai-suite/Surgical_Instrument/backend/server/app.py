"""Real Flask server for the Surgical Instrument backend.

Replaces ``backend_mvp/mock_server.py``. Wire shape identical to the mock so
the existing Redux UI works unmodified — the only differences are that the
lifecycle drives a real :class:`Orchestrator` FSM (weights → dataset → train →
export → ready) and frames come from a real DL Streamer pipeline running in
the ``surgical-pipeline`` container. This backend is a *consumer* of that
pipeline: it POSTs /start /stop to the pipeline HTTP control plane, subscribes
to the ``surgical/detections`` MQTT topic for per-frame metadata, tails the
GStreamer ``latency_tracer`` log for infer + total latency, and reads annotated
JPEGs from the shared ``/frames`` volume. See :mod:`backend.consumer`.

Emitted shapes (unchanged from mock):
  GET  /api/health           -> {status, build_sha, uptime_s}
  GET  /api/readiness        -> {lifecycle, ready, checks, errors, last_error}
  GET  /api/status           -> {lifecycle, device, bootstrap, inference}
  POST /api/start            -> {status, message}
  POST /api/stop             -> {status, message}
  GET  /api/events           -> SSE named events 'full' and 'delta'
  GET  /api/frame/latest     -> ?base64=1 -> {available, data}; else JPEG
  GET  /api/video_feed       -> multipart/x-mixed-replace MJPEG
  GET  /api/hardware-metrics -> {cpu_utilization, gpu_utilization, memory,
                                 power, npu_utilization}
  GET  /api/platform-info    -> {Processor, NPU, iGPU, Memory, Storage, OS}
  GET  /api/config           -> {video_file, default_video, devices, ...}

Lifecycle mapping (FSM state -> UI lifecycle):
  initializing / checking_cache / downloading_* / training / exporting -> 'initializing'
  ready (no inference)  -> 'ready'
  ready (worker running) -> 'running' (with 'starting' / 'stopping' transitions)
  error -> 'error'
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import queue
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

from flask import Flask, Response, jsonify, request
from PIL import Image, ImageDraw, ImageFont

from ..bootstrap.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Global server state
# ---------------------------------------------------------------------------

LIFECYCLE_RUN = {"starting", "running"}
BOUNDARY = "frame"


@dataclass
class ServerState:
    lifecycle: str = "initializing"           # UI-facing lifecycle
    instance_id: Optional[str] = None
    device: str = "GPU"
    # Selected pipeline input source. `source_kind` is one of file|v4l2|basler,
    # `source_arg` is the path/device/serial. Both None → pipeline uses its own
    # SOURCE_KIND/SOURCE_ARG env defaults (backward-compat with pre-slice-B UI).
    source_kind: Optional[str] = None
    source_arg: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    # SSE fan-out (each subscriber gets its own queue)
    subscribers: list["queue.Queue[tuple[str, dict[str, Any]]]"] = field(default_factory=list)

    lock: threading.Lock = field(default_factory=threading.Lock)

    # Rolling hardware-metrics buffers (last ~60 samples = ~4 min at 4 Hz)
    cpu_hist: deque = field(default_factory=lambda: deque(maxlen=60))
    gpu_hist: deque = field(default_factory=lambda: deque(maxlen=60))
    npu_hist: deque = field(default_factory=lambda: deque(maxlen=60))
    mem_hist: deque = field(default_factory=lambda: deque(maxlen=60))
    pwr_hist: deque = field(default_factory=lambda: deque(maxlen=60))


STATE = ServerState()
_orch: Optional[Orchestrator] = None
_worker = None  # type: Optional[Any]  # InferenceWorker — lazy import
_cfg: Optional[dict] = None

# Frozen snapshot of the last session — populated on Stop, cleared on Start,
# so the UI keeps showing the final frame + session KPIs after the user stops.
_last_stats: Optional[dict] = None
_last_dets: Optional[dict] = None
_last_frame_jpeg: Optional[bytes] = None


VALID_DEVICES = {"CPU", "GPU", "NPU"}


# ---------------------------------------------------------------------------
# Publish helpers
# ---------------------------------------------------------------------------

def _publish(event: str, payload: dict[str, Any]) -> None:
    with STATE.lock:
        dead: list[queue.Queue] = []
        for q in STATE.subscribers:
            try:
                q.put_nowait((event, payload))
            except queue.Full:
                dead.append(q)
        for q in dead:
            STATE.subscribers.remove(q)


def _set_lifecycle(new: str, *, publish: bool = True) -> None:
    with STATE.lock:
        STATE.lifecycle = new
    if publish:
        _publish("full", _snapshot_full())


def _map_fsm_to_lifecycle(fsm_state: str, worker_running: bool) -> str:
    if fsm_state == "error":
        return "error"
    if fsm_state == "ready":
        return "running" if worker_running else "ready"
    # Any other FSM state is bootstrap in progress
    return "initializing"


def _snapshot_full() -> dict[str, Any]:
    boot = _orch.state_snapshot() if _orch else {"state": "initializing"}
    # Live worker wins; frozen last-session stats used when worker is None.
    if _worker is not None:
        inf = _worker.stats()
    elif _last_stats is not None:
        inf = _last_stats
    else:
        inf = {
            "running": False, "delivered_fps": 0.0,
            "infer_mean_ms": 0.0, "infer_p99_ms": 0.0,
            "total_mean_ms": 0.0, "total_p99_ms": 0.0,
            "frame_id": 0, "uptime_s": 0.0,
            "cumulative_detections": 0, "frames_with_detection": 0, "detection_rate": 0.0,
            "peak_confidence": 0.0, "distinct_polyps": 0,
        }

    if _worker is not None:
        dets = _worker.latest_detections()
        detections = dets.get("detections", [])
        n_polyp = sum(1 for d in detections if str(d.get("class_name", "")).lower() == "polyp")
        conf = max((float(d.get("confidence", 0.0)) for d in detections), default=0.0)
    else:
        # Post-stop: no live detection. Session totals still come from _last_stats.
        n_polyp = 0
        conf = 0.0
    fps = float(inf.get("delivered_fps", 0.0))
    e2e_mean = float(inf.get("e2e_mean_ms", inf.get("total_mean_ms", 0.0)))
    e2e_p99 = float(inf.get("e2e_p99_ms", inf.get("total_p99_ms", 0.0)))
    proc_mean = float(inf.get("processing_mean_ms", 0.0))
    proc_p99 = float(inf.get("processing_p99_ms", 0.0))
    infer_ms = float(inf.get("infer_mean_ms", 0.0))
    infer_p99 = float(inf.get("infer_p99_ms", 0.0))

    cfg = _cfg or {}
    model_cfg = cfg.get("model", {}) or {}
    ds_cfg = cfg.get("dataset", {}) or {}
    pipe_cfg = cfg.get("pipeline", {}) or {}
    infer_size = int(pipe_cfg.get("infer_size", 640))
    out_w, out_h = tuple(pipe_cfg.get("output_size", (1920, 1080)))

    return {
        "lifecycle": STATE.lifecycle,
        "bootstrap": boot,
        "analytics": {
            "polyp_detection": {
                "detected": n_polyp > 0,
                "count": n_polyp,
                "confidence": round(conf, 3),
                "distinct_polyps": int(inf.get("distinct_polyps", 0)),
                "frames_processed": int(inf.get("frame_id", 0)),
                "frames_with_detection": int(inf.get("frames_with_detection", 0)),
                "detection_rate": round(float(inf.get("detection_rate", 0.0)), 4),
                "peak_confidence": round(float(inf.get("peak_confidence", 0.0)), 3),
                "session_seconds": round(float(inf.get("uptime_s", 0.0)), 1),
            },
        },
        "metrics": {
            "fps": round(fps, 2),
            "loop_count": int(inf.get("frame_id", 0)),
            "uptime_s": round(float(inf.get("uptime_s", 0.0)), 1),
            "infer_mean_ms": round(infer_ms, 2),
            "infer_p99_ms": round(infer_p99, 2),
            "processing_mean_ms": round(proc_mean, 2),
            "processing_p99_ms": round(proc_p99, 2),
            "e2e_mean_ms": round(e2e_mean, 2),
            "e2e_p99_ms": round(e2e_p99, 2),
            # Legacy aliases — same values as e2e_*.
            "total_mean_ms": round(e2e_mean, 2),
            "total_p99_ms": round(e2e_p99, 2),
        },
        "frame": (
            (_worker is not None and _worker.latest_frame_jpeg() is not None)
            or _last_frame_jpeg is not None
        ),
        "pipeline_performance": {
            "workloads": [{
                "name": "Polyp Detection",
                "device": STATE.device,
                "status": "running" if STATE.lifecycle in LIFECYCLE_RUN else "stopped",
                "fps": round(fps, 2),
                "infer_ms": round(infer_ms, 2),
                "infer_p99_ms": round(infer_p99, 2),
                "processing_mean_ms": round(proc_mean, 2),
                "processing_p99_ms": round(proc_p99, 2),
                "e2e_mean_ms": round(e2e_mean, 2),
                "e2e_p99_ms": round(e2e_p99, 2),
                # Legacy keys the current UI may still read.
                "latency_ms": round(e2e_mean, 2),
                "latency_p99_ms": round(e2e_p99, 2),
            }],
            "pipeline_fps": round(fps, 2),
            "decode": f"{out_w}x{out_h} H.264",
        },
        "model_info": {
            "name": model_cfg.get("name", "yolo11n"),
            "precision": "FP16 OpenVINO IR",
            "task": "Polyp Detection",
            "dataset": ds_cfg.get("name", "CVC-ColonDB"),
            "input_source": f"{out_h}p H.264 (looped)",
            "model_input": f"{infer_size}x{infer_size}",
            "device": STATE.device,
        },
    }


# ---------------------------------------------------------------------------
# Orchestrator wiring — bootstrap on server boot
# ---------------------------------------------------------------------------

def _on_orch_event(event: dict) -> None:
    """Called by Orchestrator on every state change; publishes SSE + updates lifecycle."""
    new_state = event.get("state")
    if new_state:
        worker_running = bool(_worker and _worker.is_running())
        new_life = _map_fsm_to_lifecycle(new_state, worker_running)
        with STATE.lock:
            if new_state == "error":
                STATE.error = event.get("error") or event.get("message")
            if STATE.lifecycle != new_life:
                STATE.lifecycle = new_life
    _publish("full", _snapshot_full())


def _start_bootstrap(config_path: Path) -> Orchestrator:
    global _orch
    _orch = Orchestrator(config_path, progress=_on_orch_event)
    _orch.run_async()
    return _orch


# ---------------------------------------------------------------------------
# Delta broadcaster + hardware metrics sampler
# ---------------------------------------------------------------------------

def _sample_hardware(t: float) -> tuple[float, float, float, float, float]:
    """Return (cpu%, gpu%, npu%, mem%, power W) — synthetic for now."""
    running = STATE.lifecycle == "running"
    if running:
        cpu = max(0.0, min(100.0, 32.0 + 24.0 * math.sin(t * 0.4) + random.uniform(-3, 3)))
        gpu = max(0.0, min(100.0, 68.0 + 20.0 * math.sin(t * 0.45) + random.uniform(-4, 4)))
        npu = max(0.0, min(100.0, 6.0 + 4.0 * abs(math.sin(t * 0.6))))
        mem_pct = max(0.0, min(100.0, 25.0 + 6.0 * abs(math.sin(t * 0.15))))
        pwr = 30.0 + 8.0 * math.sin(t * 0.3)
    else:
        cpu = 8.0 + 4.0 * abs(math.sin(t * 0.25))
        gpu = 4.0 + 3.0 * abs(math.sin(t * 0.6))
        npu = 0.0
        mem_pct = 20.0
        pwr = 18.0
    return cpu, gpu, npu, mem_pct, pwr


def _delta_loop(stop_event: threading.Event) -> None:
    t = 0.0
    while not stop_event.is_set():
        ts_iso = datetime.now().isoformat(timespec="seconds")
        cpu, gpu, npu, mem_pct, pwr = _sample_hardware(t)
        STATE.cpu_hist.append([ts_iso, round(cpu, 1)])
        STATE.gpu_hist.append([ts_iso, round(gpu, 1)])
        STATE.npu_hist.append([ts_iso, round(npu, 1)])
        STATE.mem_hist.append([ts_iso, round(32 * mem_pct / 100, 2), 32.0, 0.0, round(mem_pct, 1)])
        STATE.pwr_hist.append([ts_iso, round(pwr, 1)])

        if STATE.lifecycle == "running":
            _publish("delta", _snapshot_full())

        t += 0.25
        stop_event.wait(0.25)


# ---------------------------------------------------------------------------
# Frame delivery — real InferenceWorker JPEG, with placeholder fallback
# ---------------------------------------------------------------------------

_PLACEHOLDER_W, _PLACEHOLDER_H = 960, 540


def _placeholder_jpeg(message: str) -> bytes:
    img = Image.new("RGB", (_PLACEHOLDER_W, _PLACEHOLDER_H), color=(12, 16, 22))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((16, 16), "Surgical Instrument backend", fill=(180, 200, 220), font=font)
    d.text((16, 40), f"lifecycle: {STATE.lifecycle}", fill=(180, 200, 220), font=font)
    d.text((16, 64), message, fill=(255, 217, 168), font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _current_jpeg() -> bytes:
    if _worker is not None:
        jpeg = _worker.latest_frame_jpeg()
        if jpeg:
            return jpeg
    # Post-stop: keep showing the last real frame so the video panel doesn't blank.
    if _last_frame_jpeg is not None and STATE.lifecycle in ("ready", "stopping"):
        return _last_frame_jpeg
    if STATE.lifecycle == "initializing":
        boot_msg = ""
        if _orch is not None:
            snap = _orch.state_snapshot()
            boot_msg = f"{snap.get('state','')} — {snap.get('message','')}"
        return _placeholder_jpeg(boot_msg or "bootstrap in progress...")
    if STATE.lifecycle == "error":
        return _placeholder_jpeg(STATE.error or "error")
    return _placeholder_jpeg("press Start to begin inference")


def _mjpeg_stream() -> Generator[bytes, None, None]:
    while True:
        jpeg = _current_jpeg()
        yield (
            b"--" + BOUNDARY.encode() + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
            + jpeg + b"\r\n"
        )
        # Deliver at ~30 fps when running, slower otherwise to save CPU.
        time.sleep(0.033 if STATE.lifecycle == "running" else 0.25)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
API = "/api"


@app.get(f"{API}/health")
def health() -> Response:
    return jsonify({
        "status": "healthy",
        "build_sha": os.environ.get("BUILD_SHA", "dev"),
        "uptime_s": int(time.time() - STATE.started_at),
    })


@app.get(f"{API}/readiness")
def readiness() -> Response:
    boot = _orch.state_snapshot() if _orch else {"state": "initializing", "error": None}
    fsm = boot.get("state", "initializing")
    ready = fsm == "ready"
    return jsonify({
        "lifecycle": STATE.lifecycle,
        "ready": ready,
        "checks": {
            "bootstrap": ready,
            "pipeline": _worker is not None,
        },
        "errors": [boot["error"]] if boot.get("error") else [],
        "last_error": boot.get("error"),
    })


@app.get(f"{API}/status")
def status() -> Response:
    boot = _orch.state_snapshot() if _orch else {"state": "initializing"}
    # Live worker wins; when stopped, fall through to the last-session
    # snapshot frozen by /stop so the UI keeps rendering the final KPIs
    # (fps, latency, detection totals) instead of blanking to zero.
    # `_last_stats` is cleared on /start (fresh session) and /reset.
    inf = _worker.stats() if _worker else _last_stats
    return jsonify({
        "lifecycle": STATE.lifecycle,
        "device": STATE.device,
        "bootstrap": boot,
        "inference": inf,
    })


@app.post(f"{API}/start")
def start() -> Response:
    if STATE.lifecycle in LIFECYCLE_RUN:
        return jsonify({"lifecycle": STATE.lifecycle, "error": "already running"}), 409

    boot = _orch.state_snapshot() if _orch else {"state": "initializing"}
    if boot.get("state") != "ready":
        return jsonify({
            "status": "not_ready",
            "message": f"bootstrap not complete (state={boot.get('state')})",
            "bootstrap": boot,
        }), 409

    # Optional per-request overrides. Persist to STATE so a subsequent Start
    # (with no body) still uses the last user choice.
    body = request.get_json(silent=True) or {}
    dev = body.get("device")
    if isinstance(dev, str) and dev.upper() in VALID_DEVICES:
        STATE.device = dev.upper()
    src = body.get("source")
    if isinstance(src, dict):
        kind = src.get("kind")
        arg  = src.get("arg")
        if kind in ("file", "v4l2", "basler") and isinstance(arg, str) and arg:
            STATE.source_kind = kind
            STATE.source_arg  = arg

    STATE.instance_id = f"srv-{int(time.time())}"
    _set_lifecycle("starting")
    threading.Thread(target=_do_start, name="inference-start", daemon=True).start()
    return jsonify({"status": "starting", "message": "inference starting"})


def _do_start() -> None:
    global _worker, _last_stats, _last_dets, _last_frame_jpeg
    assert _cfg is not None
    try:
        from ..consumer import InferenceConsumer

        # Fresh session — clear any frozen snapshot from the previous run.
        _last_stats = None
        _last_dets = None
        _last_frame_jpeg = None

        # STATE.device is the authoritative runtime choice (POST /api/device);
        # falls back to the config value at first boot via create_app().
        device = (STATE.device or _cfg.get("pipeline", {}).get("device", "GPU"))
        _worker = InferenceConsumer(
            device=device,
            source_kind=STATE.source_kind,
            source_arg=STATE.source_arg,
        )
        _worker.start()
        # Wait briefly for the pipeline container to produce the first
        # annotated frame; then mark running.
        for _ in range(100):
            if _worker.latest_frame_jpeg() is not None:
                break
            time.sleep(0.1)
        _set_lifecycle("running")
    except Exception as exc:  # noqa: BLE001
        with STATE.lock:
            STATE.error = f"{type(exc).__name__}: {exc}"
        _set_lifecycle("error")


@app.post(f"{API}/stop")
def stop() -> Response:
    global _worker
    _set_lifecycle("stopping")

    def _do_stop() -> None:
        global _worker, _last_stats, _last_dets, _last_frame_jpeg
        if _worker is not None:
            # Freeze the last session so the UI keeps showing final KPIs + frame.
            try:
                _last_stats = _worker.stats()
                _last_dets = _worker.latest_detections()
                _last_frame_jpeg = _worker.latest_frame_jpeg()
            except Exception:  # noqa: BLE001
                pass
            _worker.stop(timeout=5.0)
            _worker = None
        _set_lifecycle("ready")

    threading.Thread(target=_do_stop, name="inference-stop", daemon=True).start()
    return jsonify({"status": "stopping", "message": "inference stopping"})


@app.post(f"{API}/reset")
def reset() -> Response:
    """Clear frozen post-stop state (frame + KPIs + error).

    Called after Stop when the user wants a fresh slate — e.g. before
    changing the inference device and pressing Start again. Rejected while
    inference is running (Stop first).
    """
    global _last_stats, _last_dets, _last_frame_jpeg
    if STATE.lifecycle in LIFECYCLE_RUN:
        return jsonify({
            "error": "cannot reset while running — stop inference first",
            "lifecycle": STATE.lifecycle,
        }), 409
    _last_stats = None
    _last_dets = None
    _last_frame_jpeg = None
    with STATE.lock:
        STATE.error = None
        if STATE.lifecycle == "error":
            STATE.lifecycle = "ready"
    _publish("full", _snapshot_full())
    return jsonify({"status": "ok", "lifecycle": STATE.lifecycle})


@app.post(f"{API}/device")
def set_device() -> Response:
    """Change inference device (CPU/GPU/NPU). Rejects if inference is running."""
    if STATE.lifecycle in LIFECYCLE_RUN:
        return jsonify({
            "error": "cannot change device while running — stop inference first",
            "lifecycle": STATE.lifecycle,
            "device": STATE.device,
        }), 409

    body = request.get_json(silent=True) or {}
    dev = str(body.get("device", "")).upper().strip()
    if dev not in VALID_DEVICES:
        return jsonify({
            "error": f"invalid device {dev!r}; want one of {sorted(VALID_DEVICES)}",
            "device": STATE.device,
        }), 400

    with STATE.lock:
        STATE.device = dev
    _publish("full", _snapshot_full())
    return jsonify({"status": "ok", "device": STATE.device})


@app.get(f"{API}/events")
def events() -> Response:
    q: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue(maxsize=64)
    with STATE.lock:
        STATE.subscribers.append(q)
    q.put_nowait(("full", _snapshot_full()))

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


@app.get(f"{API}/frame/latest")
def frame_latest() -> Response:
    jpeg = _current_jpeg()
    if request.args.get("base64"):
        # "available" mirrors _current_jpeg's real output: live worker frame OR
        # the frozen last-session frame. Without this the UI treats every
        # post-Stop poll as a miss and shows a stale-overlay spinner.
        available = (
            (_worker is not None and _worker.latest_frame_jpeg() is not None)
            or _last_frame_jpeg is not None
        )
        return jsonify({
            "available": available,
            "data": base64.b64encode(jpeg).decode("ascii"),
        })
    return Response(jpeg, mimetype="image/jpeg")


@app.get(f"{API}/video_feed")
def video_feed() -> Response:
    return Response(_mjpeg_stream(), mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY}")


@app.get(f"{API}/hardware-metrics")
def hardware_metrics() -> Response:
    return jsonify({
        "cpu_utilization": list(STATE.cpu_hist),
        "gpu_utilization": list(STATE.gpu_hist),
        "npu_utilization": list(STATE.npu_hist),
        "memory":          list(STATE.mem_hist),
        "power":           list(STATE.pwr_hist),
    })


# ---------------------------------------------------------------------------
# Platform detection — runtime-derived from host /proc + /sys (which containers
# share with the host kernel), so the same image reports MTL on MTL and PTL on
# PTL without any config knobs.
# ---------------------------------------------------------------------------

# Known Intel PCI device IDs we want to give a friendly name to.
# Anything not in the table falls back to "Intel <class> [8086:xxxx]".
_INTEL_GPU_NAMES: dict[str, str] = {
    "7d55": "Intel Arc Graphics (Meteor Lake-P, Xe-LPG)",
    "7d67": "Intel Arc Graphics (Meteor Lake-U, Xe-LPG)",
    "7d40": "Intel Arc Graphics (Meteor Lake, Xe-LPG)",
    "7d45": "Intel Arc Graphics (Meteor Lake, Xe-LPG)",
    "b0a0": "Intel Xe3 Graphics (Panther Lake)",
    "b080": "Intel Xe3 Graphics (Panther Lake)",
    "64a0": "Intel Arc Graphics (Lunar Lake, Xe2)",
    "7d51": "Intel Arc Graphics (Arrow Lake, Xe-LPG+)",
}

_INTEL_NPU_NAMES: dict[str, str] = {
    "7d1d": "Intel AI Boost NPU (Meteor Lake, NPU 3720)",
    "643e": "Intel AI Boost NPU (Arrow Lake, NPU 3720)",
    "7d1e": "Intel AI Boost NPU (Lunar Lake, NPU 4.0)",
    "b01d": "Intel AI Boost NPU (Panther Lake, NPU 4.0)",
}


def _read_first_line(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.readline().strip()
    except OSError:
        return ""


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown CPU"


def _mem_total_gib() -> str:
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return f"{kb / (1024 * 1024):.1f} GiB"
    except (OSError, ValueError, IndexError):
        pass
    return "unknown"


def _os_pretty() -> str:
    # Prefer host os-release if the compose file bind-mounts it; fall back
    # to the container OS (still useful — tells the operator what image
    # they're on) plus the host kernel version, which containers share.
    for candidate in ("/host_etc/os-release", "/etc/os-release"):
        try:
            with open(candidate, "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            continue
    return "unknown"


def _host_kernel() -> str:
    return _read_first_line("/proc/sys/kernel/osrelease") or "unknown"


def _detect_intel_devices() -> tuple[str, str]:
    """Return (iGPU, NPU) friendly names from /sys/bus/pci/devices."""
    igpu = "not detected"
    npu = "not detected"
    root = "/sys/bus/pci/devices"
    try:
        entries = os.listdir(root)
    except OSError:
        return igpu, npu
    for dev in sorted(entries):
        base = f"{root}/{dev}"
        vendor = _read_first_line(f"{base}/vendor").lower()
        if vendor != "0x8086":
            continue
        did = _read_first_line(f"{base}/device").lower().replace("0x", "")
        klass = _read_first_line(f"{base}/class").lower()
        # class 0x030000 == VGA, 0x038000 == other display
        is_gpu = klass.startswith("0x0300") or klass.startswith("0x0380") or did in _INTEL_GPU_NAMES
        # class 0x120000 == Processing accelerator, 0x118000 == Signal-processing
        is_npu = klass.startswith("0x1200") or klass.startswith("0x1180") or did in _INTEL_NPU_NAMES
        if is_gpu and igpu == "not detected":
            igpu = _INTEL_GPU_NAMES.get(did, f"Intel iGPU [8086:{did}]")
        elif is_npu and npu == "not detected":
            # Prefer a name-table hit — some PCH IDs (e.g. 0xb03e) share
            # class 0x1200 with the NPU but aren't the NPU.
            if did in _INTEL_NPU_NAMES:
                npu = _INTEL_NPU_NAMES[did]
            elif npu == "not detected":
                # Only fall back to a generic label if we haven't already
                # matched a known NPU on this bus.
                npu = f"Intel NPU [8086:{did}]"
    return igpu, npu


@app.get(f"{API}/platform-info")
def platform_info() -> Response:
    igpu, npu = _detect_intel_devices()
    os_line = _os_pretty()
    kernel = _host_kernel()
    return jsonify({
        "Processor": _cpu_model(),
        "NPU":       npu,
        "iGPU":      igpu,
        "Memory":    _mem_total_gib(),
        "OS":        f"{os_line} (kernel {kernel})" if kernel != "unknown" else os_line,
    })


@app.get(f"{API}/devices/cameras")
def devices_cameras() -> Response:
    v4l2: list[dict] = []
    try:
        for entry in sorted(os.listdir("/sys/class/video4linux")):
            name_path = f"/sys/class/video4linux/{entry}/name"
            try:
                with open(name_path, "r") as f:
                    name = f.read().strip()
            except OSError:
                name = entry
            v4l2.append({"device": f"/dev/{entry}", "name": name, "node": entry})
    except FileNotFoundError:
        pass

    basler: list[dict] = []
    basler_note: str | None = None
    try:
        from pypylon import pylon  # type: ignore
        for d in pylon.TlFactory.GetInstance().EnumerateDevices():
            basler.append({
                "serial": d.GetSerialNumber(),
                "model":  d.GetModelName(),
                "vendor": d.GetVendorName(),
            })
    except ImportError:
        basler_note = "pypylon not installed in backend image (ships in slice E)"
    except Exception as e:
        basler_note = f"pylon enumerate failed: {e}"

    resp: dict = {"v4l2": v4l2, "basler": basler}
    if basler_note:
        resp["basler_note"] = basler_note
    return jsonify(resp)


# ---------------------------------------------------------------------------
# Videos — list + upload
# ---------------------------------------------------------------------------

VIDEO_EXTS      = {".mp4", ".mkv", ".avi", ".mov", ".ts"}
MAX_UPLOAD_MB   = 500
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _videos_dir() -> str:
    """Container path where mp4s live. Mounted from ./videos on the host."""
    return os.environ.get("VIDEOS_DIR", "/videos")


@app.get(f"{API}/videos")
def list_videos() -> Response:
    """Enumerate video files available to the pipeline.

    Returns a plain list of {name, size_bytes, mtime}. `name` is the basename
    only — the pipeline path is always `{VIDEOS_DIR}/{name}`.
    """
    d = _videos_dir()
    out: list[dict] = []
    try:
        for entry in sorted(os.listdir(d)):
            path = os.path.join(d, entry)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(entry)[1].lower()
            if ext not in VIDEO_EXTS:
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            out.append({
                "name": entry,
                "size_bytes": st.st_size,
                "mtime": int(st.st_mtime),
            })
    except FileNotFoundError:
        pass
    return jsonify({"videos": out, "dir": d, "max_upload_mb": MAX_UPLOAD_MB})


@app.post(f"{API}/videos")
def upload_video() -> Response:
    """Accept a multipart upload; save to VIDEOS_DIR under a sanitised name.

    Rejects non-video extensions and files larger than MAX_UPLOAD_MB. Refuses
    to overwrite an existing file (client should DELETE + re-POST if that's
    the intent — no delete endpoint today, so effectively immutable).
    """
    if "file" not in request.files:
        return jsonify({"error": "no file part (expected multipart field 'file')"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    # Sanitise: basename only, keep extension check strict.
    name = os.path.basename(f.filename).replace("\\", "_")
    ext  = os.path.splitext(name)[1].lower()
    if ext not in VIDEO_EXTS:
        return jsonify({
            "error": f"unsupported extension {ext!r}; expected one of {sorted(VIDEO_EXTS)}",
        }), 415

    d = _videos_dir()
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as exc:
        return jsonify({"error": f"videos dir not writable: {exc}"}), 500

    dest = os.path.join(d, name)
    if os.path.exists(dest):
        return jsonify({"error": f"file already exists: {name}"}), 409

    # Stream to disk in chunks; enforce size cap without loading fully in memory.
    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = f.stream.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    os.remove(dest)
                    return jsonify({
                        "error": f"file exceeds {MAX_UPLOAD_MB} MB limit",
                    }), 413
                out.write(chunk)
    except OSError as exc:
        try:
            os.remove(dest)
        except OSError:
            pass
        return jsonify({"error": f"write failed: {exc}"}), 500

    return jsonify({"name": name, "size_bytes": written, "path": dest}), 201


@app.get(f"{API}/config")
def config() -> Response:
    if _cfg is None:
        return jsonify({}), 503
    p = _cfg.get("pipeline", {})
    # STATE.source_arg (set by POST /api/start body or POST /api/source) takes
    # precedence over the config default so the UI reflects the user's last
    # choice across a stop/start cycle.
    default_video = p.get("default_video", "videos/polyp_test.mp4")
    selected = STATE.source_arg if STATE.source_kind == "file" else None
    return jsonify({
        "video_file": selected,
        "default_video": default_video,
        "source": {
            "kind": STATE.source_kind or "file",
            "arg":  STATE.source_arg  or default_video,
        },
        "devices": {"detect": STATE.device},
        "model": {
            "name": _cfg["model"]["name"],
            "ir_dir": _cfg["model"]["ir_dir"],
        },
        "pending": False,
        "fallback": None,
    })


@app.get("/health")
def health_alias() -> Response:
    return health()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def create_app(config_path: str | Path) -> Flask:
    """Wire orchestrator + background threads; return the Flask app."""
    global _cfg
    from ..bootstrap.config import load_config

    _cfg = load_config(config_path)
    # Seed the runtime device from config so /api/device reflects the compose-time choice.
    cfg_device = str((_cfg.get("pipeline", {}) or {}).get("device", "GPU")).upper()
    if cfg_device in VALID_DEVICES:
        STATE.device = cfg_device

    _start_bootstrap(Path(config_path))

    stop_event = threading.Event()
    t = threading.Thread(target=_delta_loop, args=(stop_event,), daemon=True)
    t.start()
    # Stash on app for graceful shutdown in tests.
    app.config["_delta_stop"] = stop_event
    return app


def main() -> None:
    config_path = os.environ.get("BACKEND_CONFIG", "backend/config/model.yaml")
    port = int(os.environ.get("PORT", "5001"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[server] booting with config={config_path} host={host} port={port}")
    create_app(config_path)
    app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
