import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from utils.config_loader import config

logger = logging.getLogger(__name__)

# Board OCR processing status returned to the /board-ocr/ocr endpoint.
STATUS_NOT_STARTED = "not_started"                     # nothing running, no file
STATUS_FRAME_EXTRACTION = "frame_extraction_in_progress"  # extracting frames
STATUS_OCR = "ocr_in_progress"                         # extraction done, OCR draining
STATUS_DONE = "done"                                   # all frames extracted and OCR'd

_board_ocr_warned = False


def board_ocr_enabled() -> bool:
    """Whether board OCR is enabled in config."""
    global _board_ocr_warned

    board_cfg = getattr(config, "board_ocr", None)
    if not board_cfg or not bool(getattr(board_cfg, "enabled", False)):
        return False

    ocr_cfg = getattr(config.models, "ocr", None)
    if ocr_cfg and bool(getattr(ocr_cfg, "enabled", False)):
        return True

    if not _board_ocr_warned:
        logger.warning(
            "board_ocr.enabled is true but models.ocr.enabled is false; "
            "board OCR will be SKIPPED. Set models.ocr.enabled: true to use it."
        )
        _board_ocr_warned = True
    return False


def _board_ocr_debug() -> bool:
    """Whether board OCR debug mode is enabled (keeps intermediate artifacts)."""
    board_cfg = getattr(config, "board_ocr", None)
    return bool(getattr(board_cfg, "debug", False)) if board_cfg else False


def va_pipeline_enabled() -> bool:
    """Whether the VA pipeline is enabled.

    Board OCR sources its video from the VA content pipeline, so it can only run
    when the VA pipeline is enabled. There is no `va_pipeline.enabled` flag today;
    it defaults to True for forward compatibility with a future on/off switch.
    """
    va_cfg = getattr(config, "va_pipeline", None)
    if va_cfg is None:
        return True
    return bool(getattr(va_cfg, "enabled", True))


# ---------------------------------------------------------------------------
# Frame Extractor (FFmpeg + Intel QSV)
# ---------------------------------------------------------------------------

