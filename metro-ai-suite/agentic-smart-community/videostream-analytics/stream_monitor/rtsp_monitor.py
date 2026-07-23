"""Per-source video stream pipeline.

Each registered source gets its own StreamPipeline running in a background thread.
Pipeline: RTSP read -> motion detect -> segment extract -> webhook POST.

Exit logic (cascaded):
  - prefilter disabled: motion detector says static
  - prefilter enabled, before decision: static + prefilter decided
  - prefilter enabled, after pass: static (prefilter already confirmed person present)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any

import cv2

from shared.config import (
    MotionConfig,
    SegmentConfig,
    StaticConfig,
    PrefilterConfig,
    RoiConfig,
    HealthConfig,
    SourceConfig,
    DefaultsConfig,
    merge_config,
)
from sinks import EventSink
from stream_monitor.base_monitor import BaseMonitor
from stream_monitor.pipeline.motion_detector import MotionDetector
from stream_monitor.pipeline.segment_extractor import SegmentExtractor
from stream_monitor.pipeline.prefilter_yolo import YoloPrefilter, FramePrefilter
from stream_monitor.pipeline.roi_processor import prepare_roi_segment

logger = logging.getLogger(__name__)


class StreamPipeline(BaseMonitor):
    """Manages a single RTSP source: connect, detect motion, extract clips, post webhooks."""

    def __init__(
        self,
        source: SourceConfig,
        defaults: DefaultsConfig,
        data_dir: str,
        sink: EventSink,
        on_remove_callback=None,
    ):
        self.source = source
        self.source_id = source.source_id
        self.rtsp_url = source.source_url
        self._sink = sink
        self._on_remove_callback = on_remove_callback

        # Merge per-source config with defaults
        self._motion_cfg = merge_config(defaults.motion, source.motion)
        self._segment_cfg = merge_config(defaults.segment, source.segment)
        self._static_cfg = merge_config(defaults.static, source.static)
        self._recording_cfg = merge_config(defaults.recording, source.recording)
        self._prefilter_cfg = merge_config(defaults.prefilter, source.prefilter)
        self._roi_cfg = merge_config(defaults.roi, source.roi)
        self._health_cfg = merge_config(defaults.health, source.health)
        self.source.motion = self._motion_cfg
        self.source.segment = self._segment_cfg
        self.source.static = self._static_cfg
        self.source.recording = self._recording_cfg
        self.source.prefilter = self._prefilter_cfg
        self.source.roi = self._roi_cfg
        self.source.health = self._health_cfg

        # `data_dir` is already the per-source root (resolved by SourceManager).
        self._data_dir = data_dir
        os.makedirs(self._data_dir, exist_ok=True)
        self._latest_jpg_path = os.path.join(self._data_dir, "latest.jpg")
        # 1 Hz snapshot rate; actual cadence = max(1, _fps // _snapshot_hz)
        self._snapshot_hz = 1.0
        self._snapshot_next_idx = 0

        # Initialize prefilter if enabled
        self._prefilter: FramePrefilter | None = None
        self._init_prefilter()

        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = threading.Event()  # set = not paused (normal running)
        self._paused.set()
        self._status = "stopped"
        self._cap: cv2.VideoCapture | None = None
        self._frame_count = 0
        self._fps: float = 15.0

        # Health state tracking
        self._failure_count = 0
        self._last_failure_time: str | None = None
        self._start_time: str | None = None
        self._reconnect_count = 0

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name=f"pipeline-{self.source_id}", daemon=True
        )
        self._thread.start()
        logger.info("[%s] Pipeline started", self.source_id)

    def stop(self):
        self._running = False
        self._paused.set()  # unblock if paused, so thread can exit
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._status = "stopped"
        logger.info("[%s] Pipeline stopped", self.source_id)

    def pause(self):
        if not self._running or self._status == "paused":
            return
        self._paused.clear()
        self._status = "paused"
        self._emit_status("paused")
        logger.info("[%s] Pipeline paused", self.source_id)

    def resume(self):
        if not self._running or self._status != "paused":
            return
        self._paused.set()
        self._status = "online"
        self._emit_status("online")
        logger.info("[%s] Pipeline resumed", self.source_id)

    def _init_prefilter(self):
        """Initialize or rebuild prefilter from current config."""
        self._prefilter = None
        if self._prefilter_cfg.enabled and self._prefilter_cfg.model_path:
            try:
                yolo = YoloPrefilter(
                    model_path=self._prefilter_cfg.model_path,
                    target_classes=self._prefilter_cfg.target_classes,
                    min_confidence=self._prefilter_cfg.min_confidence,
                    device=self._prefilter_cfg.device,
                    long_side=self._prefilter_cfg.long_side,
                )
                self._prefilter = FramePrefilter(
                    yolo=yolo,
                    detect_fps=self._prefilter_cfg.detect_fps,
                    min_frames_hit=self._prefilter_cfg.min_frames_hit,
                )
                logger.info("[%s] Prefilter enabled: classes=%s", self.source_id, self._prefilter_cfg.target_classes)
            except Exception as e:
                logger.warning("[%s] Prefilter init failed, running without: %s", self.source_id, e)

    def update_pipeline_config(
        self,
        motion: MotionConfig | None = None,
        segment: SegmentConfig | None = None,
        prefilter: PrefilterConfig | None = None,
        roi: RoiConfig | None = None,
        health: HealthConfig | None = None,
    ):
        """Update pipeline configuration. Caller must stop/start for changes to take effect."""
        if motion:
            self._motion_cfg = merge_config(self._motion_cfg, motion)
            self.source.motion = self._motion_cfg
        if segment:
            self._segment_cfg = merge_config(self._segment_cfg, segment)
            self.source.segment = self._segment_cfg
        if prefilter:
            self._prefilter_cfg = merge_config(self._prefilter_cfg, prefilter)
            self.source.prefilter = self._prefilter_cfg
            self._init_prefilter()
        if roi:
            self._roi_cfg = merge_config(self._roi_cfg, roi)
            self.source.roi = self._roi_cfg
        if health:
            self._health_cfg = merge_config(self._health_cfg, health)
            self.source.health = self._health_cfg

    @property
    def health_info(self) -> dict:
        """Current health state for status reporting."""
        return {
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "reconnect_count": self._reconnect_count,
            "recovery_strategy": self._health_cfg.recovery_strategy,
            "max_failures": self._health_cfg.max_failures,
            "start_time": self._start_time,
        }

    def _calculate_backoff(self) -> float:
        """Exponential backoff based on reconnect attempts."""
        delay = self._health_cfg.backoff_base * (2 ** min(self._reconnect_count, 10))
        return min(delay, self._health_cfg.backoff_max)

    def _handle_unhealthy(self):
        """Execute recovery strategy when max_failures threshold is reached."""
        strategy = self._health_cfg.recovery_strategy

        self._status = "unhealthy"
        logger.warning("[%s] Source unhealthy (%d failures), strategy=%s",
                       self.source_id, self._failure_count, strategy)

        if strategy == "pause":
            self._paused.clear()
            self._status = "paused"
            self._emit_status("paused")
            self._paused.wait()
            if not self._running:
                return
            self._failure_count = 0
            self._reconnect_count = 0
        elif strategy == "remove":
            self._running = False
            self._status = "removed"
            if self._on_remove_callback:
                self._on_remove_callback(self.source_id)
        else:  # "retry"
            delay = self._health_cfg.backoff_max
            logger.info("[%s] Unhealthy, retrying in %.1fs...", self.source_id, delay)
            time.sleep(delay)

    def _run(self):
        """Main pipeline loop with health-aware reconnection."""
        self._start_time = datetime.now().isoformat(timespec="seconds")

        while self._running:
            try:
                self._connect()
                if self._cap and self._cap.isOpened():
                    # Respect an externally-set paused flag: RTSP idle-timeout
                    # during pause can drop us here after a silent reconnect,
                    # but the user intent is still "paused" until /resume.
                    if self._paused.is_set():
                        self._status = "online"
                        self._emit_status("online")
                    else:
                        self._status = "paused"
                    self._failure_count = 0
                    self._reconnect_count = 0
                    self._process_loop()
            except Exception as e:
                logger.error("[%s] Pipeline error: %s", self.source_id, e)
                self._status = "error"
                self._failure_count += 1
                self._last_failure_time = datetime.now().isoformat(timespec="seconds")

            if self._cap:
                self._cap.release()
                self._cap = None

            if self._running:
                self._reconnect_count += 1
                if self._failure_count >= self._health_cfg.max_failures:
                    self._handle_unhealthy()
                    if not self._running:
                        break
                else:
                    # Same rule as above: keep the pause label visible while
                    # we quietly retry in the background.
                    if self._paused.is_set():
                        self._status = "reconnecting"
                        self._emit_status("reconnecting")
                    delay = self._calculate_backoff()
                    logger.info("[%s] Reconnecting in %.1fs (attempt %d)...",
                               self.source_id, delay, self._reconnect_count)
                    time.sleep(delay)

        self._emit_status("stopped")

    def _connect(self):
        """Connect to RTSP stream."""
        self._status = "connecting"
        logger.info("[%s] Connecting to %s", self.source_id, self.rtsp_url)

        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            raise ConnectionError(f"Cannot open RTSP: {self.rtsp_url}")

        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 15.0
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        logger.info("[%s] Connected: %dx%d @ %.1f fps", self.source_id, w, h, self._fps)

    def _should_exit_motion(self, detector: MotionDetector, motion_frames: int) -> bool:
        """Cascaded exit logic: motion detector + prefilter collaboration.

        Without prefilter: exit when detector says static.
        With prefilter, before pass: exit when static AND min_dur reached AND decided.
        With prefilter, after pass: exit ONLY when exit_decided (YOLO no longer sees person).
        """
        if self._prefilter is None:
            return detector.is_static
        if self._prefilter.pass_decided:
            return self._prefilter.exit_decided
        min_dur_ok = (self._segment_cfg.min_duration <= 0
                      or motion_frames / self._fps >= self._segment_cfg.min_duration)
        return detector.is_static and min_dur_ok and self._prefilter.is_decided

    def _process_loop(self):
        """Read frames, detect motion, extract segments with fixed interval."""
        detector = MotionDetector(self._motion_cfg)
        motion_dir = os.path.join(self._data_dir, "motion_events")
        extractor = SegmentExtractor(
            config=self._segment_cfg,
            output_dir=motion_dir,
            source_id=self.source_id,
            fps=self._fps,
            frame_size=self._get_frame_size(),
        )

        in_motion = False
        motion_frames = 0
        consecutive_failures = 0

        # Static close-out state (strict Motion → static → Motion loop).
        # `None` means "not currently inside a closed-out quiet period"; it is
        # ONLY set when a motion segment ends, never at startup (the gap from
        # camera-online to first motion is system uptime, not a real quiet
        # period, and would otherwise be emitted as a bogus long static).
        static_start_wall: float | None = None
        static_start_iso: str | None = None

        while self._running:
            ret, frame = self._cap.read()  # type: ignore
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= self._health_cfg.max_failures:
                    # Count one connection-level failure; outer loop owns the
                    # retry/unhealthy decision (counting per-frame failures
                    # would skip retries entirely on a single bad reconnect).
                    self._failure_count += 1
                    self._last_failure_time = datetime.now().isoformat(timespec="seconds")
                    logger.warning(
                        "[%s] %d consecutive read failures, reconnecting",
                        self.source_id,
                        consecutive_failures,
                    )
                    break
                time.sleep(0.01)
                continue

            consecutive_failures = 0
            self._frame_count += 1
            self._maybe_write_snapshot(frame)

            if not self._paused.is_set():
                # Paused: keep reading frames (maintain RTSP connection) but skip processing
                if not self._paused.wait(timeout=0.1):
                    continue
                if not self._running:
                    break
                # Just resumed: if we were mid quiet-period, drop the span that
                # elapsed across the pause — the paused wall-clock is not real
                # idle time. Keep `None` as `None` (no open period to reset).
                if static_start_wall is not None:
                    static_start_wall = time.time()
                    static_start_iso = datetime.now().isoformat(timespec="seconds")

            # Motion detection
            motion_detected = detector.detect(frame)

            # State: enter motion
            if motion_detected and not in_motion:
                # Close out the preceding quiet period (if any) before the new
                # motion. `static_start_*` is None on the very first motion
                # (nothing to close out) — correct, we never fabricate a
                # leading static.
                if static_start_wall is not None:
                    self._maybe_emit_static(static_start_wall, static_start_iso)
                    static_start_wall = None
                    static_start_iso = None
                in_motion = True
                motion_frames = 0
                extractor.start_segment()
                if self._prefilter:
                    self._prefilter.reset()
                logger.info("[%s] Motion started", self.source_id)

            # State: in motion — record frames
            if in_motion:
                motion_frames += 1
                if self._prefilter:
                    self._prefilter.accumulate(frame, self._fps)

                result = extractor.add_frame(frame)
                if result:
                    # Interval reached — emit segment, start next one
                    self._maybe_emit(result)
                    extractor.start_segment()
                    if self._prefilter:
                        self._prefilter.reset_for_next_segment()
                elif self._prefilter and self._should_split_segment():
                    # Phase 9: trajectory union grew past auto_split_area;
                    # finish current segment early so the ROI crop stays tight.
                    early = extractor.finish()
                    if early:
                        self._maybe_emit(early)
                    extractor.start_segment()
                    self._prefilter.reset_for_next_segment()
                    logger.debug(
                        "[%s] Segment early-split by trajectory union",
                        self.source_id,
                    )

                # Cascaded exit check
                if self._should_exit_motion(detector, motion_frames):
                    tail = extractor.finish()
                    if tail:
                        self._maybe_emit(tail)
                    in_motion = False
                    # A real motion just ended → the quiet period begins now.
                    # This is the ONLY place static_start is armed (close-out
                    # model: static is always bracketed by two motions).
                    static_start_wall = time.time()
                    static_start_iso = datetime.now().isoformat(timespec="seconds")
                    logger.info("[%s] Motion ended", self.source_id)

        # Drain remaining segment on shutdown
        if in_motion:
            result = extractor.finish()
            if result:
                self._maybe_emit(result)
        elif static_start_wall is not None:
            # Shut down while inside a quiet period (a motion had ended and no
            # new motion arrived): emit the final static so state_query still
            # sees the trailing idle span. If motion never happened at all,
            # static_start_wall is None here and we (correctly) emit nothing.
            self._maybe_emit_static(static_start_wall, static_start_iso)
        extractor.close()

    def _should_split_segment(self) -> bool:
        """Return True when the active prefilter wants an early segment cut.

        Honors `pipeline.roi.auto_split_area`. With value <=0 or roi disabled,
        never splits.
        """
        if self._prefilter is None:
            return False
        roi_cfg = self._roi_cfg
        if not roi_cfg.enabled or roi_cfg.auto_split_area <= 0:
            return False
        return self._prefilter.should_split(roi_cfg.auto_split_area)

    def _maybe_emit(self, result):
        """Check prefilter and emit or discard segment."""
        pf_result = None
        if self._prefilter:
            pf_result = self._prefilter.result()
            if not pf_result.passed:
                try:
                    os.remove(result.path)
                except FileNotFoundError:
                    pass
                logger.debug("[%s] Segment discarded by prefilter: %s", self.source_id, result.path)
                return
        self._emit_segment(result, pf_result)

    def _emit_envelope(self, event_type: str, payload: dict[str, Any]) -> None:
        """Wrap payload in the nested envelope MCP expects.

        Envelope shape:
            { sourceId, type, timestamp, payload }
        """
        self._sink.emit({
            "sourceId": self.source_id,
            "type": event_type,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "payload": payload,
        })

    def _emit_segment(self, result, pf_result=None) -> None:
        """Post segment as motion event via sink, in MCP's nested envelope."""
        clip_path = result.path
        summary_clip_input = clip_path  # default: original clip

        # Phase 9: optionally produce <clip>_input.mp4 via ROI crop. Only when
        # prefilter passed AND roi is enabled AND we have a trajectory region.
        # Failure falls back to the original clip — never raises.
        roi_cfg = self._roi_cfg
        traj = getattr(pf_result, "trajectory_region_xyxy", None) if pf_result else None
        if (
            pf_result is not None
            and pf_result.passed
            and roi_cfg.enabled
            and traj is not None
        ):
            yolo_inst = None
            if roi_cfg.mode == "crop_and_concat" and self._prefilter is not None:
                yolo_inst = getattr(self._prefilter, "_yolo", None)
            roi_path = prepare_roi_segment(
                clip_path, traj,
                mode=roi_cfg.mode,
                expand=roi_cfg.expand,
                yolo=yolo_inst,
            )
            if roi_path:
                summary_clip_input = roi_path

        # Pre-cropped sibling clip fallback (e.g. produced out-of-band): only
        # honour it if ROI crop above didn't run.
        if summary_clip_input == clip_path:
            crop_path = clip_path.rsplit(".", 1)[0] + "_input.mp4"
            if os.path.exists(crop_path):
                summary_clip_input = crop_path

        payload: dict[str, Any] = {
            "event_file_path": clip_path,
            "summary_clip_input": summary_clip_input,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "duration_seconds": result.duration_s,
        }
        if pf_result is not None:
            payload["prefilter_passed"] = int(bool(pf_result.passed))
            payload["prefilter_classes"] = json.dumps(list(pf_result.hit_classes))
            payload["prefilter_confidence"] = float(pf_result.max_confidence)
            if traj is not None:
                # MCP expects a JSON string (events-endpoint.ts:143 wraps in String()).
                payload["trajectory_region"] = json.dumps(traj)

        self._emit_envelope("motion", payload)
        logger.debug(
            "[%s] Emitted motion: %.1fs %s prefilter=%s region=%s",
            self.source_id,
            result.duration_s,
            clip_path,
            "n/a" if pf_result is None else ("pass" if pf_result.passed else "skip"),
            traj,
        )

    def _maybe_emit_static(self, start_wall: float, start_iso: str | None) -> None:
        """Close out a quiet period as a `static` event, subject to config gates.

        Skips emission when static is disabled or the quiet span is shorter than
        `min_duration` (avoids flooding the events table with sub-second gaps).
        `start_wall` (float, from time.time()) drives the duration; `start_iso`
        is the ISO start recorded when the period began.
        """
        if not self._static_cfg.enabled:
            return
        duration = time.time() - start_wall
        if duration < self._static_cfg.min_duration:
            logger.debug(
                "[%s] Static period %.1fs < min_duration %.1fs, not emitting",
                self.source_id, duration, self._static_cfg.min_duration,
            )
            return
        end_iso = datetime.now().isoformat(timespec="seconds")
        self._emit_static(start_iso, end_iso, duration)

    def _emit_static(self, start_iso: str | None, end_iso: str, duration: float) -> None:
        """Emit a `static` event via the shared MCP envelope.

        Payload matches mcp_webhook_event_api.md §4: required `start_time` +
        `duration_seconds`, optional `end_time`.
        """
        self._emit_envelope("static", {
            "start_time": start_iso,
            "end_time": end_iso,
            "duration_seconds": duration,
        })
        logger.info(
            "[%s] Emitted static: %.1fs [%s → %s]",
            self.source_id, duration, start_iso, end_iso,
        )

    def _emit_status(self, status: str):
        """No-op. RTSP connection status is NOT a clip-segment event and must not be
        pushed to the MCP /events webhook — MCP only accepts motion/static/recording
        and 422s anything else, which used to trigger a retry storm that also slowed
        reconnection (see smarthome_arch2_dev.md §32). Health is still exposed via the
        internal `self._status` field, which MCP reads through GET /sources/{id}/status.
        Kept as a method (rather than deleting all call sites) so callers stay readable."""
        return

    def _maybe_write_snapshot(self, frame) -> None:
        """Write latest.jpg at ~_snapshot_hz Hz (atomic via tmp+rename).

        MCP's latest-frame resource reads this file directly off the shared volume.
        Errors are swallowed — snapshot is best-effort and must not stall pipeline.

        Note: cv2.imwrite dispatches by file extension, so the tmp filename must
        still end in `.jpg` — using `.tmp` suffix breaks with
        "could not find a writer for the specified extension".
        """
        if frame is None:
            return
        if self._frame_count < self._snapshot_next_idx:
            return
        step = max(1, int(round(max(self._fps, 1.0) / max(self._snapshot_hz, 0.1))))
        self._snapshot_next_idx = self._frame_count + step
        tmp_path = os.path.join(
            os.path.dirname(self._latest_jpg_path), ".latest.tmp.jpg"
        )
        try:
            ok = cv2.imwrite(tmp_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok:
                os.replace(tmp_path, self._latest_jpg_path)
            else:
                logger.warning("[%s] cv2.imwrite returned False for %s",
                               self.source_id, tmp_path)
        except Exception as e:
            logger.warning("[%s] snapshot write failed: %s", self.source_id, e)

    def _get_frame_size(self) -> tuple[int, int]:
        if self._cap:
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
            return (w, h)
        return (640, 480)
