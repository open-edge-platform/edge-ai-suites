"""Updated endoscopy demo — decoupled capture / inference / display.
 
Architecture (their proven design, cleaned):
  * Capture thread  : pulls newest frame from the source, feeds display + (every
                      Nth frame) inference. Never blocks on inference.
  * Inference thread: OpenVINO detection on the latest frame -> shared results.
  * Display (main)  : draws EVERY captured frame with the latest detections
                      overlaid, so displayed FPS is independent of inference FPS.
 
Low-latency ``--camera-trigger vsync`` mode restores the reference design: a
dedicated GLX_OML vblank clock (``vsync.py``) software-triggers the camera in
phase with the monitor refresh, while the display shows the newest frame on
arrival via cv2 with zero frame queue. Inference stays fully decoupled and only
box coordinates cross to the display. Core pinning is retained but fully
configurable and off by default.
"""
from __future__ import annotations
 
# IMPORTANT: load the Basler (pypylon) runtime BEFORE OpenCV. Both bundle their
# own native image codecs (libjpeg etc.); if OpenCV loads first it replaces the
# JPEG error handler that pylon expects, and pylon's longjmp then lands on a
# freed stack frame -> "longjmp causes uninitialized stack frame" abort.
# Optional import so --source file / --source v4l2 users need not install pypylon.
try:  # noqa: SIM105
    import pypylon.pylon  # noqa: F401
except Exception:
    pass
 
import logging
import os
import queue
import signal
import threading
import time
 
import cv2
import numpy as np
 
from config import Config, parse_config
from detector import Box, Detector
from display import create_presenter
from sources import Source, create_source
from vsync import VSyncClock

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(name)s: %(message)s")
log = logging.getLogger("app")

shutdown = threading.Event()


class Captured:
    """A captured frame plus the perf-clock timestamps used for latency tracing."""

    __slots__ = ("image", "t_trigger_ns", "t_grab_ns")

    def __init__(self, image: np.ndarray, t_trigger_ns: int = 0, t_grab_ns: int = 0) -> None:
        self.image = image
        self.t_trigger_ns = t_trigger_ns
        self.t_grab_ns = t_grab_ns


