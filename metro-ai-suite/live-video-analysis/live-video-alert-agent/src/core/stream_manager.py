# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
LiveStreamManager — per-camera RTSP/file ingestion with frame-rate throttling.

Design
------
- A dedicated daemon thread calls ``cap.grab()`` on every native frame to keep
  the stream buffer current (prevents stale-frame drift on RTSP sources).
- ``cap.retrieve()`` (the expensive decode step) is called only when
  ``target_interval`` has elapsed, slashing CPU usage by ~95 % at typical
  analysis rates (1 fps) versus native camera rate (25-30 fps).
- Decoded frames are optionally resized at capture time to reduce memory and
  downstream encoding work.
- Thread-safe health metrics are maintained for monitoring endpoints.
"""

import cv2
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StreamHealth:
    """Runtime health snapshot for one stream."""
    connected: bool = False
    actual_capture_fps: float = 0.0
    resolution: Optional[str] = None          # e.g. "1920x1080"
    buffer_fill: int = 0
    reconnect_count: int = 0
    last_frame_ts: Optional[float] = None     # monotonic


class LiveStreamManager:
    """
    Manages ingestion of a single video source (RTSP or local file).

    Parameters
    ----------
    rtsp_url:
        Stream URL (rtsp://, http://, https://, or file://).
    capture_fps:
        Target decoded-frame rate.  Defaults to 1 / ANALYSIS_INTERVAL
        (i.e. one frame per analysis cycle).  Set higher if more temporal
        context is needed.
    resize_height:
        If > 0, decoded frames are resized to this height (aspect-ratio
        preserved) before being stored.  Reduces memory and downstream
        JPEG encoding time.
    """

    def __init__(
        self,
        rtsp_url: str,
        capture_fps: float = 0.0,
        resize_height: int = 0,
    ):
        self.rtsp_url = rtsp_url
        self.frame_buffer: deque = deque(maxlen=settings.FRAME_BUFFER_SIZE)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.health = StreamHealth()

        # Resolve capture FPS
        if capture_fps > 0:
            self._capture_fps = capture_fps
        elif settings.CAPTURE_FPS > 0:
            self._capture_fps = settings.CAPTURE_FPS
        else:
            # Default: one frame per analysis cycle
            self._capture_fps = max(0.1, 1.0 / settings.ANALYSIS_INTERVAL)

        self._target_interval = 1.0 / self._capture_fps
        self._resize_height = resize_height if resize_height > 0 else settings.CAPTURE_RESIZE_HEIGHT

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._ingest_loop, daemon=True, name=f"stream-{self.rtsp_url[:40]}")
        self.thread.start()
        logger.info(f"Started LiveStreamManager for {self.rtsp_url} @ {self._capture_fps:.1f} fps capture")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3.0)
        self.health.connected = False

    def get_recent_frames(self, count: int = 1) -> List:
        """Return the *count* most recently decoded frames (thread-safe)."""
        with self._lock:
            buf = list(self.frame_buffer)
        if len(buf) < count:
            return []
        return buf[-count:]

    def get_health(self) -> StreamHealth:
        with self._lock:
            self.health.buffer_fill = len(self.frame_buffer)
        return self.health

    # ------------------------------------------------------------------ #
    # Internal loop
    # ------------------------------------------------------------------ #

    def _resize(self, frame):
        if self._resize_height <= 0:
            return frame
        h, w = frame.shape[:2]
        if h <= self._resize_height:
            return frame
        scale = self._resize_height / h
        return cv2.resize(frame, (int(w * scale), self._resize_height), interpolation=cv2.INTER_AREA)

    def _ingest_loop(self):
        is_local = not str(self.rtsp_url).startswith(("rtsp://", "rtsps://", "http://", "https://"))
        backoff = 2.0          # reconnection back-off (seconds)
        max_backoff = 30.0

        # FPS tracking
        fps_window: deque = deque(maxlen=30)
        last_capture = 0.0

        cap = cv2.VideoCapture(self.rtsp_url)

        while self.running:
            # ---- ensure capture is open ----
            if not cap.isOpened():
                logger.warning(f"[{self.rtsp_url}] Opening stream (backoff {backoff:.0f}s) ...")
                self.health.connected = False
                cap = cv2.VideoCapture(self.rtsp_url)
                if not cap.isOpened():
                    time.sleep(backoff)
                    backoff = min(backoff * 1.5, max_backoff)
                    self.health.reconnect_count += 1
                    continue
                backoff = 2.0  # reset on success

            # ---- record resolution once ----
            if self.health.resolution is None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if w > 0 and h > 0:
                    self.health.resolution = f"{w}x{h}"

            # ---- grab: advance stream pointer WITHOUT decoding ----
            grabbed = cap.grab()
            if not grabbed:
                if is_local:
                    # Loop local files back to start
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                logger.warning(f"[{self.rtsp_url}] Stream lost — reconnecting ...")
                self.health.connected = False
                cap.release()
                self.health.reconnect_count += 1
                time.sleep(backoff)
                backoff = min(backoff * 1.5, max_backoff)
                cap = cv2.VideoCapture(self.rtsp_url)
                continue

            self.health.connected = True
            backoff = 2.0  # reset on sustained connection

            # ---- retrieve (decode) only at target capture interval ----
            now = time.monotonic()
            if now - last_capture < self._target_interval:
                continue

            ret, frame = cap.retrieve()
            if not ret or frame is None:
                continue

            frame = self._resize(frame)

            ts = time.monotonic()
            with self._lock:
                self.frame_buffer.append(frame)
                self.health.last_frame_ts = ts
                self.health.buffer_fill = len(self.frame_buffer)

            # Update FPS estimate
            if last_capture > 0:
                fps_window.append(1.0 / max(ts - last_capture, 1e-6))
                self.health.actual_capture_fps = sum(fps_window) / len(fps_window)
            last_capture = ts

        cap.release()
        logger.info(f"LiveStreamManager stopped for {self.rtsp_url}")
