import threading
import tempfile

from tests.integration.conftest import wait_for_state


def _fake_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF")
        return f.name


def _hold_va(client, _mock, event):
    _mock["wait_completion"].side_effect = \
        lambda *a, **k: (event.wait(), True)[1]
    resp = client.post("/api/v1/sessions/process",
                       json={"stages": ["va"],
                             "video_sources": {"front": "rtsp://127.0.0.1:8554/live"}})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def _cancel(client, session_id):
    return client.post(f"/api/v1/sessions/{session_id}/cancel")


# Cancelling an in-flight audio session lands it in the cancelled state.
def test_cancel_audio_session(client, _mock_orchestrator):
    event = threading.Event()
    _mock_orchestrator["pipeline"].run_transcription.side_effect = \
        lambda *a, **k: (event.wait(), iter([]))[1]
    resp = client.post("/api/v1/sessions/process",
                       json={"stages": ["transcribe", "summarize"],
                             "audio_path": _fake_audio()})
    sid = resp.json()["session_id"]
    try:
        r = _cancel(client, sid)
        assert r.status_code == 200
        assert r.json()["cancelled"] is True
        event.set()
        state = wait_for_state(client, sid, timeout=5.0)
        assert state == "cancelled"
    finally:
        event.set()


# Cancelling a VA session must reach cancelled, not failed.
def test_cancel_va_session(client, _mock_orchestrator):
    event = threading.Event()
    sid = _hold_va(client, _mock_orchestrator, event)
    try:
        assert _cancel(client, sid).status_code == 200
        event.set()
        state = wait_for_state(client, sid, timeout=5.0)
        assert state == "cancelled"
    finally:
        event.set()


# A cancel arriving inside the VA wait window still tears pipelines down.
def test_cancel_during_va_wait(client, _mock_orchestrator):
    event = threading.Event()
    sid = _hold_va(client, _mock_orchestrator, event)
    try:
        assert _cancel(client, sid).status_code == 200
        event.set()
        state = wait_for_state(client, sid, timeout=5.0)
        assert state == "cancelled"
        assert _mock_orchestrator["va_service"].stop_all_pipelines.called
    finally:
        event.set()


# Cancelling a session that already terminated is rejected with 409.
def test_double_cancel_returns_409(client, _mock_orchestrator):
    event = threading.Event()
    _mock_orchestrator["pipeline"].run_transcription.side_effect = \
        lambda *a, **k: (event.wait(), iter([]))[1]
    resp = client.post("/api/v1/sessions/process",
                       json={"stages": ["transcribe", "summarize"],
                             "audio_path": _fake_audio()})
    sid = resp.json()["session_id"]
    try:
        assert _cancel(client, sid).status_code == 200
        event.set()
        state = wait_for_state(client, sid, timeout=5.0)
        assert state == "cancelled"
        assert _cancel(client, sid).status_code == 409
    finally:
        event.set()


# Cancelling a completed session is a 409 conflict.
def test_cancel_completed_returns_409(client):
    resp = client.post("/api/v1/sessions/process",
                       json={"stages": ["transcribe"], "audio_path": _fake_audio()})
    sid = resp.json()["session_id"]
    state = wait_for_state(client, sid, timeout=5.0)
    assert state == "completed"
    assert _cancel(client, sid).status_code == 409


# Cancelling a session that does not exist returns 404.
def test_cancel_nonexistent_returns_404(client):
    assert _cancel(client, "20260903-000000-dead").status_code == 404