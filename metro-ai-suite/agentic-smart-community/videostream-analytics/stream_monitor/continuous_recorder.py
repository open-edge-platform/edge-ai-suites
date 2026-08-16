"""Continuous recorder — fixed-interval segment recording independent of motion detection.

Runs in its own thread with its own VideoCapture, parallel to the motion pipeline.
Produces time-based segments (default 60s) and optionally emits recording events via sink.
Old segments are pruned by the MCP server (storage.retention_days).
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime

import cv2

from typing import Any

from shared.config import RecordingConfig, SourceConfig
from sinks import EventSink
from stream_monitor.base_monitor import BaseMonitor
from stream_monitor.h264_writer import H264SegmentWriter

logger = logging.getLogger(__name__)


class ContinuousRecorder(BaseMonitor):
    """Records RTSP stream continuously in fixed-interval segments."""

    def __init__(
        self,
        source: SourceConfig,
        recording_cfg: RecordingConfig,
        data_dir: str,
        sink: EventSink,
    ):
        self.source = source
        self.source_id = source.source_id
        self.rtsp_url = source.source_url
        self._cfg = recording_cfg
        self._sink = sink

        # `data_dir` is the per-source root resolved by SourceManager.
        self._output_dir = os.path.join(data_dir, "recordings")
        os.makedirs(self._output_dir, exist_ok=True)

        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = threading.Event()
        self._paused.set()
        # stop_event makes every sleep in the run loops interruptible, so
        # stop() actually joins instead of leaving a parked thread behind.
        self._stop_event = threading.Event()
        # Bumped by start(); a stale thread from a previous start observes the
        # mismatch at its next loop check and exits instead of resurrecting.
        self._generation = 0
        self._status = "stopped"

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        if self._thread and self._thread.is_alive():
            # Previous thread is parked in a blocking call (cap.read). Safe to
            # proceed: the generation guard makes it exit when it wakes.
            logger.warning("[%s] Previous recorder thread still alive; superseding it", self.source_id)
        self._stop_event.clear()
        self._generation += 1
        self._running = True
        self._thread = threading.Thread(
            target=self._run, args=(self._generation,),
            name=f"recorder-{self.source_id}", daemon=True,
        )
        self._thread.start()
        logger.info("[%s] Continuous recorder started", self.source_id)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self._paused.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                # Parked in a blocking cap.read() — it cannot be interrupted,
                # but the generation guard prevents it from resurrecting on the
                # next start().
                logger.warning("[%s] Recorder thread did not exit within 10s", self.source_id)
        self._status = "stopped"
        logger.info("[%s] Continuous recorder stopped", self.source_id)

    def pause(self) -> None:
        if not self._running or self._status == "paused":
            return
        self._paused.clear()
        self._status = "paused"
        logger.info("[%s] Continuous recorder paused", self.source_id)

    def resume(self) -> None:
        if not self._running or self._status != "paused":
            return
        self._paused.set()
        self._status = "recording"
        logger.info("[%s] Continuous recorder resumed", self.source_id)

    def _run(self, generation: int):
        """Main loop: connect, record segments, reconnect on failure."""
        while self._running and self._generation == generation:
            cap = None
            try:
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    raise ConnectionError(f"Cannot open RTSP: {self.rtsp_url}")

                fps = cap.get(cv2.CAP_PROP_FPS) or self._cfg.fps
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

                self._status = "recording"
                logger.info("[%s] Recording: %dx%d @ %.1f fps", self.source_id, w, h, fps)
                self._record_loop(cap, fps, w, h, generation)

            except Exception as e:
                logger.error("[%s] Recorder error: %s", self.source_id, e)
                self._status = "error"
            finally:
                if cap:
                    cap.release()

            if self._running and self._generation == generation:
                self._status = "reconnecting"
                logger.info("[%s] Recorder reconnecting in 10s...", self.source_id)
                if self._stop_event.wait(10):
                    break

    def _record_loop(self, cap: cv2.VideoCapture, fps: float, w: int, h: int, generation: int):
        """Record frames in fixed-interval segments."""
        while self._running and self._generation == generation:
            if not self._paused.is_set():
                if not self._paused.wait(timeout=1.0):
                    continue
                if not self._running or self._generation != generation:
                    break

            segment_path, writer = self._start_segment(fps, w, h)
            if writer is None:
                break

            start_time = datetime.now()
            frame_count = 0
            target_frames = int(self._cfg.interval_seconds * fps)

            while self._running and self._generation == generation and frame_count < target_frames:
                if not self._paused.is_set():
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                writer.write(frame)
                frame_count += 1

            writer.release()
            end_time = datetime.now()
            duration = frame_count / fps if fps > 0 else 0

            if frame_count > 0:
                file_size = os.path.getsize(segment_path) if os.path.exists(segment_path) else 0
                payload: dict[str, Any] = {
                    "recording_path": segment_path,
                    "recording_start": start_time.isoformat(timespec="seconds"),
                    "recording_end": end_time.isoformat(timespec="seconds"),
                    "duration_seconds": round(duration, 1),
                    "file_size_bytes": file_size,
                }
                self._sink.emit({
                    "sourceId": self.source_id,
                    "type": "recording",
                    "timestamp": end_time.isoformat(timespec="seconds"),
                    "payload": payload,
                })
                logger.debug("[%s] Segment: %.1fs, %s", self.source_id, duration, segment_path)
            else:
                if os.path.exists(segment_path):
                    os.remove(segment_path)
                break

    def _start_segment(self, fps: float, w: int, h: int) -> tuple[str, H264SegmentWriter | None]:
        """Create a new segment file and writer."""
        now = datetime.now()
        date_dir = os.path.join(self._output_dir, now.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)

        # Millisecond suffix: a rapid read-fail/restart cycle must not reuse the
        # name of the segment just emitted (1s-resolution names can collide).
        filename = f"{self.source_id}_{now.strftime('%H%M%S')}_{now.microsecond // 1000:03d}.mp4"
        path = os.path.join(date_dir, filename)

        # H.264, not cv2.VideoWriter's mp4v — the dashboard replays these in a
        # browser, and no browser decodes MPEG-4 Part 2.
        writer = H264SegmentWriter(path, fps, w, h)
        if not writer.isOpened():
            logger.error("[%s] Cannot create writer: %s", self.source_id, path)
            return path, None

        return path, writer
