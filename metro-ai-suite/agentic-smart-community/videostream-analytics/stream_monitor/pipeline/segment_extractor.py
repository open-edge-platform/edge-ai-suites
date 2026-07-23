"""Fixed-interval segment writer with min_duration filter."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from shared.config import SegmentConfig


class SegmentResult:
    def __init__(self, path: str, duration_s: float, start_time: str, end_time: str):
        self.path = path
        self.duration_s = duration_s
        self.start_time = start_time
        self.end_time = end_time
        self.file_size = os.path.getsize(path) if os.path.exists(path) else 0


class SegmentExtractor:
    def __init__(
        self,
        config: SegmentConfig,
        output_dir: str,
        source_id: str,
        fps: float = 15.0,
        frame_size: tuple[int, int] = (640, 480),
    ):
        self.max_duration = config.max_duration
        self.min_duration = config.min_duration
        self.output_dir = output_dir
        self.source_id = source_id
        self.fps = fps
        self.frame_size = frame_size

        self._writer: Optional[cv2.VideoWriter] = None
        self._current_path: Optional[str] = None
        self._frame_count = 0
        self._start_time: Optional[str] = None

        os.makedirs(output_dir, exist_ok=True)

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    def start_segment(self):
        """Start a new segment."""
        now = datetime.now()
        date_dir = os.path.join(self.output_dir, now.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)

        filename = f"{self.source_id}_{now.strftime('%H%M%S')}.mp4"
        self._current_path = os.path.join(date_dir, filename)
        self._start_time = now.isoformat(timespec="seconds")
        self._frame_count = 0

        fourcc = cv2.VideoWriter.fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            self._current_path, fourcc, self.fps, self.frame_size
        )

    def add_frame(self, frame: cv2.typing.MatLike) -> Optional[SegmentResult]:
        """Add a frame. Returns SegmentResult when interval reached."""
        if self._writer is None:
            self.start_segment()

        self._writer.write(frame)  # type: ignore
        self._frame_count += 1

        duration = self._frame_count / self.fps
        if duration >= self.max_duration:
            return self.finish()
        return None

    def finish(self) -> Optional[SegmentResult]:
        """Finalize current segment."""
        if self._writer is None or self._current_path is None:
            return None

        self._writer.release()
        self._writer = None

        duration = self._frame_count / self.fps
        end_time = datetime.now().isoformat(timespec="seconds")

        if duration < self.min_duration:
            try:
                os.unlink(self._current_path)
            except OSError:
                pass
            self._current_path = None
            return None

        result = SegmentResult(
            path=self._current_path,
            duration_s=duration,
            start_time=self._start_time or end_time,
            end_time=end_time,
        )
        self._current_path = None
        self._start_time = None
        self._frame_count = 0
        return result

    def close(self):
        if self._writer:
            self._writer.release()
            self._writer = None
            if self._current_path and os.path.exists(self._current_path):
                duration = self._frame_count / self.fps if self.fps > 0 else 0
                if duration < self.min_duration:
                    try:
                        os.unlink(self._current_path)
                    except OSError:
                        pass
                    self._current_path = None
