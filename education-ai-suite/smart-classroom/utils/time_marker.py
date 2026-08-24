# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Wall-clock stage markers for end-to-end timing analysis.

Emits one INFO line per pipeline milestone with an ISO-8601 local timestamp
(``2026-03-27T14:38:33.125``) so a full session timeline can be reconstructed from
the backend log with a single ``grep``:

    grep "\\[STAGE\\]" backend.log

Every marker is also appended to that session's
``utilization_logs/stage_timeline.csv``. Markers that pass ``stage`` +
``boundary`` delimit a monitored stage window, which ``monitoring.stage_metrics``
uses to slice the raw utilization series into per-stage CPU/GPU/NPU/memory
figures; all others are recorded with the ``info`` boundary so their timestamp
is preserved without moving any window.

Upload markers are queued until ``/transcribe`` explicitly binds them to the
session it creates. Other markers without a session id remain in the backend
log only.
"""

import logging
import threading
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
MARKER_PREFIX = "[STAGE]"
_pending_uploads = deque(maxlen=8)
_pending_lock = threading.Lock()

def now_stamp() -> str:
    """Return the current local time with millisecond precision."""
    return datetime.now().strftime(TIME_FORMAT)[:-3]


def mark(event: str, session_id: str = None, stage: str = None, boundary: str = None) -> str:
    """Log ``event`` with the current timestamp and return that timestamp.

    Args:
        event: Marker text, e.g. ``"audio pipeline-ASR-started"``.
        session_id: Session owning the marker. Without one, the marker is logged
            but not written to a session timeline.
        stage: Monitored stage this marker relates to (``monitoring.stage_metrics``
            stage names: ``ASR``, ``Summary``, ``Mind map``, ``Video``).
        boundary: ``"start"`` or ``"end"`` to delimit that stage's window;
            defaults to ``"info"``, which records the timestamp only.
    """
    stamp = now_stamp()
    logger.info("%s %s %s", MARKER_PREFIX, event, stamp)
    _record(event, stage, boundary, stamp, session_id)
    return stamp


def mark_pending_upload(event: str) -> str:
    """Log and queue an upload marker until the next transcribe session binds it."""
    stamp = now_stamp()
    logger.info("%s %s %s", MARKER_PREFIX, event, stamp)
    with _pending_lock:
        if event == "upload-audio-started":
            _pending_uploads.clear()
        _pending_uploads.append((event, stamp))
    return stamp


def flush_pending_uploads(session_id: str) -> None:
    """Write queued upload markers to the explicitly supplied session."""
    with _pending_lock:
        rows = tuple(_pending_uploads)
        _pending_uploads.clear()
    for event, stamp in rows:
        _record(event, None, None, stamp, session_id)


def _record(event: str, stage: str, boundary: str, stamp: str, session_id: str) -> None:
    """Append the marker to its session timeline when a session is known."""
    if not session_id:
        return

    try:
        # Imported lazily: keeps this module free of monitoring/config imports
        # for callers that only want a log line.
        from monitoring.stage_metrics import BOUNDARY_INFO, record_stage_event
        from utils.artifacts.path import get_artifact_path

        metrics_logs = get_artifact_path(session_id, "utilization_logs")
        record_stage_event(
            metrics_logs,
            stage or "",
            boundary or BOUNDARY_INFO,
            event,
            stamp,
        )
    except Exception as e:
        # Instrumentation must never break the pipeline it measures.
        logger.error("Failed to record stage event '%s': %s", event, e)
