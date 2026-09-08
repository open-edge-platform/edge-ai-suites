import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from utils.stage_events import StageEventWriter

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def stage_tracker(session_id, stage):
    """Wrap a pipeline stage: record start/end/duration/exception to both the
    log and the per-session stage_events.jsonl. One instrumentation point, two
    outlets. Re-raises on failure so the caller's error handling still runs.
    """
    started_at = _now_iso()
    t0 = time.monotonic()
    logger.info(f"[stage] {session_id} {stage} start")
    try:
        yield
    except Exception as e:
        duration = round(time.monotonic() - t0, 3)
        StageEventWriter.write(
            session_id, stage, "failed", started_at, _now_iso(), duration,
            error_class=type(e).__name__, error_detail=str(e),
        )
        logger.exception(f"[stage] {session_id} {stage} failed after {duration}s")
        raise
    else:
        duration = round(time.monotonic() - t0, 3)
        StageEventWriter.write(
            session_id, stage, "done", started_at, _now_iso(), duration,
        )
        logger.info(f"[stage] {session_id} {stage} done in {duration}s")