class FrameExtractor:
    """Extract frames from an RTSP stream or video file using FFmpeg + Intel QSV."""

    def __init__(self, source: str, output_dir: Path):
        self.source = source
        self.input_source = self._prepare_input_source(source)
        self.output_dir = Path(output_dir)
        self.log_path = self.output_dir.parent / "frame_extractor.log"
        board_cfg = getattr(config, "board_ocr", None)
        self.frame_interval = str(getattr(board_cfg, "frame_rate", "1/3") or "1/3").strip()

        self._process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._log_fh = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> bool:
        """Launch FFmpeg to extract frames. Returns True if started successfully."""
        if self.is_running:
            logger.warning("Frame extractor already running")
            return True

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()

        cmd = self._build_command()
        logger.info(f"Starting frame extractor: {' '.join(cmd)}")

        # ffmpeg writes all of its output (progress + errors) to stderr; send it
        # straight to frame_extractor.log instead of the console.
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_fh = open(self.log_path, "w", encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not open frame extractor log {self.log_path}: {e}")
            self._log_fh = None

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=self._log_fh or subprocess.DEVNULL,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )
        except FileNotFoundError:
            logger.error("ffmpeg not found on PATH")
            return False
        except Exception as e:
            logger.error(f"Failed to start frame extractor: {e}")
            return False

        self._monitor_thread = threading.Thread(
            target=self._monitor, daemon=True, name="frame-extractor-monitor"
        )
        self._monitor_thread.start()

        logger.info(
            f"Frame extractor started (pid={self._process.pid}, "
            f"source={self.input_source}, interval={self.frame_interval})"
        )
        return True

    def _prepare_input_source(self, source: str) -> str:
        """Normalize local file paths before passing them to FFmpeg."""
        src = (source or "").strip()
        if len(src) >= 2 and src[0] == src[-1] and src[0] in {'"', "'"}:
            src = src[1:-1].strip()

        lowered = src.lower()
        if lowered.startswith(("rtsp://", "http://", "https://", "file://")):
            return src
    
        expanded = Path(os.path.expandvars(os.path.expanduser(src)))
        candidate = expanded.resolve() if expanded.is_absolute() else (Path.cwd() / expanded).resolve()

        if not candidate.exists():
            logger.error(f"Board OCR source path does not exist: {candidate}")
            return str(candidate)

        if candidate.is_dir():
            logger.error(f"Board OCR source must be a file, not a directory: {candidate}")
            return str(candidate)
        result = f"file:{candidate.as_posix()}"
        return result

    def stop(self, timeout: float = 10.0):
        """Stop the FFmpeg process gracefully."""
        self._stop_event.set()

        if self._process is None:
            return

        if self._process.poll() is not None:
            self._process = None
            return

        try:
            if sys.platform == "win32":
                import signal
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()

            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Frame extractor did not stop in time, killing")
            self._process.kill()
            self._process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error stopping frame extractor: {e}")

        self._process = None

        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=3.0)
            self._monitor_thread = None

        logger.info("Frame extractor stopped")

    def _build_command(self) -> list:
        """Build the FFmpeg command with Intel QSV hardware decode."""
        is_rtsp = self.source.startswith("rtsp://")

        cmd = ["ffmpeg", "-y"]

        if is_rtsp:
            cmd += ["-rtsp_transport", "tcp"]

        cmd += [
            "-hwaccel", "qsv",
            "-hwaccel_output_format", "qsv",
            "-i", self.input_source,
        ]

        output_pattern = (self.output_dir / "frame_%06d.jpg").as_posix()
        cmd += [
            "-vf", f"hwdownload,format=nv12,fps={self.frame_interval}",
            "-qscale:v", "2",
            "-update", "0",
            output_pattern,
        ]

        return cmd

    def _monitor(self):
        """Wait for ffmpeg to exit and report an unexpected failure.

        ffmpeg's output is written directly to frame_extractor.log (see start()).
        This just waits for the process to end and, unless we asked it to stop,
        logs an error with the exit code pointing at the log for details.
        """
        proc = self._process
        if proc is None:
            return

        ret = proc.wait()
        if self._log_fh is not None:
            self._log_fh.close()
            self._log_fh = None

        if not self._stop_event.is_set() and ret != 0:
            logger.error(
                f"Frame extractor exited unexpectedly (code={ret}); "
                f"see {self.log_path} for details."
            )


# ---------------------------------------------------------------------------
# OCR Worker (dedup + OCR + confidence gate)
# ---------------------------------------------------------------------------

# Tuning constants for the OCR worker.
_DEDUP_RESIZE = (256, 256)      # thumbnail size for duplicate detection
_DEDUP_PIXEL_DIFF = 25          # per-pixel gray delta that counts as "changed"
_DEDUP_CHANGED_FRAC = 0.001     # keep frame if more than this fraction changed
_MIN_MEAN_CONFIDENCE = 0.6      # drop frames whose mean OCR confidence is below this
_BACKLOG_WARN = 60              # warn when this many frames are pending
_POLL_INTERVAL = 0.5            # seconds between polls when no frames are pending

# Tuning constants for the text-cleaning pass (token saving for downstream LLM).
_CLEAN_SIMILARITY = 0.80        # adjacent records at/above this text ratio are merged
_CLEAN_CONTAINMENT = 0.90       # fraction of shorter text found in the other to treat as write/erase noise


