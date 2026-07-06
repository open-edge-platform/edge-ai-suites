"""JPEG frame reader with EOI-marker retry.

The pipeline writes `/frames/latest.jpg` at 30 fps via GStreamer's
`multifilesink` — every frame overwrites the same file. Racing the writer
occasionally yields a partially-written JPEG missing the `FFD9` end-of-image
marker; PIL and browsers reject it as truncated. We verify the trailer and
retry up to three times (5 ms sleep between attempts), falling back to the
previously-good frame if the writer is stalled.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)


class FrameReader:
    _EOI = b"\xff\xd9"

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._last_good: bytes | None = None
        self._lock = threading.Lock()

    def latest_jpeg(self) -> bytes | None:
        """Return the most recent complete JPEG, or the last good one, or None."""
        for _ in range(3):
            try:
                data = self._path.read_bytes()
            except FileNotFoundError:
                time.sleep(0.005)
                continue
            except OSError as exc:
                log.debug("frame read error: %s", exc)
                time.sleep(0.005)
                continue

            if len(data) > 4 and data[-2:] == self._EOI:
                with self._lock:
                    self._last_good = data
                return data
            # Partial write — retry.
            time.sleep(0.005)

        with self._lock:
            return self._last_good

    def clear(self) -> None:
        with self._lock:
            self._last_good = None
