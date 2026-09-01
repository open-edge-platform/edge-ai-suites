import logging
import os
import shutil

from utils import session_store, orchestrator
from utils.session_paths import SessionPaths
from api.v1.schemas.session import WorkflowRequest

logger = logging.getLogger(__name__)


class SessionNotFound(Exception):
    pass


class SessionRunning(Exception):
    pass


class SessionNotRunning(Exception):
    pass


class SessionValidationError(Exception):
    pass


class ConcurrencyLimitError(Exception):
    pass


def list_sessions() -> dict:
    sessions = []
    for state in session_store.SessionStore.list_all():
        sessions.append(
            {
                "session_id": state.get("session_id"),
                "state": state.get("state"),
                "current_stage": state.get("current_stage"),
                "stages": state.get("stages"),
                "sources": state.get("sources"),
                "started_at": state.get("started_at"),
                "updated_at": state.get("updated_at"),
            }
        )
    return {"total": len(sessions), "sessions": sessions}


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
    orchestrator.request_cancel(session_id)
    session_store.SessionStore.update(session_id, cancel_requested=1)
    return {"session_id": session_id, "cancelled": True}


def list_running_sessions() -> dict:
    sessions = []
    for state in session_store.SessionStore.list_all():
        if state.get("state") != "running":
            continue
        sessions.append(
            {
                "session_id": state.get("session_id"),
                "state": state.get("state"),
                "current_stage": state.get("current_stage"),
                "stages": state.get("stages"),
                "sources": state.get("sources"),
                "started_at": state.get("started_at"),
                "updated_at": state.get("updated_at"),
            }
        )
    return {"total": len(sessions), "sessions": sessions}


def _validate_stages(stages: list) -> None:
    from utils.session_store import _ALL_STAGES
    for s in stages:
        if s not in _ALL_STAGES:
            raise SessionValidationError(f"unknown stage: {s}")


def _validate_sources(req: WorkflowRequest) -> None:
    if "transcribe" in req.stages:
        if not req.audio_path:
            raise SessionValidationError("stage transcribe requires audio_path")
        _check_file(req.audio_path, "audio_path")
    for name, source in (req.video_sources or {}).items():
        if source and not source.startswith("rtsp://"):
            _check_file(source, f"video_sources[{name}]")


def _check_file(path: str, field: str) -> None:
    if not os.path.isfile(path):
        raise SessionValidationError(f"{field} file not found: {path}")


def _session_dir(session_id: str) -> str:
    return str(SessionPaths.session_dir(session_id))


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