class LatestDetections:
    """Thread-safe most-recent detection result with a timestamp."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._boxes: list[Box] = []
        self._ts_ns = 0
 
    def set(self, boxes: list[Box], ts_ns: int) -> None:
        with self._lock:
            self._boxes, self._ts_ns = boxes, ts_ns
 
    def get(self) -> tuple[list[Box], int]:
        with self._lock:
            return list(self._boxes), self._ts_ns
 
 
# PresentSignal (present-completion trigger) removed: capture is now phase-locked
# by the dedicated VSyncClock (vsync.py), and the display is a zero-queue cv2
# show-on-arrival window -- it no longer drives the capture timing.
 
 
class Rate:
    """Rolling FPS/latency counter."""
 
    def __init__(self) -> None:
        self._t = time.monotonic()
        self._n = 0
        self.fps = 0.0
        self._lat_ms = 0.0
 
    def tick(self, latency_ms: float | None = None) -> None:
        self._n += 1
        if latency_ms is not None:
            self._lat_ms = 0.9 * self._lat_ms + 0.1 * latency_ms
        now = time.monotonic()
        if now - self._t >= 1.0:
            self.fps = self._n / (now - self._t)
            self._t, self._n = now, 0
 
    @property
    def latency_ms(self) -> float:
        return self._lat_ms
 
 
def _pin(cpu: int | None, rt_priority: int, label: str) -> None:
    if cpu is None and rt_priority <= 0:
        return
    try:
        if cpu is not None:
            os.sched_setaffinity(0, {cpu})
        if rt_priority > 0:
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(rt_priority))
        log.info("%s pinned: cpu=%s rt_priority=%s", label, cpu, rt_priority)
    except (PermissionError, OSError) as exc:
        log.warning("%s pinning skipped (%s) — continuing unpinned", label, exc)
 
 
def _put_latest(q: "queue.Queue", item) -> None:  # noqa: ANN001
    """Non-blocking put that keeps only the newest item."""
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            pass


def capture_loop(cfg: Config, src: Source, display_q, infer_q, cap_rate: Rate,
                 clock: "VSyncClock | None" = None) -> None:  # noqa: ANN001
    _pin(cfg.cpu_capture, cfg.rt_priority, "capture")
    frame_interval = 1.0 / src.fps if (not src.is_live and src.fps > 0) else 0.0
    n = 0
    next_t = time.monotonic()
    last_msc = -1
    clock_stalls = 0
    while not shutdown.is_set():
        # vsync mode: wait for the monitor vblank (dedicated GLX_OML clock thread),
        # then software-trigger the camera every Nth vblank. CAPTURE -- not the
        # display -- is phase-locked to the refresh, exactly like the reference; the
        # display then just shows the newest frame on arrival (zero queue).
        if clock is not None:
            tick = clock.wait(last_msc, timeout=0.25)
            if tick is None:
                # Clock not delivering vblanks (compositor/driver without working
                # GLX_OML). Don't limp at the timeout cadence -- disable vblank
                # pacing and fall through to full-rate on-demand triggering.
                clock_stalls += 1
                if clock_stalls >= 3:
                    log.warning("vsync clock not advancing -- disabling vblank pacing, "
                                "using full-rate on-demand trigger")
                    clock = None
                continue
            clock_stalls = 0
            last_msc = tick[0]
            if last_msc % cfg.vsync_divisor != 0:
                continue
        t_trigger = time.perf_counter_ns()
        frame = src.read()
        t_grab = time.perf_counter_ns()
        if frame is None:
            if not src.is_live:
                shutdown.set()
                break
            continue
        n += 1
        cap_rate.tick()
        pkt = Captured(frame, t_trigger, t_grab)
        _put_latest(display_q, pkt)
        if n % cfg.frame_skip == 0:
            _put_latest(infer_q, pkt)
        # Pace file playback to its native FPS (live sources self-pace).
        if frame_interval and clock is None:
            next_t += frame_interval
            sleep = next_t - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_t = time.monotonic()


def inference_loop(cfg: Config, det: Detector, infer_q, latest: LatestDetections, inf_rate: Rate) -> None:  # noqa: ANN001
    _pin(cfg.cpu_inference, cfg.rt_priority, "inference")
    while not shutdown.is_set():
        try:
            pkt = infer_q.get(timeout=0.1)
        except queue.Empty:
            continue
        t0 = time.perf_counter()
        try:
            boxes = det.infer(pkt.image)
        except Exception as exc:  # noqa: BLE001
            log.warning("inference error: %s", exc)
            continue
        latest.set(boxes, time.perf_counter_ns())
        inf_rate.tick((time.perf_counter() - t0) * 1000.0)
 
 
def display_loop(cfg: Config, src: Source, display_q, latest: LatestDetections,
                 cap_rate: Rate, inf_rate: Rate) -> None:  # noqa: ANN001
    _pin(cfg.cpu_display, cfg.rt_priority, "display")
    writer = None
    if cfg.record_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = src.fps if src.fps > 0 else 30.0
        writer = cv2.VideoWriter(cfg.record_path, fourcc, fps, (src.width, src.height))
        log.info("recording annotated output -> %s", cfg.record_path)

    # Non-vsync GL fullscreen wants immediate present (swap_interval 0); windowed GL
    # stays vsync-locked. In vsync *capture* mode the presenter is cv2 (show-on-
    # arrival), so this flag is irrelevant there.
    vsync_lock = not cfg.fullscreen
    presenter = create_presenter(cfg.headless, cfg.presenter, src.width, src.height,
                                 cfg.display_scale, cfg.fullscreen, vsync_lock)
    vsync = getattr(presenter, "vsync", False)

    ttl_ns = cfg.detection_ttl_ms * 1_000_000
    disp_rate = Rate()
    last_log = time.monotonic()
    last_pkt: Captured | None = None
    annotated: np.ndarray | None = None  # cached drawn frame, reused for held-frame presents

    if cfg.latency_trace:
        # photon-to-pixel breakdown, one row per newly presented frame.
        print("clock_time,trigger_to_grab_ms,grab_to_display_ms,"
              "trigger_to_display_ms,infer_ms,disp_fps,cap_fps")

    while not shutdown.is_set():
        # Get the newest frame with zero polling jitter. On the cv2 show-on-arrival
        # path we BLOCK until a frame lands (wake the instant capture delivers it),
        # then drain any extras to the newest -- exactly what the reference does.
        # Polling here (get_nowait + sleep) added ~1-2ms of variable latency that,
        # against the 120Hz vblank, occasionally pushed a frame past its deadline
        # (a 1-frame slip). A vsync-locked GL presenter instead must re-present every
        # vblank, so it drains non-blocking and never waits on the queue.
        new = None
        if vsync:
            try:
                while True:
                    new = display_q.get_nowait()
            except queue.Empty:
                pass
        else:
            try:
                new = display_q.get(timeout=0.1)  # block: wake the instant a frame lands
                while True:                        # then keep only the newest
                    new = display_q.get_nowait()
            except queue.Empty:
                pass
        if new is not None:
            last_pkt = new

        if last_pkt is None:
            time.sleep(0.005)  # nothing captured yet
            continue

        # Only build/copy+annotate on a genuinely new frame; held frames re-present
        # the cached annotated buffer (saves a full-frame copy + redraw each idle loop).
        if new is not None or annotated is None:
            frame = last_pkt.image.copy()
            boxes, ts_ns = latest.get()
            fresh = boxes and (time.perf_counter_ns() - ts_ns) < ttl_ns
            if fresh:
                for b in boxes:
                    cv2.rectangle(frame, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), (0, 255, 0), 2)
                    cv2.putText(frame, f"{b.score:.2f}", (int(b.x1), max(14, int(b.y1) - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
            if new is not None:
                disp_rate.tick()
            hud = (f"disp {disp_rate.fps:4.1f}  cap {cap_rate.fps:4.1f}  "
                   f"infer {inf_rate.fps:4.1f} ({inf_rate.latency_ms:4.1f}ms)  "
                   f"det {len(boxes) if fresh else 0}")
            cv2.putText(frame, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(frame, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)
            annotated = frame

        # Record only genuinely new frames so the file stays at capture rate.
        if writer is not None and new is not None:
            writer.write(annotated)
        # Show the newest frame. cv2 (show-on-arrival) returns immediately; a
        # vsync-locked GL presenter blocks until the vblank. Held frames are cheap to
        # re-show and never queue, so latency stays "newest frame, shown immediately".
        if presenter is not None:
            if not presenter.present(annotated):  # ESC / window close -> False
                shutdown.set()

        # Per-stage photon-to-pixel latency, measured only on genuinely new frames.
        if cfg.latency_trace and new is not None:
            now = time.perf_counter_ns()
            trig_to_grab = (new.t_grab_ns - new.t_trigger_ns) / 1e6
            grab_to_disp = (now - new.t_grab_ns) / 1e6
            trig_to_disp = (now - new.t_trigger_ns) / 1e6
            print(f"{time.time():.3f},{trig_to_grab:.3f},{grab_to_disp:.3f},"
                  f"{trig_to_disp:.3f},{inf_rate.latency_ms:.3f},"
                  f"{disp_rate.fps:.1f},{cap_rate.fps:.1f}")

        now = time.monotonic()
        if now - last_log >= 5.0:
            log.info("FPS display=%.1f capture=%.1f inference=%.1f latency=%.1fms",
                     disp_rate.fps, cap_rate.fps, inf_rate.fps, inf_rate.latency_ms)
            last_log = now

    if writer is not None:
        writer.release()
    if presenter is not None:
        presenter.close()


def main(argv: list[str] | None = None) -> int:
    cfg = parse_config(argv)
    log.info("config: %s", cfg)

    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())

    det = Detector(cfg.model, device=cfg.device, threshold=cfg.threshold, iou_threshold=cfg.iou)
    src = create_source(cfg)
    log.info("source: %s %dx%d fps=%.1f live=%s", src.name, src.width, src.height, src.fps, src.is_live)

    # vsync trigger: a dedicated GLX_OML vblank clock thread phase-locks the CAMERA
    # capture to the monitor refresh (the reference's proven design). The display is
    # then a plain show-on-arrival cv2 window with zero frame queue -- it never blocks
    # on a vsync swap, so there is no "queue of frames" adding photon-to-pixel latency.
    clock: VSyncClock | None = None
    if cfg.camera_trigger == "vsync":
        clock = VSyncClock()
        if not clock.start():
            log.warning("vsync clock unavailable -- falling back to on-demand software trigger")
            clock = None
        elif cfg.presenter in ("auto", "gl"):
            # Capture owns the vblank lock; the display must show the newest frame
            # immediately (cv2), NOT block on its own vsync swap (that is what queued
            # frames and added latency). Force the show-on-arrival cv2 presenter.
            log.info("vsync trigger active -- capture is vblank-locked; "
                     "using cv2 show-on-arrival display (zero queue)")
            cfg.presenter = "cv2"

    display_q: "queue.Queue[Captured]" = queue.Queue(maxsize=2)
    infer_q: "queue.Queue[Captured]" = queue.Queue(maxsize=1)
    latest = LatestDetections()
    cap_rate, inf_rate = Rate(), Rate()

    threading.Thread(target=capture_loop, args=(cfg, src, display_q, infer_q, cap_rate, clock),
                     name="capture", daemon=True).start()
    threading.Thread(target=inference_loop, args=(cfg, det, infer_q, latest, inf_rate),
                     name="inference", daemon=True).start()
    try:
        display_loop(cfg, src, display_q, latest, cap_rate, inf_rate)  # main thread
    finally:
        shutdown.set()
        if clock is not None:
            clock.stop()
        time.sleep(0.2)
        src.close()
    return 0
 
 
if __name__ == "__main__":
    raise SystemExit(main())