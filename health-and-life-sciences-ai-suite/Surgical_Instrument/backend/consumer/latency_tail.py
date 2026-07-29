"""Background tailer for the DL Streamer `latency_tracer` log.

We consume two tracers that the launcher enables together via
`GST_TRACERS="latency_tracer;latency(flags=pipeline+element+reported)"`.

* `_recent_infer_ms`  — per-frame element-latency for the gvadetect element
                        (named `det` in our pipeline). Emitted by the
                        GStreamer core `latency` tracer as
                        `element-latency, element=det, time=<ns>`.
                        Nanoseconds -> milliseconds. Pure model + pre/post
                        inside that one element — the number to compare
                        accelerators.

* processing latency  — per-frame **processing latency**: the sum of
                        element-latencies across the AI + annotate + encode
                        chain (`det` + `gvatrack0` + `gvametaconvert0`
                        + `gvawatermarkimpl0` + `jpegenc0`). This is the
                        "camera-to-screen" number for a live-camera source
                        and the number the customer requirement targets
                        (<30 ms). We keep one rolling deque per element
                        and, at snapshot time, sum the per-element means
                        (mathematically correct: `E[X+Y] = E[X]+E[Y]`) and
                        sum the per-element p99s (conservative honest
                        upper bound — the true joint p99 is smaller
                        because element latencies are only weakly
                        correlated frame-to-frame).

* `_recent_e2e_ms`    — per-frame **source-to-sink residence** in
                        milliseconds. Emitted by Intel DL Streamer's
                        `latency_tracer` as the `frame_latency` field
                        inside a `latency_tracer_pipeline` record. Per
                        the DLS schema header this is literally
                        "current frame latency in ms" — the true
                        end-to-end pipeline residence (includes decode,
                        any pacing wait, detect, tracker, watermark,
                        encode, sink). Kept for diagnostics; hidden from
                        the primary UI because it is dominated by
                        filesrc/decodebin read-ahead in a paced-file demo
                        pipeline and does not represent live-camera
                        camera-to-screen latency.

Why NOT the same `latency_tracer_pipeline` record's `latency=(double)...`
field: DLS's own schema describes it as "pipeline latency in ms (if frames
dropped this may result in invalid value)". Numerically it converges to
`1000/fps` (inter-frame period at the sink) and is degenerate as a
per-frame delay signal.
"""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import deque
from pathlib import Path

log = logging.getLogger(__name__)

# element-latency, element-id=(string)0x..., element=(string)det, src=(string)src,
#   time=(guint64)15234567, ts=(guint64)...;
_RE_ELEMENT = re.compile(
    r"element-latency,[^;]*element=\(string\)(?P<elem>[^,]+),[^;]*"
    r"time=\(guint64\)(?P<ns>\d+)"
)

# latency_tracer_pipeline, ..., frame_latency=(double)380.6, ..., latency=(double)18.4, ...
_RE_PIPELINE = re.compile(
    r"latency_tracer_pipeline,[^;]*frame_latency=\(double\)(?P<ms>[\d.]+)"
)

# gvadetect element (name=det in our pipeline).
_INFER_ELEM = re.compile(r"^(gvadetect|det)\d*$")

# Elements in the "processing chain" — AI inference + tracker + metadata +
# on-screen annotate + JPEG encode. For the file/v4l2 branches the drawer
# is our custom gvapython (named `drawer`; see pipeline/watermark_green.py).
# For the basler branch the drawer is DL Streamer's built-in `gvawatermark`
# (VA-memory native, no colour convert) — it appears in tracer logs as
# `gvawatermarkimpl0`. Both names are listed so the same allowlist works
# regardless of source_kind. `meta` is our tee's name, NOT a
# gvametaconvert. `gvametaconvert0` is the one in the display chain (before
# the tee); the MQTT branch has a separate gvapython publisher not counted
# as "processing" here (it's I/O to an external broker).
_PROCESSING_ELEMENTS: tuple[str, ...] = (
    "det",                # gvadetect (explicit name)
    "gvadetect0",         # gvadetect (default auto name)
    "gvatrack0",
    "gvametaconvert0",
    "drawer",             # gvapython single-green bbox drawer (file/v4l2)
    "gvawatermark0",      # gvawatermark auto name
    "gvawatermarkimpl0",  # gvawatermark internal impl (basler VA-native path)
    "vajpegenc0",         # VA-API HW JPEG encoder on iGPU (was libjpeg-turbo/jpegenc0)
)


