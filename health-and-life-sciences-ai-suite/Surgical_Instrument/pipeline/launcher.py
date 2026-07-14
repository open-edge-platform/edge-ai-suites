"""Flask control plane for the surgical DL Streamer pipeline container.

Exposes three routes:

    GET  /health              → {"status": "idle"|"running", "pid": int|null}
    POST /start {"device":X}  → spawn gst-launch-1.0 subprocess; 409 if running
    POST /stop                → SIGTERM subprocess, escalate to SIGKILL after 5s

The subprocess is launched with GST_TRACERS=latency_tracer;latency(...) so
canonical per-element and per-pipeline latency records land in
$FRAME_DIR/latency.log for the backend consumer to tail.

Auto-loop: a supervisor thread respawns gst-launch when it exits (typically
from EOS at the end of the mp4). Loop stops only when /stop is called or the
container shuts down — matches the "seek-to-0-on-EOF" loop the old OpenCV
InferenceWorker did with cv2.CAP_PROP_POS_FRAMES.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request

from pipeline_string import VALID_DEVICES, VALID_SOURCE_KINDS, build

log = logging.getLogger("launcher")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# ------------------------------------------------------------ config -------
VIDEO       = os.environ["VIDEO"]
IR_XML      = os.environ["IR_XML"]
THRESHOLD   = float(os.environ.get("THRESHOLD", "0.5"))
TARGET_FPS  = int(os.environ.get("TARGET_FPS", "60"))
MQTT_HOST   = os.environ.get("MQTT_HOST", "surgical-mqtt")
MQTT_TOPIC  = os.environ.get("MQTT_TOPIC", "surgical/detections")
FRAME_DIR   = Path(os.environ.get("FRAME_DIR", "/frames"))
HTTP_PORT   = int(os.environ.get("PIPELINE_HTTP_PORT", "8000"))
# Source defaults. `SOURCE_KIND` = file|v4l2|basler. `SOURCE_ARG` is the
# path/device/serial. Both fall back to `VIDEO` (a file path) for
# backward compat with the pre-multi-source docker-compose.yaml.
SOURCE_KIND = os.environ.get("SOURCE_KIND", "file").lower()
SOURCE_ARG  = os.environ.get("SOURCE_ARG", VIDEO)
# If the pipeline restarts more than this many times within RESPAWN_WINDOW_S
# seconds we give up (protects against a config error that instant-crashes).
RESPAWN_MAX     = int(os.environ.get("RESPAWN_MAX", "6"))
RESPAWN_WINDOW  = float(os.environ.get("RESPAWN_WINDOW_S", "10"))

FRAME_DIR.mkdir(parents=True, exist_ok=True)
LATENCY_LOG = FRAME_DIR / "latency.log"
FRAME_PATH  = FRAME_DIR / "latest.jpg"

# ------------------------------------------------------------ state --------
_proc: subprocess.Popen | None = None
_proc_device: str | None = None
_proc_source_kind: str | None = None
_proc_source_arg: str | None = None
_wanted_running: bool = False        # set True by /start, False by /stop
_supervisor: threading.Thread | None = None
_lock = threading.Lock()


def _reap_if_dead() -> None:
    """Clear _proc if the subprocess has exited."""
    global _proc, _proc_device
    if _proc is not None and _proc.poll() is not None:
        _proc = None


def _spawn(device: str, source_kind: str, source_arg: str) -> subprocess.Popen:
    pipeline = build(
        source_kind=source_kind,
        source_arg=source_arg,
        ir_xml=IR_XML,
        device=device,
        threshold=THRESHOLD,
        target_fps=TARGET_FPS,
        mqtt_host=MQTT_HOST,
        mqtt_topic=MQTT_TOPIC,
        frame_path=str(FRAME_PATH),
    )
    # Truncate the latency log per run so stale ticks don't skew p99.
    LATENCY_LOG.write_text("")

    env = os.environ.copy()
    env.update(
        {
            "GST_TRACERS": "latency_tracer;latency(flags=pipeline+element+reported)",
            "GST_DEBUG": "GST_TRACER:7",
            "GST_DEBUG_FILE": str(LATENCY_LOG),
            "GST_DEBUG_NO_COLOR": "1",
        }
    )

    # gst-launch-1.0 parses its own CLI (elements + `!` separators + properties
    # with spaces). Easiest & most robust is to hand the full pipeline string
    # to the shell so its own tokeniser handles quoting. stdout/stderr flow to
    # the container log so `docker logs` shows pipeline errors.
    #
    # For `basler`, the pipeline_string.py starts with `fdsrc fd=0`; a small
    # Python helper (basler_reader.py) streams raw YUY2 frames from pypylon
    # to stdout, which we pipe into gst-launch's fd=0. `exec` on the tail
    # ensures the shell doesn't linger past the pipeline exit; PIPESTATUS/
    # set -o pipefail isn't needed because our supervisor only cares that
    # *any* pipe stage exiting takes the whole group down.
    #
    # basler_reader.py streams raw camera-native YCbCr422_8 (UYVY, 2 B/px)
    # frames from pypylon on stdout — no `pylon.ImageFormatConverter`, no
    # software colour convert. pipeline_string.py's basler branch consumes
    # them via `fdsrc ! rawvideoparse format=uyvy ! vapostproc ! NV12` in VA
    # memory, and the drawer branch is `gvawatermark` (VA-native), so the
    # entire video path stays on the iGPU media engine — no `videoconvert`
    # anywhere. `--pixel-format bgr` remains available as a fallback for
    # cameras that do not advertise YCbCr422_8 (basler_reader.py fails fast
    # in that case).
    if source_kind == "basler":
        cmd = (
            f"exec python3 /opt/basler_reader.py {source_arg} "
            f"--geometry 1920x1080@{TARGET_FPS} --pixel-format uyvy "
            f"| exec gst-launch-1.0 {pipeline}"
        )
    else:
        cmd = f"exec gst-launch-1.0 {pipeline}"

    return subprocess.Popen(
        cmd,
        shell=True,
        env=env,
        start_new_session=True,
    )


def _supervisor_loop(device: str, source_kind: str, source_arg: str) -> None:
    """Respawn gst-launch on EOS/exit while /start was the last user intent.

    filesrc reads polyp_test.mp4 once and emits EOS. To match the old
    OpenCV loop-on-EOF behaviour we simply relaunch the pipeline.
    """
    global _proc
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
                _proc = _spawn(device, source_kind, source_arg)
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
            wanted_running=_wanted_running,
            latency_log=str(LATENCY_LOG),
            frame_path=str(FRAME_PATH),
        )


@app.post("/start")
def start():
    global _proc, _proc_device, _proc_source_kind, _proc_source_arg, _wanted_running, _supervisor
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
            _proc = _spawn(device, source_kind, source_arg)
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
            _proc = None
            _proc_device = None
            _proc_source_kind = None
            _proc_source_arg = None
            _wanted_running = False
            return jsonify(error=f"pipeline exited immediately (rc={rc})"), 500

        # Supervisor lives across the /start /stop cycle and respawns
        # gst-launch on EOS so the demo loops indefinitely.
        _supervisor = threading.Thread(
            target=_supervisor_loop, args=(device, source_kind, source_arg),
            name="pipeline-supervisor", daemon=True,
        )
        _supervisor.start()
        return jsonify(
            status="running", pid=_proc.pid, device=device,
            source_kind=source_kind, source_arg=source_arg,
        ), 200


@app.post("/stop")
def stop():
    global _proc, _proc_device, _proc_source_kind, _proc_source_arg, _wanted_running
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
        return jsonify(status="stopped", pid=pid), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=HTTP_PORT, threaded=True)
