"""Flask control plane for the finalized DL Streamer pipeline container.

Routes:

    GET  /health
    GET  /latency
    POST /start {"device":X, "source": {"kind": ..., "arg": ...}}
    POST /stop

The launched gst process writes latency tracer output to stderr. A local
collector parses those lines into rolling window percentiles exposed by
`GET /latency` for the backend/UI.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time

from flask import Flask, jsonify, request

from latency_tracer_sink import RollingLatency, pump_stream
from pipeline_string import VALID_DEVICES, VALID_SOURCE_KINDS, build

log = logging.getLogger("launcher")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# ------------------------------------------------------------ config -------
VIDEO       = os.environ["VIDEO"]
IR_XML      = os.environ["IR_XML"]
THRESHOLD   = float(os.environ.get("THRESHOLD", "0.5"))
TARGET_FPS  = int(os.environ.get("TARGET_FPS", "60"))
HTTP_PORT   = int(os.environ.get("PIPELINE_HTTP_PORT", "8000"))
DISPLAY_VIEW = os.environ.get("PIPELINE_DISPLAY_VIEW", "1") == "1"
VIDEO_SINK   = os.environ.get("PIPELINE_VIDEO_SINK", "autovideosink")
# 0 = unlimited (default for live demo). Set PIPELINE_FRAME_LIMIT=N to cap
# at N frames — useful for benchmarking runs that should auto-terminate.
FRAME_LIMIT  = int(os.environ.get("PIPELINE_FRAME_LIMIT", "0"))
# Source defaults. `SOURCE_KIND` = file|v4l2|basler. `SOURCE_ARG` is the
# path/device/serial. Both fall back to `VIDEO` (a file path) for
# backward compat with the pre-multi-source docker-compose.yaml.
SOURCE_KIND = os.environ.get("SOURCE_KIND", "file").lower()
SOURCE_ARG  = os.environ.get("SOURCE_ARG", VIDEO)
# If the pipeline restarts more than this many times within RESPAWN_WINDOW_S
# seconds we give up (protects against a config error that instant-crashes).
RESPAWN_MAX     = int(os.environ.get("RESPAWN_MAX", "6"))
RESPAWN_WINDOW  = float(os.environ.get("RESPAWN_WINDOW_S", "10"))

# ------------------------------------------------------------ state --------
_proc: subprocess.Popen | None = None
_proc_device: str | None = None
_proc_source_kind: str | None = None
_proc_source_arg: str | None = None
_proc_display_view: bool | None = None
_wanted_running: bool = False        # set True by /start, False by /stop
_supervisor: threading.Thread | None = None
_latency = RollingLatency()
_lock = threading.Lock()


def _reap_if_dead() -> None:
    """Clear _proc if the subprocess has exited."""
    global _proc, _proc_device
    if _proc is not None and _proc.poll() is not None:
        _proc = None


def _spawn(
    device: str,
    source_kind: str,
    source_arg: str,
    display_view: bool | None = None,
) -> subprocess.Popen:
    _latency.reset()
    use_display = DISPLAY_VIEW if display_view is None else display_view
    # FRAME_LIMIT defaults to 0 (unlimited). A file source plays to its own
    # natural EOS; a live Basler source runs until /stop or a genuine failure.
    # Set PIPELINE_FRAME_LIMIT env var to cap frames for benchmarking only.
    pipeline = build(
        source_kind=source_kind,
        source_arg=source_arg,
        ir_xml=IR_XML,
        device=device,
        threshold=THRESHOLD,
        target_fps=TARGET_FPS,
        frame_limit=FRAME_LIMIT,
        display_view=use_display,
        video_sink=VIDEO_SINK,
    )

    env = os.environ.copy()
    env.update(
        {
            "GST_TRACERS": "latency(flags=pipeline)",
            "GST_DEBUG": "GST_TRACER:7",
            "GST_DEBUG_NO_COLOR": "1",
        }
    )

    if source_kind == "basler":
        # Enumerate Basler cameras visible inside the container before spawning
        # so connectivity problems appear immediately in the logs.
        try:
            from pypylon import pylon as _pylon  # type: ignore
            _tl = _pylon.TlFactory.GetInstance()
            _devs = _tl.EnumerateDevices()
            _cam_list = [(d.GetSerialNumber(), d.GetModelName()) for d in _devs]
            log.info(
                "[basler] cameras visible in container: %s",
                _cam_list if _cam_list else "NONE",
            )
        except Exception as _exc:  # noqa: BLE001
            log.warning("[basler] pypylon enumeration failed: %s", _exc)
        cmd = (
            f"exec python3 /opt/basler_reader.py {source_arg} "
            f"--geometry 1920x1080@{TARGET_FPS} --pixel-format uyvy "
            f"| exec gst-launch-1.0 {pipeline}"
        )
    else:
        cmd = f"exec gst-launch-1.0 {pipeline}"

    log.info("[pipeline] generated cmd: %s", cmd)

    proc = subprocess.Popen(
        cmd,
        shell=True,
        env=env,
        start_new_session=True,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.stderr is not None:
        threading.Thread(
            target=pump_stream,
            args=(proc.stderr, _latency),
            kwargs={"log": log, "passthrough": sys.stderr},
            name="latency-tracer",
            daemon=True,
        ).start()
    return proc


def _supervisor_loop(device: str, source_kind: str, source_arg: str, display_view: bool) -> None:
    """Respawn gst-launch on EOS/exit while /start was the last user intent.

    A live Basler source can drop out transiently, so we relaunch it to keep
    the demo running. A file source is one-shot: once the clip reaches EOS the
    demo is complete and we deliberately do NOT respawn — respawning tore down
    the popup and launched a fresh gst-launch/ximagesink window every loop.
    """
    global _proc, _proc_device, _proc_source_kind, _proc_source_arg
    global _proc_display_view, _wanted_running
    restarts: list[float] = []
    while True:
        # Wait unlocked so /stop can grab the lock and kill us.
        p = _proc
        if p is None:
            break
        rc = p.wait()

        with _lock:
            if not _wanted_running:
                _proc = None
                log.info("supervisor: /stop honoured, exiting")
                return

            if source_kind == "file":
                # One-shot playback: the clip finished, so stop cleanly and
                # leave the pipeline idle instead of relaunching.
                log.info("supervisor: file source completed (rc=%s) — not respawning", rc)
                _proc = None
                _proc_device = None
                _proc_source_kind = None
                _proc_source_arg = None
                _proc_display_view = None
                _wanted_running = False
                return

            now = time.time()
            restarts = [t for t in restarts if now - t < RESPAWN_WINDOW]
            if len(restarts) >= RESPAWN_MAX:
                log.error(
                    "supervisor: %d restarts within %.1fs — giving up (rc=%s)",
                    len(restarts), RESPAWN_WINDOW, rc,
                )
                _proc = None
                return

            log.info("supervisor: pipeline exited rc=%s — respawning (loop)", rc)
            try:
                _proc = _spawn(device, source_kind, source_arg, display_view)
            except Exception as exc:  # noqa: BLE001
                log.exception("supervisor: respawn failed: %s", exc)
                _proc = None
                return
            restarts.append(now)


# ------------------------------------------------------------ app ----------
app = Flask(__name__)


@app.get("/health")
def health():
    with _lock:
        _reap_if_dead()
        return jsonify(
            status="running" if _proc else "idle",
            pid=_proc.pid if _proc else None,
            device=_proc_device,
            source_kind=_proc_source_kind,
            source_arg=_proc_source_arg,
            display_view=_proc_display_view,
            wanted_running=_wanted_running,
            latency=_latency.snapshot(),
        )


@app.get("/latency")
def latency():
    return jsonify(_latency.snapshot())


@app.post("/start")
def start():
    global _proc, _proc_device, _proc_source_kind, _proc_source_arg, _proc_display_view, _wanted_running, _supervisor
    body = request.get_json(silent=True) or {}
    device = str(body.get("device", "GPU")).upper()
    if device not in VALID_DEVICES:
        return jsonify(error=f"unsupported device: {device}"), 400

    # Source is optional on /start; falls back to env-derived default so
    # the existing UI (which only sends `device`) keeps working.
    src = body.get("source") or {}
    source_kind = str(src.get("kind", SOURCE_KIND)).lower()
    source_arg  = str(src.get("arg",  SOURCE_ARG))
    if source_kind not in VALID_SOURCE_KINDS:
        return jsonify(error=f"unsupported source_kind: {source_kind}"), 400

    with _lock:
        _reap_if_dead()
        if _proc is not None:
            return jsonify(error="pipeline already running", pid=_proc.pid), 409
        try:
            _proc = _spawn(device, source_kind, source_arg, DISPLAY_VIEW)
            _proc_display_view = DISPLAY_VIEW
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=f"spawn failed: {exc}"), 500
        _proc_device = device
        _proc_source_kind = source_kind
        _proc_source_arg = source_arg
        _wanted_running = True
        # Give gst-launch a moment to fail fast (missing IR, bad pipeline).
        time.sleep(0.3)
        if _proc.poll() is not None:
            rc = _proc.returncode
            # If display initialization fails (common in headless/RDP envs),
            # fall back to non-display mode so inference and metrics still run.
            if DISPLAY_VIEW:
                log.warning(
                    "pipeline exited immediately in display mode (rc=%s); retrying headless sink",
                    rc,
                )
                try:
                    _proc = _spawn(device, source_kind, source_arg, False)
                    _proc_display_view = False
                    time.sleep(0.3)
                except Exception as exc:  # noqa: BLE001
                    _proc = None
                    _proc_device = None
                    _proc_source_kind = None
                    _proc_source_arg = None
                    _proc_display_view = None
                    _wanted_running = False
                    return jsonify(error=f"headless fallback failed: {exc}"), 500

            if _proc is None or _proc.poll() is not None:
                rc2 = _proc.returncode if _proc is not None else rc
                _proc = None
                _proc_device = None
                _proc_source_kind = None
                _proc_source_arg = None
                _proc_display_view = None
                _wanted_running = False
                return jsonify(error=f"pipeline exited immediately (rc={rc2})"), 500

        # Supervisor lives across the /start /stop cycle and respawns
        # gst-launch on EOS so the demo loops indefinitely.
        _supervisor = threading.Thread(
            target=_supervisor_loop,
            args=(device, source_kind, source_arg, bool(_proc_display_view)),
            name="pipeline-supervisor", daemon=True,
        )
        _supervisor.start()
        return jsonify(
            status="running", pid=_proc.pid, device=device,
            source_kind=source_kind, source_arg=source_arg, display_view=_proc_display_view,
        ), 200


@app.post("/stop")
def stop():
    global _proc, _proc_device, _proc_source_kind, _proc_source_arg, _proc_display_view, _wanted_running
    with _lock:
        _wanted_running = False   # tell supervisor not to respawn
        _reap_if_dead()
        if _proc is None:
            return jsonify(status="idle"), 200
        pid = _proc.pid
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(50):  # up to 5 s
            if _proc.poll() is not None:
                break
            time.sleep(0.1)
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            _proc.wait(timeout=2)
        _proc = None
        _proc_device = None
        _proc_source_kind = None
        _proc_source_arg = None
        _proc_display_view = None
        return jsonify(status="stopped", pid=pid), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=HTTP_PORT, threaded=True)