class BoardOCRWorker:
    """Background worker that OCRs tapped board / content-screen frames."""

    def __init__(
        self,
        frames_dir: Path,
        output_file: Path,
        provider: str,
        device: str,
        lang: str,
        session_id: str,
        extractor: Optional["FrameExtractor"] = None,
    ):
        self.frames_dir = Path(frames_dir)
        self.output_file = Path(output_file)
        self.provider = provider
        self.device = device
        self.lang = lang
        self.session_id = session_id
        self._extractor = extractor

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ocr = None
        self._last_kept_thumb: Optional[np.ndarray] = None
        self._frame_count = 0
        self._finalized = False
        self._finalize_lock = threading.Lock()

    def start(self) -> bool:
        """Start the worker thread. Returns False if OCR model init fails."""
        try:
            from model_manager import ModelManager

            self._ocr = ModelManager.instance().ocr()
            self._ocr.load()
        except Exception as e:
            logger.error(f"Failed to init OCR model, disabling board OCR: {e}")
            return False

        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="board-ocr-worker"
        )
        self._thread.start()
        logger.info(
            f"Board OCR worker started (provider={self.provider}, device={self.device}, "
            f"frames_dir={self.frames_dir})"
        )
        return True

    def stop(self, timeout: float = 5.0):
        """Signal the worker to stop, join the thread, and clean the output."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._finalize()

    def _finalize(self) -> None:
        """Run the output-cleaning pass exactly once (idempotent).

        Called both when the worker finishes on its own (extraction ended and
        the backlog drained) and when it is stopped externally by the content
        pipeline's EOS/stop. The guard ensures the cleaning runs only once.
        """
        with self._finalize_lock:
            if self._finalized:
                return
            self._finalized = True
        try:
            self.clean_output()
        except Exception as e:
            logger.error(f"Board OCR cleaning failed: {e}")

    def has_pending_frames(self) -> bool:
        """True if there are extracted frames still waiting to be OCR'd."""
        try:
            return any(self.frames_dir.glob("frame_*.jpg"))
        except Exception:
            return False

    def _thumbnail(self, img: np.ndarray) -> np.ndarray:
        return np.array(
            Image.fromarray(img).resize(_DEDUP_RESIZE).convert("L"),
            dtype=np.float32,
        )

    def _is_duplicate(self, img: np.ndarray) -> bool:
        thumb = self._thumbnail(img)
        if self._last_kept_thumb is None:
            self._last_kept_thumb = thumb
            return False
        changed_frac = float(
            np.mean(np.abs(thumb - self._last_kept_thumb) > _DEDUP_PIXEL_DIFF)
        )
        if changed_frac <= _DEDUP_CHANGED_FRAC:
            return True
        self._last_kept_thumb = thumb
        return False

    def _extraction_ended(self) -> bool:
        """True once the ffmpeg extraction process is no longer running.
        """
        if self._extractor is None:
            return False
        return not self._extractor.is_running

    def _run(self):
        while not self._stop.is_set():
            try:
                frames = sorted(self.frames_dir.glob("frame_*.jpg"))
            except Exception as e:
                logger.warning(f"Failed to list frames: {e}")
                frames = []

            if not frames:
                # ffmpeg has exited and the backlog is fully drained: the worker
                # is done, so clean the output and exit on its own instead of
                # idling until the content pipeline stops it.
                if self._extraction_ended() and not self.has_pending_frames():
                    logger.info(
                        "Board OCR: extraction ended and backlog drained; finishing"
                    )
                    break
                time.sleep(_POLL_INTERVAL)
                continue

            if len(frames) >= _BACKLOG_WARN:
                logger.warning(
                    f"{len(frames)} frames pending (backlog); OCR is lagging real time or full-speed local file frame extraction."
                )

            for frame_path in frames:
                if self._stop.is_set():
                    return
                self._process_frame(frame_path)

        logger.info("Board OCR worker stopped")
        self._finalize()

    def _process_frame(self, frame_path: Path):
        try:
            with Image.open(frame_path) as im:
                img = np.array(im.convert("RGB"))
        except Exception as e:
            logger.debug(f"Skip unreadable frame {frame_path.name}: {e}")
            time.sleep(_POLL_INTERVAL)
            return

        try:
            if self._is_duplicate(img):
                logger.debug(f"Duplicate frame skipped {frame_path.name}")
                return

            text, scores = self._ocr.extract_text_with_scores(str(frame_path))

            if scores:
                mean_conf = sum(scores) / len(scores)
                if mean_conf < _MIN_MEAN_CONFIDENCE:
                    logger.info(
                        f"Low-confidence frame skipped {frame_path.name} "
                        f"(mean_conf={mean_conf:.3f} < {_MIN_MEAN_CONFIDENCE}, "
                        f"{len(scores)} lines)"
                    )
                    return
            else:
                mean_conf = 0.0

            self._frame_count += 1
            record = {
                "frame": self._frame_count,
                "source_frame": frame_path.name,
                "timestamp": int(time.time()),
                "text": text or "",
            }
            self._append_result(record)
            logger.debug(
                f"OCR'd {frame_path.name} ({len(text or '')} chars, "
                f"mean_conf={mean_conf:.3f})"
            )
        except Exception as e:
            logger.error(f"OCR failed for {frame_path.name}: {e}")
        finally:
            try:
                frame_path.unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Failed to delete {frame_path.name}: {e}")

    def _append_result(self, record: dict):
        try:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write result: {e}")

    # -----------------------------------------------------------------------
    # Post-processing: clean board_ocr.txt for token-efficient LLM usage
    # -----------------------------------------------------------------------

    def clean_output(self) -> Optional[Path]:
        """Post-process board_ocr.txt in place for token-efficient LLM usage.

        As the teacher writes on and erases the board, consecutive frames yield
        many near-identical OCR records. Feeding all of them to an LLM wastes
        tokens, so this pass collapses the redundancy. Two cases are handled:

        1. Write/erase noise: while a line is being written (or partially
           erased and rewritten) the OCR text grows/shrinks but carries the
           same net meaning. When one record's text is largely contained in an
           adjacent one, only the most complete version is kept.

        2. Minor changes / near-same meaning: adjacent records whose text is
           highly similar (but not strictly containing) are merged, keeping the
           later, usually more complete, version.

        The cleaned content overwrites ``board_ocr.txt``. When board OCR debug
        is enabled (``board_ocr.debug: true``), the original, uncleaned content
        is first preserved next to it as ``board_ocr_raw.txt``. Returns the path
        of the cleaned file (or None if there was nothing to clean).

        NOTE: These are intentionally simple, dependency-free heuristics — a
        placeholder to be swapped for a smarter (e.g. embedding/LLM based)
        deduplicator later.
        """
        records = self._read_records()
        if not records:
            return None

        cleaned: list[dict] = []
        for rec in records:
            text = (rec.get("text") or "").strip()
            if not text:
                continue

            if cleaned:
                prev = cleaned[-1]
                prev_text = prev.get("text") or ""
                if self._is_write_erase_noise(prev_text, text):
                    # Case 1: keep whichever version is more complete.
                    if len(text) >= len(prev_text):
                        cleaned[-1] = rec
                    continue
                if self._is_minor_change(prev_text, text):
                    # Case 2: near-same meaning; keep the later version.
                    cleaned[-1] = rec
                    continue

            cleaned.append(rec)

        for idx, rec in enumerate(cleaned, start=1):
            rec["frame"] = idx

        if _board_ocr_debug():
            raw_path = self.output_file.with_name(self.output_file.stem + "_raw" + self.output_file.suffix)
            try:
                shutil.copyfile(self.output_file, raw_path)
                logger.info(f"Board OCR debug: original saved to {raw_path.name}")
            except Exception as e:
                logger.warning(f"Failed to save raw board OCR file: {e}")

        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                for rec in cleaned:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write cleaned board OCR file: {e}")
            return None

        logger.info(
            f"Board OCR cleaned: {len(records)} -> {len(cleaned)} records "
            f"({self.output_file.name})"
        )
        return self.output_file

    def _read_records(self) -> list:
        records = []
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.debug(f"Skip non-JSON line in {self.output_file.name}")
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.warning(f"Failed to read {self.output_file}: {e}")
            return []
        return records

    @staticmethod
    def _is_write_erase_noise(a: str, b: str) -> bool:
        """True if one text is largely contained in the other (write/erase noise)."""
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if not shorter:
            return True
        matcher = SequenceMatcher(None, shorter, longer)
        matched = sum(block.size for block in matcher.get_matching_blocks())
        return (matched / len(shorter)) >= _CLEAN_CONTAINMENT

    @staticmethod
    def _is_minor_change(a: str, b: str) -> bool:
        """True if two texts are highly similar overall (minor change / same meaning)."""
        if not a or not b:
            return False
        return SequenceMatcher(None, a, b).ratio() >= _CLEAN_SIMILARITY



# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class BoardOCRPipeline:
    """Self-contained board OCR pipeline: FFmpeg frame extraction + OCR worker.

    It is a "twin" of the VA content pipeline: it consumes the same video source
    and produces board_ocr.txt for the session. Lifecycle is driven entirely by
    the module-level controller (start_board_ocr / stop_board_ocr).

    Usage:
        pipeline = BoardOCRPipeline(source, session_id, output_dir)
        pipeline.start()
        ...
        pipeline.stop()
    """

    def __init__(self, source: str, session_id: str, output_dir: Path):
        self.source = source
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self._extractor: Optional[FrameExtractor] = None
        self._worker: Optional[BoardOCRWorker] = None

    @property
    def is_running(self) -> bool:
        return self._extractor is not None and self._extractor.is_running

    def status(self) -> str:
        """Which step the pipeline is on.

        - STATUS_FRAME_EXTRACTION: FFmpeg is still pulling frames from the source
        - STATUS_OCR: extraction finished, OCR worker is draining pending frames
        - STATUS_DONE: extraction finished and no frames remain to OCR
        """
        if self._extractor is None:
            return STATUS_DONE
        if self._extractor.is_running:
            return STATUS_FRAME_EXTRACTION
        if self._worker is not None and self._worker.has_pending_frames():
            return STATUS_OCR
        return STATUS_DONE

    def start(self) -> bool:
        """Start frame extraction and OCR worker. Returns False if it can't start."""
        if not self.source:
            logger.error("Board OCR has no video source; not starting.")
            return False

        frames_dir = self.output_dir / "frames"
        ocr_output = self.output_dir / "board_ocr.txt"

        self._extractor = FrameExtractor(
            source=self.source,
            output_dir=frames_dir,
        )
        if not self._extractor.start():
            logger.error("Failed to start frame extractor")
            return False

        ocr_cfg = config.models.ocr
        self._worker = BoardOCRWorker(
            frames_dir=frames_dir,
            output_file=ocr_output,
            provider=getattr(ocr_cfg, "provider", "openvino"),
            device=getattr(ocr_cfg, "device", "CPU"),
            lang=getattr(ocr_cfg, "lang", "en"),
            session_id=self.session_id,
            extractor=self._extractor,
        )
        if not self._worker.start():
            logger.error("Failed to start OCR worker, stopping frame extractor")
            self._extractor.stop()
            return False

        logger.info(f"Board OCR pipeline started for session {self.session_id}")
        return True

    def stop(self):
        """Stop both the OCR worker and frame extractor."""
        if self._worker is not None:
            self._worker.stop()
            self._worker = None

        if self._extractor is not None:
            self._extractor.stop()
            self._extractor = None

        logger.info(f"Board OCR pipeline stopped for session {self.session_id}")


