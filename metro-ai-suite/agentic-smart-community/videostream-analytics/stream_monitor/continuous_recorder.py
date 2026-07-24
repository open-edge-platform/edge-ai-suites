"""Continuous recorder — fixed-interval segment recording independent of motion detection.

Runs in its own thread with its own VideoCapture, parallel to the motion pipeline.
Produces time-based segments (default 60s) and optionally emits recording events via sink.
Old segments are cleaned up based on retention_days.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2

from typing import Any

from shared.config import RecordingConfig, SourceConfig
from sinks import EventSink
from stream_monitor.base_monitor import BaseMonitor

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
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name=f"recorder-{self.source_id}", daemon=True
        )
        self._thread.start()
        logger.info("[%s] Continuous recorder started", self.source_id)

    def stop(self) -> None:
        self._running = False
        self._paused.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
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

    def _run(self):
        """Main loop: connect, record segments, reconnect on failure."""
        while self._running:
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
                self._record_loop(cap, fps, w, h)

            except Exception as e:
                logger.error("[%s] Recorder error: %s", self.source_id, e)
                self._status = "error"
            finally:
                if cap:
                    cap.release()

            if self._running:
                self._status = "reconnecting"
                logger.info("[%s] Recorder reconnecting in 10s...", self.source_id)
                time.sleep(10)

    def _record_loop(self, cap: cv2.VideoCapture, fps: float, w: int, h: int):
        """Record frames in fixed-interval segments."""
        while self._running:
            if not self._paused.is_set():
                if not self._paused.wait(timeout=1.0):
                    continue
                if not self._running:
                    break

            segment_path, writer = self._start_segment(fps, w, h)
            if writer is None:
                break

            start_time = datetime.now()
            frame_count = 0
            target_frames = int(self._cfg.interval_seconds * fps)

            while self._running and frame_count < target_frames:
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

        self._cleanup_old_segments()

    def _start_segment(self, fps: float, w: int, h: int) -> tuple[str, cv2.VideoWriter | None]:
        """Create a new segment file and VideoWriter."""
        now = datetime.now()
        date_dir = os.path.join(self._output_dir, now.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)

        filename = f"{self.source_id}_{now.strftime('%H%M%S')}.mp4"
        path = os.path.join(date_dir, filename)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h))
        if not writer.isOpened():
            logger.error("[%s] Cannot create writer: %s", self.source_id, path)
            return path, None

        return path, writer

    def _cleanup_old_segments(self):
        """Remove recording segments older than retention_days."""
        if self._cfg.retention_days <= 0:
            return

        cutoff = datetime.now() - timedelta(days=self._cfg.retention_days)
        try:
            for date_dir in Path(self._output_dir).iterdir():
                if not date_dir.is_dir():
                    continue
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                except ValueError:
                    continue
                if dir_date < cutoff:
                    for f in date_dir.iterdir():
                        f.unlink(missing_ok=True)
                    date_dir.rmdir()
                    logger.info("[%s] Cleaned up old recordings: %s", self.source_id, date_dir.name)
        except Exception as e:
            logger.warning("[%s] Cleanup error: %s", self.source_id, e)
