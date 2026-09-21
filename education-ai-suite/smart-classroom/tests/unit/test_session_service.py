import os
import tempfile
from unittest.mock import patch

from api.v1.schemas.session import RegisterRequest, WorkflowRequest
from services.session_service import (
    ArtifactNotFound,
    ConcurrencyLimitError,
    SessionNotCancellable,
    SessionNotFound,
    SessionNotRunning,
    SessionRunning,
    SessionValidationError,
    artifact_file,
    cancel_session,
    create_process,
    delete_session,
    finalize_session,
    get_stage_events,
    get_status,
    list_artifacts,
    list_running_sessions,
    list_sessions,
    read_text_artifact,
    register_session,
)
from services import session_service
from utils.session_manager import generate_session_id


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


def test_cancel_rejects_a_session_the_orchestrator_does_not_own():
    """A UI-driven session has no cancel flag and no thread polling one. Saying
    'cancelled: true' would be a lie: nothing would stop."""
    with patch.object(
        session_service.session_store.SessionStore, "get",
        return_value={"state": "running"},
    ), patch.object(
        session_service.orchestrator, "request_cancel", return_value=False
    ):
        _expect_raises(SessionNotCancellable, lambda: cancel_session("s1"))


# ----- register -----

def _reg(**kw):
    defaults = {"session_id": generate_session_id(), "stages": ["transcribe"]}
    defaults.update(kw)
    return RegisterRequest(**defaults)


def test_register_rejects_a_client_invented_id():
    for bogus in ("../../etc", "s1", "", "20260909-143012-XYZQ"):
        _expect_raises(
            SessionValidationError, lambda b=bogus: register_session(_reg(session_id=b))
        )


def test_register_rejects_empty_and_unknown_stages():
    _expect_raises(SessionValidationError, lambda: register_session(_reg(stages=[])))
    _expect_raises(SessionValidationError, lambda: register_session(_reg(stages=["bogus"])))


def test_register_creates_a_running_session():
    req = _reg(stages=["transcribe", "summarize"])
    result = register_session(req)
    assert result["session_id"] == req.session_id
    assert result["state"] == "running"
    assert result["already_registered"] is False
    assert result["stages"]["transcribe"] == "pending"
    # Stages that were not asked for are marked skipped, as with create_process.
    assert result["stages"]["report"] == "skipped"


def test_register_is_idempotent():
    req = _reg()
    register_session(req)
    session_service.session_store.SessionStore.set_stage(
        req.session_id, "transcribe", "done"
    )
    again = register_session(req)
    assert again["already_registered"] is True
    # A retried POST must not rewind a session already underway.
    assert again["stages"]["transcribe"] == "done"


# ----- finalize -----

def test_finalize_not_found():
    _expect_raises(SessionNotFound, lambda: finalize_session("nope", "completed"))


def test_finalize_marks_completed():
    req = _reg()
    register_session(req)
    result = finalize_session(req.session_id, "completed")
    assert result["state"] == "completed"


def test_finalize_aborted_records_a_reason():
    """What the browser's unload beacon sends."""
    req = _reg()
    register_session(req)
    result = finalize_session(req.session_id, "aborted")
    assert result["state"] == "failed"
    assert "interrupted" in result["error"]


def test_finalize_is_idempotent_and_does_not_overwrite():
    req = _reg()
    register_session(req)
    finalize_session(req.session_id, "completed")
    # A late beacon arriving after a clean finish must not turn it into a failure.
    again = finalize_session(req.session_id, "aborted")
    assert again["state"] == "completed"
    assert again["error"] is None


def test_finalize_refuses_orchestrator_owned_sessions():
    req = _reg()
    register_session(req)
    with patch.object(
        session_service.orchestrator, "running_session_ids",
        return_value=[req.session_id],
    ):
        _expect_raises(
            SessionRunning, lambda: finalize_session(req.session_id, "completed")
        )


def test_registered_session_shows_up_in_the_history():
    req = _reg()
    register_session(req)
    listing = list_sessions()
    assert req.session_id in [s["session_id"] for s in listing["sessions"]]


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


# ----- history -----

def test_list_sessions_reports_the_whole_table_not_the_page():
    """The history pages through `total`, so it must not be the page length."""
    for _ in range(3):
        register_session(_reg())
    page = list_sessions(limit=2, offset=0)
    assert len(page["sessions"]) == 2
    assert page["total"] == 3


def test_list_sessions_includes_the_error_so_the_row_can_explain_itself():
    req = _reg()
    register_session(req)
    finalize_session(req.session_id, "aborted")
    row = next(s for s in list_sessions()["sessions"] if s["session_id"] == req.session_id)
    assert row["state"] == "failed"
    assert "interrupted" in row["error"]


def test_stage_events_not_found():
    _expect_raises(SessionNotFound, lambda: get_stage_events("20260101-000000-abcd"))


def test_stage_events_are_empty_when_nothing_was_recorded():
    req = _reg()
    register_session(req)
    assert get_stage_events(req.session_id) == {"session_id": req.session_id, "events": []}


