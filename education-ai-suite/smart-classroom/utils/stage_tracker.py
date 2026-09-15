import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock

from utils.session_store import SessionStore
from utils.stage_events import StageEventWriter

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _store_stage(session_id, stage, status) -> None:
    """Mirror the stage transition onto the session row."""
    try:
        SessionStore.set_stage(session_id, stage, status)
    except Exception:
        logger.warning(
            f"[stage] {session_id} {stage}: failed to record '{status}' in the session store",
            exc_info=True,
        )


class StageHandle:
    """Escape hatch for stages that report failure in-band instead of raising.

    A streaming endpoint that catches its own errors and yields them as a payload
    (so the browser gets a message rather than a truncated response) leaves
    nothing for the context manager to see. Such a stage calls `fail(exc)` to say
    so explicitly; everyone else can ignore the handle.
    """

    def __init__(self):
        self.error = None

    def fail(self, exc) -> None:
        if self.error is None:
            self.error = exc


@contextmanager
def stage_tracker(session_id, stage):
    """Wrap a pipeline stage: record start/end/duration/exception to the log, to
    the per-session stage_events.jsonl and to the session store. One
    instrumentation point, three outlets. Re-raises on failure so the caller's
    error handling still runs.
    """
    started_at = _now_iso()
    t0 = time.monotonic()
    logger.info(f"[stage] {session_id} {stage} start")
    _store_stage(session_id, stage, "running")
    handle = StageHandle()
    try:
        yield handle
    except Exception as e:
        _finish(session_id, stage, "failed", started_at, t0, e)
        raise
    except BaseException as e:
        # GeneratorExit and asyncio.CancelledError land here: the HTTP client hung
        # up part-way through a streaming stage, or the server is shutting down.
        _finish(session_id, stage, "interrupted", started_at, t0, e)
        raise
    else:
        if handle.error is None:
            _finish(session_id, stage, "done", started_at, t0, None)
        else:
            _finish(session_id, stage, "failed", started_at, t0, handle.error)


def _finish(session_id, stage, status, started_at, t0, exc) -> None:
    duration = round(time.monotonic() - t0, 3)
    if exc is None:
        StageEventWriter.write(session_id, stage, status, started_at, _now_iso(), duration)
        logger.info(f"[stage] {session_id} {stage} done in {duration}s")
    else:
        StageEventWriter.write(
            session_id, stage, status, started_at, _now_iso(), duration,
            error_class=type(exc).__name__, error_detail=str(exc),
        )
        if status == "failed":
            # exc_info=exc rather than logger.exception(): a stage that reported
            # its failure through StageHandle is not inside an except block.
            logger.error(
                f"[stage] {session_id} {stage} failed after {duration}s", exc_info=exc
            )
        else:
            # A disconnect is routine; record it without the traceback noise.
            logger.info(
                f"[stage] {session_id} {stage} interrupted after {duration}s "
                f"({type(exc).__name__})"
            )
    _store_stage(session_id, stage, status)


_MANUAL_STARTS: dict[tuple, tuple] = {}
_MANUAL_LOCK = Lock()


def stage_started(session_id, stage) -> None:
    """Open a stage whose start and end land in different requests."""
    with _MANUAL_LOCK:
        _MANUAL_STARTS[(session_id, stage)] = (_now_iso(), time.monotonic())
    logger.info(f"[stage] {session_id} {stage} start")
    _store_stage(session_id, stage, "running")


def stage_finished(session_id, stage, status, error_class=None, error_detail=None) -> None:
    """Close out a stage opened with stage_started()."""
    with _MANUAL_LOCK:
        started_at, t0 = _MANUAL_STARTS.pop((session_id, stage), (None, None))
    duration = round(time.monotonic() - t0, 3) if t0 is not None else None
    StageEventWriter.write(
        session_id, stage, status, started_at, _now_iso(), duration,
        error_class=error_class, error_detail=error_detail,
    )
    logger.info(
        f"[stage] {session_id} {stage} {status}"
        + (f" in {duration}s" if duration is not None else "")
    )
    _store_stage(session_id, stage, status)