# ---------------------------------------------------------------------------
# Controller — at most one active board OCR pipeline (twin of content pipeline)
# ---------------------------------------------------------------------------

_controller_lock = threading.Lock()
_active_pipeline: Optional["BoardOCRPipeline"] = None


def default_board_ocr_output_dir(session_id: str) -> Path:
    """<Project.location>/<Project.name>/<session_id>/board_ocr"""
    from utils.runtime_config_loader import RuntimeConfig

    project_config = RuntimeConfig.get_section("Project")
    return Path(
        project_config.get("location"),
        project_config.get("name"),
        session_id,
        "board_ocr",
    )


def _configured_source() -> str:
    board_cfg = getattr(config, "board_ocr", None)
    if not board_cfg:
        return ""
    return (getattr(board_cfg, "source", "") or "").strip()


def _resolve_source(content_source: Optional[str]) -> str:
    """Board OCR reuses the content pipeline's source. An explicit
    board_ocr.source in config overrides it (e.g. a dedicated board camera)."""
    return _configured_source() or (content_source or "").strip()


def get_active_session_id() -> Optional[str]:
    """Return the session_id of the pipeline currently owning board_ocr.txt."""
    with _controller_lock:
        return _active_pipeline.session_id if _active_pipeline else None


def start_board_ocr(session_id: str, content_source: Optional[str]) -> bool:
    """Start the board OCR twin pipeline for a content pipeline.

    Called from endpoints.py when the VA content pipeline starts. Idempotent.
    No-op (with a log line) when board OCR or the VA pipeline is disabled.
    """
    if not board_ocr_enabled():
        logger.info("Board OCR disabled in config; not starting")
        return False

    global _active_pipeline

    if not va_pipeline_enabled():
        logger.warning(
            "board_ocr.enabled is true but the VA pipeline is not enabled; "
            "the content source is unavailable, so board OCR will NOT start."
        )
        return False

    if not session_id:
        logger.error("Board OCR needs a session_id to start; skipping")
        return False

    source = _resolve_source(content_source)
    if not source:
        logger.error(
            "Board OCR has no video source (no content source and empty "
            "board_ocr.source); not starting."
        )
        return False

    with _controller_lock:
        if (
            _active_pipeline is not None
            and _active_pipeline.session_id == session_id
            and _active_pipeline.is_running
        ):
            return True
        _stop_locked()

        out_dir = default_board_ocr_output_dir(session_id)
        pipe = BoardOCRPipeline(source=source, session_id=session_id, output_dir=out_dir)
        if not pipe.start():
            return False
        _active_pipeline = pipe
        logger.info(f"Board OCR controller: started (session={session_id})")
        return True


