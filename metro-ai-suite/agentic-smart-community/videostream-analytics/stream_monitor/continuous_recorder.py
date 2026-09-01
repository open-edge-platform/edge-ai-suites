"""Continuous recorder — fixed-interval segment recording independent of motion detection.

Runs in its own thread, parallel to the motion pipeline, and emits recording
events via sink. Old segments are pruned by the MCP server (storage.retention_days).

Two backends (RecordingConfig.backend):
  - "copy" (default): one ffmpeg subprocess per session pulls the stream and
    cuts segments with `-c copy` — no decode, no encode, original codec and
    bitrate preserved, near-zero CPU. Segment boundaries align to the source
    GOP (ffmpeg cuts at the first keyframe at/after segment_time).
  - "x264": own cv2.VideoCapture (a second RTSP session per source), decode +
    libx264 re-encode via H264SegmentWriter. Kept as a rollback escape hatch.
"""

from __future__ import annotations

import glob
import itertools
import logging
import os
import shutil
import signal
import subprocess
import threading
from datetime import datetime, timedelta

import cv2

from typing import Any

from shared.config import RecordingConfig, SourceConfig
from sinks import EventSink
from stream_monitor.base_monitor import BaseMonitor
from stream_monitor.h264_writer import H264SegmentWriter

logger = logging.getLogger(__name__)

# Socket I/O stall tolerance for the copy backend (rtsp demuxer `-timeout`,
# microseconds — only meaningful with TCP transport).
_RW_TIMEOUT_US = 15_000_000


