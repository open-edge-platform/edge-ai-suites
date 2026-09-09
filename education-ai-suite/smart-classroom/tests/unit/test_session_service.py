import os
import tempfile
from unittest.mock import patch

from api.v1.schemas.session import WorkflowRequest
from services.session_service import (
    ConcurrencyLimitError,
    SessionNotFound,
    SessionNotRunning,
    SessionRunning,
    SessionValidationError,
    cancel_session,
    create_process,
    delete_session,
    get_status,
    list_running_sessions,
    list_sessions,
)
from services import session_service


def _expect_raises(exc, fn):
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def _req(**kw):
    defaults = {
        "stages": ["transcribe"],
        "audio_path": "/tmp/unused.wav",
        "video_sources": None,
    }
    defaults.update(kw)
    return WorkflowRequest(**defaults)


def test_create_process_rejects_empty_stages():
    _expect_raises(SessionValidationError, lambda: create_process(_req(stages=[])))


def test_create_process_rejects_unknown_stage():
    _expect_raises(SessionValidationError, lambda: create_process(_req(stages=["bogus"])))


def test_create_process_rejects_missing_audio_for_transcribe():
    _expect_raises(SessionValidationError, lambda: create_process(_req(audio_path=None)))


def test_create_process_rejects_nonexistent_audio():
    with tempfile.TemporaryDirectory() as tmp:
        missing = os.path.join(tmp, "nope.wav")
        _expect_raises(
            SessionValidationError, lambda: create_process(_req(audio_path=missing))
        )


def test_create_process_calls_orchestrator():
    with tempfile.TemporaryDirectory() as tmp:
        audio = os.path.join(tmp, "a.wav")
        open(audio, "w").close()
        with patch.object(session_service, "orchestrator") as mo, patch.object(
            session_service.session_store.SessionStore, "get"
        ) as mget:
            mo.start_process.return_value = "sess-1"
            mget.return_value = {"stages": {"transcribe": "pending"}, "started_at": "now"}
            result = create_process(_req(audio_path=audio))
            assert result["session_id"] == "sess-1"
            assert mo.start_process.called


def test_create_process_maps_concurrency_limit():
    from utils import orchestrator as orch
    with tempfile.TemporaryDirectory() as tmp:
        audio = os.path.join(tmp, "a.wav")
        open(audio, "w").close()
        with patch.object(
            session_service.orchestrator, "start_process",
            side_effect=orch._ConcurrencyLimit("too many concurrent sessions"),
        ):
            _expect_raises(ConcurrencyLimitError, lambda: create_process(_req(audio_path=audio)))


def test_get_status_not_found():
    with patch.object(
        session_service.session_store.SessionStore, "get", return_value=None
    ):
        _expect_raises(SessionNotFound, lambda: get_status("nope"))


def test_get_status_returns_state():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(
            session_service.session_store.SessionStore, "get"
        ) as mget, patch.object(session_service, "_session_dir", return_value=tmp):
            mget.return_value = {
                "session_id": "s1",
                "state": "completed",
                "current_stage": "va",
                "stages": {"va": "done"},
                "sources": {},
                "error": None,
                "started_at": "t0",
                "updated_at": "t1",
            }
            result = get_status("s1")
            assert result["state"] == "completed"
            assert result["output_dir"] == os.path.abspath(tmp)


def test_list_sessions():
    with patch.object(
        session_service.session_store.SessionStore, "list_all"
    ) as mlist:
        mlist.return_value = [{"session_id": "s1", "state": "completed"}]
        result = list_sessions()
        assert result["total"] == 1
        assert result["sessions"][0]["session_id"] == "s1"


def test_delete_not_found():
    with patch.object(
        session_service.session_store.SessionStore, "get", return_value=None
    ):
        _expect_raises(SessionNotFound, lambda: delete_session("nope"))


def test_delete_rejects_running():
    with patch.object(
        session_service.session_store.SessionStore, "get",
        return_value={"state": "running"},
    ):
        _expect_raises(SessionRunning, lambda: delete_session("s1"))


def test_delete_removes_dir():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(
            session_service.session_store.SessionStore, "get",
            return_value={"state": "completed"},
        ), patch.object(
            session_service.session_store.SessionStore, "delete", return_value=True
        ), patch.object(session_service, "_session_dir", return_value=tmp):
            marker = os.path.join(tmp, "f.txt")
            open(marker, "w").close()
            result = delete_session("s1")
            assert result["deleted"] is True
            assert result["files_removed"] is True
            assert not os.path.exists(tmp)


def test_cancel_not_found():
    with patch.object(
        session_service.session_store.SessionStore, "get", return_value=None
    ):
        _expect_raises(SessionNotFound, lambda: cancel_session("nope"))


def test_cancel_rejects_non_running():
    with patch.object(
        session_service.session_store.SessionStore, "get",
        return_value={"state": "completed"},
    ):
        _expect_raises(SessionNotRunning, lambda: cancel_session("s1"))


def test_cancel_calls_request_cancel():
    with patch.object(
        session_service.session_store.SessionStore, "get",
        return_value={"state": "running"},
    ), patch.object(
        session_service.session_store.SessionStore, "update"
    ), patch.object(
        session_service.orchestrator, "request_cancel",
        return_value=True,
    ) as mreq:
        result = cancel_session("s1")
        assert result == {"session_id": "s1", "cancelled": True}
        assert mreq.called


def test_list_running_filters_non_running():
    with patch.object(
        session_service.session_store.SessionStore, "list_all"
    ) as mlist:
        mlist.return_value = [
            {"session_id": "r1", "state": "running"},
            {"session_id": "d1", "state": "completed"},
        ]
        result = list_running_sessions()
        assert result["total"] == 1
        assert result["sessions"][0]["session_id"] == "r1"
