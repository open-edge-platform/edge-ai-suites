import json
import logging
import os
import shutil
from pathlib import Path
from typing import Callable

from utils import session_store, orchestrator
from utils.pipeline_catalog import ALL_STAGES, FEATURE_STAGE, TERMINAL_SESSION_STATES
from utils.session_manager import is_generated_session_id
from utils.session_paths import SessionPaths
from api.v1.schemas.session import RegisterRequest, WorkflowRequest

logger = logging.getLogger(__name__)


class SessionNotFound(Exception):
    pass


class SessionRunning(Exception):
    pass


class SessionNotRunning(Exception):
    pass


class SessionNotCancellable(Exception):
    pass


class SessionValidationError(Exception):
    pass


class ConcurrencyLimitError(Exception):
    pass


class ArtifactNotFound(Exception):
    pass


# Stage outputs, list in run order
_STAGE_ARTIFACTS: dict[str, tuple[str, Callable[[str], Path]]] = {
    FEATURE_STAGE["asr"]: ("transcript", SessionPaths.transcript_path),
    FEATURE_STAGE["summary"]: ("markdown", SessionPaths.summary_path),
    # The .mmd source, not the report's PNG: the source is what the stage itself
    # wrote, so it is there for every session that got this far, and the preview
    # re-renders it live rather than showing a screenshot of an old layout.
    FEATURE_STAGE["mindmap"]: ("mindmap", SessionPaths.mindmap_path),
    FEATURE_STAGE["video_analytics"]: ("stats", SessionPaths.class_statistics_path),
    FEATURE_STAGE["topic_segmentation"]: ("topics", SessionPaths.topics_path),
    # The markdown, not the .docx or .pdf: those are for sending, and the
    # report screen already downloads them.
    FEATURE_STAGE["report"]: ("markdown", SessionPaths.report_md_path),
}

#: Cutoff for text artifacts. anything past this is not something a pop-up should be paging through
_TEXT_ARTIFACT_LIMIT = 2 * 1024 * 1024


def list_sessions(limit: int | None = None, offset: int = 0) -> dict:
    """Newest first. `total` is the whole table, not the page, so the history
    screen can page through it."""
    states = session_store.SessionStore.list_all(limit=limit, offset=offset)
    total = session_store.SessionStore.count() if limit is not None else len(states)
    return {"total": total, "sessions": [_summary(s) for s in states]}


def create_process(req: WorkflowRequest) -> dict:
    stages = req.stages or []
    if not stages:
        raise SessionValidationError("stages required")
    _validate_stages(stages)
    _validate_sources(req)
    try:
        session_id = orchestrator.start_process(req.model_dump())
    except orchestrator._ConcurrencyLimit as e:
        raise ConcurrencyLimitError(str(e))
    state = session_store.SessionStore.get(session_id)
    return {
        "session_id": session_id,
        "stages": state.get("stages") if state else stages,
        "output_dir": os.path.abspath(_session_dir(session_id)),
        "started_at": state.get("started_at") if state else None,
    }


def register_session(req: RegisterRequest) -> dict:
    """Record a session whose stages the caller runs itself.

    Nothing is started here - unlike create_process(), which hands the whole run
    to the orchestrator. The UI goes on calling /transcribe, /summarize and the
    rest one at a time; this only gives those stages a row to write to, so a
    UI-driven session shows up in the history with the same shape as an
    orchestrated one.
    """
    # The id is the caller's, and it becomes a directory name and the target of
    # DELETE /sessions/{id}. Accept only what this server itself minted.
    if not is_generated_session_id(req.session_id):
        raise SessionValidationError("session_id must be one issued by GET /create-session")
    stages = req.stages or []
    if not stages:
        raise SessionValidationError("stages required")
    _validate_stages(stages)

    existing = session_store.SessionStore.get(req.session_id)
    if existing is not None:
        # Idempotent: a retried POST must not rewind a session already underway.
        return _register_response(existing, already_registered=True)

    session_store.SessionStore.create(req.session_id, req.model_dump(), stages)
    state = session_store.SessionStore.update(req.session_id, state="running")
    return _register_response(state, already_registered=False)


def finalize_session(session_id: str, outcome: str, error: str | None = None) -> dict:
    # Close out a registered session. Refuses sessions the orchestrator owns.
    state = session_store.SessionStore.get(session_id)
    if state is None:
        raise SessionNotFound("session not found")
    if session_id in orchestrator.running_session_ids():
        raise SessionRunning("session is driven by the orchestrator; it finalizes itself")
    if state.get("state") in TERMINAL_SESSION_STATES:
        return {
            "session_id": session_id,
            "state": state.get("state"),
            "error": state.get("error"),
        }

    if outcome == "completed":
        state = session_store.SessionStore.mark_completed(session_id)
    else:
        # An aborted run is the same outcome as recover_after_restart() records:
        # over, unsuccessful, with a reason. No extra state to teach the UI.
        default = (
            "interrupted (client disconnected)" if outcome == "aborted" else "reported failed by client"
        )
        state = session_store.SessionStore.mark_failed(session_id, error or default)

    return {
        "session_id": session_id,
        "state": state.get("state"),
        "error": state.get("error"),
    }


def get_status(session_id: str) -> dict:
    state = session_store.SessionStore.get(session_id)
    if state is None:
        raise SessionNotFound("session not found")
    return _status_response(state)


