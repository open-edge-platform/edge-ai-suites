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
        # Frames with mtime <= this are considered stale (left over from a
        # previous session) and treated as "no frame yet". Set by clear();
        # zero means "accept anything". This is the belt-and-braces guard
        # for the case where the on-disk unlink fails (e.g. the volume was
        # mounted read-only in an older compose file).
        self._min_mtime_ns: int = 0
        self._lock = threading.Lock()

    def latest_jpeg(self) -> bytes | None:
        """Return the most recent complete JPEG, or the last good one, or None."""
        for _ in range(3):
            try:
                st = self._path.stat()
            except FileNotFoundError:
                time.sleep(0.005)
                continue
            except OSError as exc:
                log.debug("frame stat error: %s", exc)
                time.sleep(0.005)
                continue

            # Reject frames that predate the current session — protects
            # against stale JPEGs from the previous run leaking into the UI
            # while the new pipeline is still spinning up its first frame.
            if self._min_mtime_ns and st.st_mtime_ns <= self._min_mtime_ns:
                time.sleep(0.005)
                continue

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
        # Record "now" as the staleness threshold — any frame with an
        # earlier mtime is from the previous session.
        self._min_mtime_ns = time.time_ns()
        # Also delete the on-disk JPEG so the first read after a Start
        # blocks until the pipeline produces a fresh frame — otherwise
        # `latest_jpeg()` immediately returns the stale JPEG left over
        # from the previous run (which, e.g., was still the camera frame
        # when the user restarts with a file source).
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.debug("frame file unlink error: %s", exc)
