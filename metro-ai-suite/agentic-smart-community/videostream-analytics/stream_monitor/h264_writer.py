"""H.264 segment writer backed by an ffmpeg subprocess.

`cv2.VideoWriter` with the "mp4v" fourcc writes MPEG-4 Part 2, which no browser
can decode — the dashboard could not replay recordings at all. pip-installed
OpenCV wheels ship no H.264 encoder, so frames are piped to ffmpeg instead.

Exposes the subset of the `cv2.VideoWriter` API the recorder uses, so it drops
straight into the existing frame loop.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

import numpy as np

logger = logging.getLogger(__name__)


class H264SegmentWriter:
    """Writes BGR frames to a browser-playable baseline H.264 mp4."""

    def __init__(self, path: str, fps: float, width: int, height: int, crf: int = 26):
        self._path = path
        self._proc: subprocess.Popen | None = None

        if shutil.which("ffmpeg") is None:
            logger.error("ffmpeg not found on PATH; cannot record %s", path)
            return

        args = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", f"{max(fps, 1.0):.6f}",
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-profile:v", "baseline",
            "-level", "3.1",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            "-an",
            # moov up front so the dashboard can seek with one range request.
            "-movflags", "+faststart",
            path,
        ]

        try:
            self._proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            logger.error("Cannot start ffmpeg for %s: %s", path, exc)
            self._proc = None

    def isOpened(self) -> bool:  # noqa: N802 - mirrors cv2.VideoWriter
        return self._proc is not None and self._proc.stdin is not None

    def write(self, frame: np.ndarray) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return
        try:
            proc.stdin.write(frame.tobytes())
        except (BrokenPipeError, ValueError):
            logger.warning("ffmpeg pipe closed early for %s", self._path)
            self._proc = None

    def release(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return

        try:
            if proc.stdin:
                proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass

        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg did not finish %s in time; killing", self._path)
            proc.kill()
            proc.wait(timeout=5)

        if proc.returncode:
            stderr = proc.stderr.read().decode("utf-8", "replace")[-500:] if proc.stderr else ""
            logger.error("ffmpeg exited %s for %s: %s", proc.returncode, self._path, stderr)
        elif proc.stderr:
            proc.stderr.close()