def stop_board_ocr(session_id: Optional[str] = None) -> None:
    """Stop the board OCR twin pipeline.

    Called from endpoints.py when the VA content pipeline stops or reaches EOS.
    If `session_id` is given, only stops when it matches the active pipeline.
    """
    with _controller_lock:
        if _active_pipeline is None:
            return
        if session_id and _active_pipeline.session_id != session_id:
            return
        _stop_locked()


def _stop_locked() -> None:
    """Assumes _controller_lock is held. Stops any active pipeline."""
    global _active_pipeline
    if _active_pipeline is not None:
        try:
            _active_pipeline.stop()
        except Exception as e:
            logger.error(f"Error stopping board OCR pipeline: {e}")
        _active_pipeline = None


def get_status(session_id: str) -> str:
    """Return processing status for `session_id`'s board_ocr.txt:

    - STATUS_FRAME_EXTRACTION — pipeline running, still extracting frames
    - STATUS_OCR              — extraction finished, OCR worker draining frames
    - STATUS_DONE             — finished (or not running) and board_ocr.txt exists
    - STATUS_NOT_STARTED      — no pipeline for this session and no file
    """
    with _controller_lock:
        if (
            _active_pipeline is not None
            and _active_pipeline.session_id == session_id
        ):
            return _active_pipeline.status()

    out_file = default_board_ocr_output_dir(session_id) / "board_ocr.txt"
    return STATUS_DONE if out_file.exists() else STATUS_NOT_STARTED