class LatencyTail:
    def __init__(self, log_path: str | Path, maxlen: int = 120) -> None:
        self._path = Path(log_path)
        self._recent_infer_ms: deque[float] = deque(maxlen=maxlen)
        self._recent_e2e_ms: deque[float] = deque(maxlen=maxlen)
        # Per-processing-element rolling deque. Sum of per-element means =
        # mean of per-frame sums (linearity of expectation). Sum of
        # per-element p99s is a conservative honest upper bound on the
        # per-frame p99.
        self._recent_elem_ms: dict[str, deque[float]] = {
            e: deque(maxlen=maxlen) for e in _PROCESSING_ELEMENTS
        }
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="latency-tail", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    # ---------------------------------------------------------------- reader
    def _run(self) -> None:
        # Wait for file to exist (pipeline may still be spinning up).
        for _ in range(50):
            if self._path.exists():
                break
            if self._stop.wait(0.1):
                return
        try:
            fh = self._path.open("r", encoding="utf-8", errors="ignore")
        except OSError as exc:
            log.warning("cannot open latency log %s: %s", self._path, exc)
            return
        # Start from the current end so we don't replay stale ticks (the
        # pipeline truncates the log at each /start anyway).
        fh.seek(0, 2)
        pos = fh.tell()

        buf = ""
        while not self._stop.is_set():
            # Detect log rotation / truncation: if the file shrunk since
            # our last read, seek back to the start. This handles the
            # /start race where the pipeline truncates /frames/latency.log
            # right after we open it at EOF.
            try:
                size = self._path.stat().st_size
            except OSError:
                size = pos
            if size < pos:
                fh.seek(0)
                pos = 0
                buf = ""

            chunk = fh.read(8192)
            if not chunk:
                time.sleep(0.05)
                continue
            pos += len(chunk)
            buf += chunk
            *lines, buf = buf.split("\n")
            for line in lines:
                self._parse_line(line)

        try:
            fh.close()
        except Exception:  # noqa: BLE001
            pass

    def _parse_line(self, line: str) -> None:
        m = _RE_PIPELINE.search(line)
        if m:
            ms = float(m.group("ms"))
            with self._lock:
                self._recent_e2e_ms.append(ms)
            return
        m = _RE_ELEMENT.search(line)
        if not m:
            return
        elem = m.group("elem")
        time_ms = int(m.group("ns")) / 1_000_000.0
        with self._lock:
            # gvadetect standalone → infer-only rolling metric.
            if _INFER_ELEM.match(elem):
                self._recent_infer_ms.append(time_ms)
            # Processing-chain per-element rolling window.
            dq = self._recent_elem_ms.get(elem)
            if dq is not None:
                dq.append(time_ms)

    # ---------------------------------------------------------------- stats
    @staticmethod
    def _mean(values: list[float]) -> float:
        return (sum(values) / len(values)) if values else 0.0

    @staticmethod
    def _p99(values: list[float]) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        k = max(0, int(round(len(s) * 0.99)) - 1)
        return s[k]

    @staticmethod
    def _nearest_rank(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        k = max(1, min(len(s), int(math.ceil(q * len(s)))))
        return s[k - 1]

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            infer = list(self._recent_infer_ms)
            elem_snap = {name: list(dq) for name, dq in self._recent_elem_ms.items()}
            e2e = list(self._recent_e2e_ms)
        infer_mean = self._mean(infer)
        infer_p50 = self._nearest_rank(infer, 0.50)
        infer_p90 = self._nearest_rank(infer, 0.90)
        infer_p95 = self._nearest_rank(infer, 0.95)
        infer_p99 = self._nearest_rank(infer, 0.99)
        # Sum-of-per-element for the processing chain. Skip elements with
        # no data yet so we don't publish a low-ball number during the
        # first frame or two.
        elem_means = [self._mean(v) for v in elem_snap.values() if v]
        elem_p50s = [self._nearest_rank(v, 0.50) for v in elem_snap.values() if v]
        elem_p90s = [self._nearest_rank(v, 0.90) for v in elem_snap.values() if v]
        elem_p95s = [self._nearest_rank(v, 0.95) for v in elem_snap.values() if v]
        elem_p99s = [self._nearest_rank(v, 0.99) for v in elem_snap.values() if v]
        # Report processing once we have at least an inference element and
        # at least one render/encode element observed. Requiring every
        # historical element name to be present can pin this to zero when
        # the active pipeline variant omits optional stages.
        has_infer = bool(elem_snap.get("det") or elem_snap.get("gvadetect0"))
        has_render = bool(
            elem_snap.get("gvawatermark0")
            or elem_snap.get("gvawatermarkimpl0")
            or elem_snap.get("drawer")
            or elem_snap.get("vajpegenc0")
        )
        if has_infer and has_render and elem_means:
            proc_mean = sum(elem_means)
            proc_p50 = sum(elem_p50s)
            proc_p90 = sum(elem_p90s)
            proc_p95 = sum(elem_p95s)
            proc_p99 = sum(elem_p99s)
        else:
            proc_mean = 0.0
            proc_p50 = 0.0
            proc_p90 = 0.0
            proc_p95 = 0.0
            proc_p99 = 0.0
        e2e_mean = self._mean(e2e)
        e2e_p50 = self._nearest_rank(e2e, 0.50)
        e2e_p90 = self._nearest_rank(e2e, 0.90)
        e2e_p95 = self._nearest_rank(e2e, 0.95)
        e2e_p99 = self._nearest_rank(e2e, 0.99)
        return {
            "infer_mean_ms": infer_mean,
            "infer_p50_ms": infer_p50,
            "infer_p90_ms": infer_p90,
            "infer_p95_ms": infer_p95,
            "infer_p99_ms": infer_p99,
            # Processing-chain sum — "camera-to-screen" for a live source.
            "processing_mean_ms": proc_mean,
            "processing_p50_ms": proc_p50,
            "processing_p90_ms": proc_p90,
            "processing_p95_ms": proc_p95,
            "processing_p99_ms": proc_p99,
            # Full source→sink residence — includes decode + any pacing.
            # Kept for diagnostics, hidden from the primary UI.
            "e2e_mean_ms": e2e_mean,
            "e2e_p50_ms": e2e_p50,
            "e2e_p90_ms": e2e_p90,
            "e2e_p95_ms": e2e_p95,
            "e2e_p99_ms": e2e_p99,
            # Back-compat aliases used by older UI/consumers.
            "total_mean_ms": e2e_mean,
            "total_p99_ms": e2e_p99,
        }
