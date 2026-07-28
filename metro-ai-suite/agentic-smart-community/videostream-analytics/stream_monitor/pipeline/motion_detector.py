"""Frame-diff based motion detector."""

from __future__ import annotations

import cv2
import numpy as np

from shared.config import MotionConfig


class MotionDetector:
    def __init__(self, config: MotionConfig):
        self.diff_threshold = config.diff_threshold
        self.area_ratio = config.area_ratio
        self.stable_frames = config.stable_frames
        self._prev_gray: np.ndarray | None = None
        self._static_count = 0

    @property
    def is_static(self) -> bool:
        return self._static_count >= self.stable_frames

    def detect(self, frame: np.ndarray) -> bool:
        """Process a frame. Returns True if motion detected in this frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return False

        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        _, thresh = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        changed_ratio = np.count_nonzero(thresh) / thresh.size

        if changed_ratio >= self.area_ratio:
            self._static_count = 0
            return True
        else:
            self._static_count += 1
            return False

    def reset(self):
        self._prev_gray = None
        self._static_count = 0
