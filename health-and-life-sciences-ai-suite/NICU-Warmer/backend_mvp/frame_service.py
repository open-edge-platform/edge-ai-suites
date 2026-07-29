"""D3: FrameService — thread-safe cache for the latest JPEG frame bytes.

The poller writes frames here; GET /frame/latest reads from here.
"""
from __future__ import annotations

import threading
import time
from typing import Optional


class FrameService:
    """Hold the single most-recent JPEG frame delivered by DLSPS.

    Thread safety: all reads and writes are protected by a lock so the
    Flask worker threads and the background poller can share one instance.

    Freshness: a frame is considered fresh if it arrived within
    ``max_age_seconds`` of the current time.  Stale frames return
    ``available=False`` to the caller so the frontend does not display
    a frozen image after DLSPS stops.
    """

    def __init__(self, max_age_seconds: float = 10.0) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[bytes] = None
        self._timestamp: Optional[float] = None
        self._max_age = max_age_seconds

    # ---------------------------------------------------------------------------
    # Write path (called by poller)
    # ---------------------------------------------------------------------------

    def update(self, jpeg_bytes: bytes) -> None:
        """Store the latest frame and record the arrival time."""
        with self._lock:
            self._frame = jpeg_bytes
            self._timestamp = time.monotonic()

    # ---------------------------------------------------------------------------
    # Read path (called by route handler)
    # ---------------------------------------------------------------------------

    def get_latest(self) -> tuple[Optional[bytes], bool]:
        """Return (frame_bytes, is_fresh).

        ``is_fresh`` is True only when a frame is present **and** it arrived
        within the configured max_age window.  Callers should use ``is_fresh``
        to decide whether to serve the frame or return an unavailable response.
        """
        with self._lock:
            if self._frame is None or self._timestamp is None:
                return None, False
            age = time.monotonic() - self._timestamp
            return self._frame, age < self._max_age

    def is_fresh(self) -> bool:
        """Convenience check: True when a recent frame is available."""
        _, fresh = self.get_latest()
        return fresh

    def clear(self) -> None:
        """Discard the cached frame (called on stop)."""
        with self._lock:
            self._frame = None
            self._timestamp = None