class ContinuousRecorder(BaseMonitor):
    """Records RTSP stream continuously in fixed-interval segments."""

    def __init__(
        self,
        source: SourceConfig,
        recording_cfg: RecordingConfig,
        data_dir: str,
        sink: EventSink,
        protocol_whitelist: list[str] | None = None,
    ):
        self.source = source
        self.source_id = source.source_id
        self.rtsp_url = source.source_url
        self._cfg = recording_cfg
        self._sink = sink
        # Constrains which protocols the ffmpeg child may open, independently of
        # the API-layer scheme check on `source_url`. Defaults to the same set as
        # `SecurityConfig.ffmpeg_protocol_whitelist` so a directly-constructed
        # recorder (CLI `stream` mode, tests) is restricted too.
        self._protocol_whitelist = protocol_whitelist or [
            "file", "crypto", "rtp", "udp", "tcp", "tls", "rtsp", "rtsps", "http", "https",
        ]

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
        # Copy backend: one token per ffmpeg session, embedded in the segment
        # names it writes. `itertools.count.__next__` is atomic, so a superseded
        # generation's thread racing a fresh one still gets a distinct value.
        self._session_seq = itertools.count(1)

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
        """Main loop: record segments, reconnect on failure."""
        while self._running and self._generation == generation:
            cap = None
            try:
                if self._cfg.backend == "copy":
                    self._record_loop_copy(generation)
                else:
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

    # ------------------------------------------------------------------
    # "copy" backend: ffmpeg -c copy segmenting, no decode/encode.
    # ------------------------------------------------------------------

    def _record_loop_copy(self, generation: int):
        """Run ffmpeg segmenting sessions until paused/stopped/failed."""
        while self._running and self._generation == generation:
            if not self._paused.is_set():
                if not self._paused.wait(timeout=1.0):
                    continue
                if not self._running or self._generation != generation:
                    return

            # ffmpeg exited on its own (stream error / EOF) → back to _run's
            # reconnect backoff; interrupted by pause/stop → loop here (park or exit).
            if not self._run_copy_session(generation):
                return

    def _run_copy_session(self, generation: int) -> bool:
        """Run one ffmpeg segmenting session.

        Returns True when the session was interrupted by pause/stop (caller
        loops back to the pause park), False when ffmpeg exited on its own
        (caller reconnects).
        """
        if shutil.which("ffmpeg") is None:
            raise ConnectionError("ffmpeg not found on PATH; cannot record (copy backend)")

        self._ensure_date_dirs()
        # Per-session token. ffmpeg's -strftime has no sub-second specifier and
        # -y overwrites silently, so two segments named in the same wall-clock
        # second would destroy each other's file AND collapse into one event
        # (_drain_segment_list dedupes by name). Within one session that cannot
        # happen (segments are >=1s apart), but across sessions it can — a
        # sub-second pause/resume flap, or a reconnect landing on the same
        # second. The token makes cross-session names disjoint; the pid keeps it
        # true across process restarts. Starts with a letter so
        # _segment_start_from_path can never mistake it for HHMMSS.
        session_tag = f"s{os.getpid():x}x{next(self._session_seq):x}"
        list_path = os.path.join(
            self._output_dir, f".segments_{os.getpid()}_{generation}_{session_tag}.csv"
        )
        self._cleanup_stale_lists(keep=os.path.basename(list_path))
        pattern = os.path.join(
            self._output_dir, "%Y-%m-%d", f"{self.source_id}_%H%M%S_{session_tag}.mp4"
        )

        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        # Must precede -i: it constrains which protocols the demuxer may open.
        # Defence in depth behind the API-layer scheme allowlist — ffmpeg itself
        # refuses `concat:`/`subfile:`/`data:` inputs even if one gets through.
        args += ["-protocol_whitelist", ",".join(self._protocol_whitelist)]
        if self.rtsp_url.startswith("rtsp://"):
            args += ["-rtsp_transport", "tcp", "-timeout", str(_RW_TIMEOUT_US)]
        else:
            # File/test inputs: pace reads like a live source so segment timing
            # (and strftime naming) behaves as it would for RTSP.
            args += ["-re"]
        args += [
            "-i", self.rtsp_url,
            "-map", "0:v:0", "-c", "copy", "-an",
            "-avoid_negative_ts", "make_zero",
            "-f", "segment",
            "-segment_time", str(self._cfg.interval_seconds),
            "-reset_timestamps", "1",
            # moov up front per segment, so the dashboard can seek with one
            # range request (same contract as the x264 backend's +faststart).
            "-segment_format_options", "movflags=+faststart",
            "-segment_list", list_path, "-segment_list_type", "csv",
            "-strftime", "1",
            pattern,
        ]

        log_file = open(list_path + ".log", "wb")
        try:
            proc = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=log_file,
            )
        except OSError as exc:
            log_file.close()
            raise ConnectionError(f"Cannot start ffmpeg: {exc}") from exc

        self._status = "recording"
        logger.info(
            "[%s] Recording (copy): %ds segments from %s",
            self.source_id, self._cfg.interval_seconds, self.rtsp_url,
        )

        emitted: set[str] = set()
        interrupted = False
        try:
            interrupted = self._watch_copy_session(proc, generation, list_path, emitted)
            return interrupted
        finally:
            rc = proc.poll()
            # ffmpeg exits 255 on SIGINT — only log when it died on its own.
            if rc and not interrupted:
                tail = self._read_log_tail(list_path)
                if tail:
                    logger.error("[%s] ffmpeg exited %s: %s", self.source_id, rc, tail)
            log_file.close()
            try:
                os.remove(list_path)
                os.remove(list_path + ".log")
            except OSError:
                pass

    def _watch_copy_session(
        self, proc: subprocess.Popen, generation: int, list_path: str, emitted: set[str]
    ) -> bool:
        """Poll a running ffmpeg; drain completed segments; interrupt on pause/stop."""
        while True:
            rc = proc.poll()
            self._drain_segment_list(list_path, emitted)
            if rc is not None:
                return False
            if not self._running or self._generation != generation or not self._paused.is_set():
                self._finalize_ffmpeg(proc)
                # SIGINT flushed the in-progress segment's entry — drain once more.
                self._drain_segment_list(list_path, emitted)
                return True
            self._stop_event.wait(0.2)

    @staticmethod
    def _finalize_ffmpeg(proc: subprocess.Popen) -> None:
        """SIGINT so ffmpeg writes the moov + final segment-list entry; kill on stall."""
        try:
            proc.send_signal(signal.SIGINT)
        except OSError:
            return
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg did not exit on SIGINT; killing")
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def _drain_segment_list(self, list_path: str, emitted: set[str]) -> None:
        """Emit events for newly completed segments from ffmpeg's csv list.

        The segment muxer appends `name,start,end` when a segment file is
        finalized, so every entry seen here is a complete, playable file.
        Duration comes from the list (start/end are on the continuous input
        timeline), segment wall-clock start from the strftime filename — no
        ffprobe needed (the production image builds ffmpeg without it).
        """
        self._ensure_date_dirs()
        try:
            with open(list_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # `name,start,end` — split from the right so a comma in source_id
            # (and thus in name) can't break parsing.
            parts = line.rsplit(",", 2)
            if len(parts) != 3:
                continue
            name, start_s, end_s = parts
            name = name.strip()
            if not name or name in emitted:
                continue
            try:
                duration = float(end_s) - float(start_s)
            except ValueError:
                continue
            if duration <= 0:
                continue
            path = self._resolve_segment_path(name)
            if path is None:
                continue
            emitted.add(name)
            self._emit_copy_segment(path, duration)

    def _resolve_segment_path(self, name: str) -> str | None:
        """Resolve a segment-list entry to the actual file path.

        ffmpeg writes just the basename into the list even when the output
        pattern contains directories, so search the date dirs (only a couple
        exist at any time thanks to MCP retention).
        """
        if os.path.dirname(name):
            return name if os.path.exists(name) else None
        matches = glob.glob(os.path.join(self._output_dir, "*", name))
        if not matches:
            return None
        matches.sort(key=os.path.getmtime)
        return matches[-1]

    def _emit_copy_segment(self, path: str, duration: float) -> None:
        """Emit one completed copy-backend segment with the standard payload."""
        start_time = self._segment_start_from_path(path) or datetime.now()
        end_time = start_time + timedelta(seconds=duration)
        payload: dict[str, Any] = {
            "recording_path": path,
            "recording_start": start_time.isoformat(timespec="seconds"),
            "recording_end": end_time.isoformat(timespec="seconds"),
            "duration_seconds": round(duration, 1),
            "file_size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        }
        self._sink.emit({
            "sourceId": self.source_id,
            "type": "recording",
            "timestamp": payload["recording_end"],
            "payload": payload,
        })
        logger.debug("[%s] Segment: %.1fs, %s", self.source_id, duration, path)

    def _segment_start_from_path(self, path: str) -> datetime | None:
        """Recover segment wall-clock start from `<date>/<source_id>_<HHMMSS>[_<suffix>].mp4`.

        The HHMMSS field is found by scanning underscore-separated fields from
        the right for the first all-digit 6-char one, so this handles the copy
        backend's `_<session_tag>` suffix (never all digits — it starts with
        "s") and the x264 backend's `_<ms>` suffix (3 digits) without needing to
        know which wrote the file. A `source_id` that itself ends in 6 digits is
        safe for the same reason: the scan stops at the rightmost match.
        """
        date_dir = os.path.basename(os.path.dirname(path))
        stem = os.path.splitext(os.path.basename(path))[0]
        for field in reversed(stem.split("_")):
            if len(field) == 6 and field.isdigit():
                try:
                    return datetime.strptime(f"{date_dir} {field}", "%Y-%m-%d %H%M%S")
                except ValueError:
                    return None
        return None

    def _ensure_date_dirs(self) -> None:
        """Pre-create today + tomorrow date dirs (ffmpeg won't mkdir at rollover)."""
        today = datetime.now().date()
        for day in (today, today + timedelta(days=1)):
            os.makedirs(
                os.path.join(self._output_dir, day.strftime("%Y-%m-%d")), exist_ok=True
            )

    def _cleanup_stale_lists(self, keep: str = "") -> None:
        """Remove segment-list files left behind by crashed sessions."""
        try:
            for name in os.listdir(self._output_dir):
                if name.startswith(".segments_") and not name.startswith(keep):
                    try:
                        os.remove(os.path.join(self._output_dir, name))
                    except OSError:
                        pass
        except OSError:
            pass

    @staticmethod
    def _read_log_tail(list_path: str, limit: int = 500) -> str:
        try:
            with open(list_path + ".log", "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 4096))
                return f.read().decode("utf-8", "replace")[-limit:].strip()
        except OSError:
            return ""

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