def test_artifacts_not_found():
    _expect_raises(SessionNotFound, lambda: list_artifacts("20260101-000000-abcd"))
    _expect_raises(SessionNotFound, lambda: artifact_file("20260101-000000-abcd", "summarize"))


def test_artifacts_lists_only_what_is_on_disk():
    """A stage that wrote nothing must be absent, not listed-and-broken: the
    history decides from this which stage names are worth making clickable."""
    from utils.session_paths import SessionPaths

    req = _reg()
    register_session(req)
    assert list_artifacts(req.session_id)["artifacts"] == []

    path = SessionPaths.summary_path(req.session_id)
    os.makedirs(path.parent, exist_ok=True)
    path.write_text("## Summary\n- a point\n", encoding="utf-8")

    artifacts = list_artifacts(req.session_id)["artifacts"]
    assert [a["stage"] for a in artifacts] == ["summarize"]
    assert artifacts[0]["kind"] == "markdown"
    assert artifacts[0]["filename"] == "summary.md"


def test_artifact_rejects_a_stage_with_no_preview():
    req = _reg()
    register_session(req)
    # A stage nobody has heard of, and one that simply wrote nothing.
    _expect_raises(ArtifactNotFound, lambda: artifact_file(req.session_id, "bogus"))
    _expect_raises(ArtifactNotFound, lambda: artifact_file(req.session_id, "va"))


def test_every_stage_that_produces_a_file_has_a_preview():
    """Each stage's own output, at the path that stage writes: the timings table
    is keyed by stage, so a stage with an artifact nobody mapped is a row the
    teacher cannot open."""
    from utils.session_paths import SessionPaths

    expected = {
        "transcribe": ("transcript", SessionPaths.transcript_path, "教师: 好，\n"),
        "summarize": ("markdown", SessionPaths.summary_path, "## 教师总结\n"),
        "mindmap": ("mindmap", SessionPaths.mindmap_path, '{"format": "node_tree"}'),
        "va": ("stats", SessionPaths.class_statistics_path, '{"student_count": 10}'),
        "segmentation": ("topics", SessionPaths.topics_path, '[{"topic": "影子"}]'),
        "report": ("markdown", SessionPaths.report_md_path, "# 课后总结报告\n"),
    }
    req = _reg()
    register_session(req)
    for stage, (kind, resolve, body) in expected.items():
        path = resolve(req.session_id)
        os.makedirs(path.parent, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        assert artifact_file(req.session_id, stage) == (kind, path)

    listed = list_artifacts(req.session_id)["artifacts"]
    # Listed in pipeline order, so the files read the way the run did.
    assert [a["stage"] for a in listed] == list(expected)


def test_read_text_artifact_returns_the_file():
    from utils.session_paths import SessionPaths

    req = _reg()
    register_session(req)
    path = SessionPaths.transcript_path(req.session_id)
    os.makedirs(path.parent, exist_ok=True)
    path.write_text("教师: 好，\n教师: 上课。\n", encoding="utf-8")

    result = read_text_artifact(req.session_id, "transcribe")
    assert result["kind"] == "transcript"
    assert result["truncated"] is False
    assert "上课" in result["content"]


def test_mindmap_artifact_is_the_mmd_source_not_the_report_png():
    """The .mmd is what the stage itself wrote, so it is there for every session
    that got that far; the PNG only exists once the UI screenshots the live view
    for a report."""
    from utils.session_paths import SessionPaths

    req = _reg()
    register_session(req)
    png = SessionPaths.mindmap_png_path(req.session_id)
    os.makedirs(png.parent, exist_ok=True)
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    # A PNG on its own is not a preview.
    _expect_raises(ArtifactNotFound, lambda: artifact_file(req.session_id, "mindmap"))

    SessionPaths.mindmap_path(req.session_id).write_text(
        '{"meta": {}, "format": "node_tree", "data": {"id": "root", "topic": "影子"}}',
        encoding="utf-8",
    )
    kind, resolved = artifact_file(req.session_id, "mindmap")
    assert kind == "mindmap"
    assert resolved.name == "mindmap.mmd"
    assert "node_tree" in read_text_artifact(req.session_id, "mindmap")["content"]


def test_read_text_artifact_truncates_a_huge_file():
    from utils.session_paths import SessionPaths

    req = _reg()
    register_session(req)
    path = SessionPaths.transcript_path(req.session_id)
    os.makedirs(path.parent, exist_ok=True)
    with patch.object(session_service, "_TEXT_ARTIFACT_LIMIT", 16):
        path.write_text("x" * 64, encoding="utf-8")
        result = read_text_artifact(req.session_id, "transcribe")
    assert result["truncated"] is True
    assert len(result["content"]) == 16


def test_stage_events_survive_a_truncated_last_line():
    """A crash mid-append leaves a partial JSON line; the rest must still load."""
    from utils.session_paths import SessionPaths

    req = _reg()
    register_session(req)
    path = SessionPaths.stage_events_path(req.session_id)
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(
        '{"stage": "transcribe", "status": "done", "duration_sec": 1.5}\n'
        '{"stage": "summarize", "status": "don',
        encoding="utf-8",
    )
    events = get_stage_events(req.session_id)["events"]
    assert len(events) == 1
    assert events[0]["stage"] == "transcribe"
