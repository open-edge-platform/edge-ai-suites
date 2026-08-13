"""Fixed-interval segment writer.

Segment length is bounded by `max_duration`. Nothing recorded is dropped for
being short — `min_duration` only gates forced cuts upstream (see the
early-split logic in rtsp_monitor), so motion-end tails always reach the VLM.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from shared.config import SegmentConfig
from shared.time_utils import now_local_str


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

    @property
    def current_duration(self) -> float:
        """Seconds recorded in the open segment (0 when idle).

        Read by the early-split gate in rtsp_monitor: forced cuts are not
        allowed before a segment reaches min_duration.
        """
        return self._frame_count / self.fps if self.fps > 0 else 0.0

    def start_segment(self):
        """Start a new segment."""
        now = datetime.now()
        date_dir = os.path.join(self.output_dir, now.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)

        # Millisecond suffix: an ROI early-split (or any sub-second restart) must
        # not reuse the name of the segment just emitted — a 1s-resolution name
        # would truncate the file the MCP side is about to read.
        filename = f"{self.source_id}_{now.strftime('%H%M%S')}_{now.microsecond // 1000:03d}.mp4"
        self._current_path = os.path.join(date_dir, filename)
        self._start_time = now_local_str()
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
        """Finalize the current segment and return it for emission.

        Recorded content is never dropped for being short — a short tail at
        motion end still reaches the VLM. The only discarded file is an empty
        one (0 frames written — nothing to analyze).
        """
        if self._writer is None or self._current_path is None:
            return None

        self._writer.release()
        self._writer = None

        duration = self._frame_count / self.fps
        end_time = now_local_str()

        if self._frame_count == 0:
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

    def close(self) -> Optional[SegmentResult]:
        """Release the writer, finalizing the open segment.

        Delegates to finish(): the segment is returned for the caller to emit
        (only 0-frame files are removed). Never leaves an un-finalized file
        behind — the previous implementation could keep a file on disk without
        handing it to anyone.
        """
        return self.finish()