def delete_session(session_id: str) -> dict:
    state = session_store.SessionStore.get(session_id)
    if state is None:
        raise SessionNotFound("session not found")
    if state.get("state") == "running":
        raise SessionRunning("session is running; cannot delete until it finishes")

    session_store.SessionStore.delete(session_id)

    session_dir = _session_dir(session_id)
    files_removed = False
    if os.path.isdir(session_dir):
        try:
            shutil.rmtree(session_dir)
            files_removed = True
        except OSError as e:
            logger.error(f"failed to remove session dir {session_dir}: {e}")
            raise RuntimeError(f"record deleted but failed to remove files: {e}")

    return {"session_id": session_id, "deleted": True, "files_removed": files_removed}


def cancel_session(session_id: str) -> dict:
    state = session_store.SessionStore.get(session_id)
    if state is None:
        raise SessionNotFound("session not found")
    if state.get("state") != "running":
        raise SessionNotRunning(f"session is not running (state={state.get('state')})")
    # Only the orchestrator has something to cancel, a UI-driven session has not.
    if not orchestrator.request_cancel(session_id):
        raise SessionNotCancellable(
            "session is not driven by the orchestrator; stop it where it was started"
        )
    session_store.SessionStore.update(session_id, cancel_requested=1)
    return {"session_id": session_id, "cancelled": True}


def list_running_sessions() -> dict:
    running = [
        s for s in session_store.SessionStore.list_all()
        if s.get("state") == "running"
    ]
    return {"total": len(running), "sessions": [_summary(s) for s in running]}


def get_stage_events(session_id: str) -> dict:
    """The per-stage timings behind a session, read back from its
    stage_events.jsonl. Timings are not in the database - the row carries the
    current status of each stage, this carries how long each one took and what
    it said when it broke."""
    state = session_store.SessionStore.get(session_id)
    if state is None:
        raise SessionNotFound("session not found")

    path = SessionPaths.stage_events_path(session_id)
    events = []
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        # A crash mid-append can leave a partial last line.
                        logger.warning(f"skipping malformed stage event in {path}")
        except OSError as e:
            logger.error(f"failed to read stage events for {session_id}: {e}")

    return {"session_id": session_id, "events": events}


def list_artifacts(session_id: str) -> dict:
    """The files this session's stages left behind that the history can open."""
    if session_store.SessionStore.get(session_id) is None:
        raise SessionNotFound("session not found")

    artifacts = []
    for stage, (kind, resolve) in _STAGE_ARTIFACTS.items():
        path = resolve(session_id)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        artifacts.append(
            {"stage": stage, "kind": kind, "filename": path.name, "size_bytes": size}
        )
    return {"session_id": session_id, "artifacts": artifacts}


def artifact_file(session_id: str, stage: str) -> tuple[str, Path]:
    """`(kind, path)` for one stage's artifact, checked to exist.

    Raises SessionNotFound for an unknown session and ArtifactNotFound for a
    stage with no preview or with nothing written - the caller cannot tell those
    apart, and does not need to: both mean there is nothing to show.
    """
    if session_store.SessionStore.get(session_id) is None:
        raise SessionNotFound("session not found")

    entry = _STAGE_ARTIFACTS.get(stage)
    if entry is None:
        raise ArtifactNotFound(f"stage {stage!r} has no previewable output")

    kind, resolve = entry
    path = resolve(session_id)
    if not path.is_file():
        raise ArtifactNotFound(f"no {stage} output on disk for session {session_id}")
    return kind, path


def read_text_artifact(session_id: str, stage: str) -> dict:
    """One stage's artifact, as text for the caller to lay out itself."""
    kind, path = artifact_file(session_id, stage)

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(_TEXT_ARTIFACT_LIMIT + 1)
    except OSError as e:
        logger.error(f"failed to read {stage} artifact for {session_id}: {e}")
        raise ArtifactNotFound(f"could not read {stage} output: {e}")

    truncated = len(content) > _TEXT_ARTIFACT_LIMIT
    return {
        "session_id": session_id,
        "stage": stage,
        "kind": kind,
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "content": content[:_TEXT_ARTIFACT_LIMIT],
        "truncated": truncated,
    }


def _summary(state: dict) -> dict:
    return {
        "session_id": state.get("session_id"),
        "state": state.get("state"),
        "current_stage": state.get("current_stage"),
        "stages": state.get("stages"),
        "sources": state.get("sources"),
        "error": state.get("error"),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
    }


def _validate_stages(stages: list) -> None:
    for s in stages:
        if s not in ALL_STAGES:
            raise SessionValidationError(f"unknown stage: {s}")


def _validate_sources(req: WorkflowRequest) -> None:
    transcribe = FEATURE_STAGE["asr"]
    if transcribe in req.stages:
        if not req.audio_path:
            raise SessionValidationError(f"stage {transcribe} requires audio_path")
        _check_file(req.audio_path, "audio_path")
    for name, source in (req.video_sources or {}).items():
        if source and not source.startswith("rtsp://"):
            _check_file(source, f"video_sources[{name}]")


def _check_file(path: str, field: str) -> None:
    if not os.path.isfile(path):
        raise SessionValidationError(f"{field} file not found: {path}")


def _session_dir(session_id: str) -> str:
    return str(SessionPaths.session_dir(session_id))


def _register_response(state: dict, already_registered: bool) -> dict:
    session_id = state.get("session_id")
    return {
        "session_id": session_id,
        "state": state.get("state"),
        "stages": state.get("stages"),
        "output_dir": os.path.abspath(_session_dir(session_id)),
        "started_at": state.get("started_at"),
        "already_registered": already_registered,
    }


def _status_response(state: dict) -> dict:
    return {
        "session_id": state.get("session_id"),
        "state": state.get("state"),
        "current_stage": state.get("current_stage"),
        "stages": state.get("stages"),
        "sources": state.get("sources"),
        "output_dir": os.path.abspath(_session_dir(state.get("session_id"))),
        "error": state.get("error"),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
    }
