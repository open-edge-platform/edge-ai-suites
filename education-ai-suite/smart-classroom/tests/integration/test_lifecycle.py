import os
import tempfile

from tests.integration.conftest import wait_for_state


def _fake_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF")
        return f.name


def _create(client):
    resp = client.post("/api/v1/sessions/process",
                       json={"stages": ["transcribe"], "audio_path": _fake_audio()})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


# The session list is empty when no session has been created.
def test_empty_list(client):
    resp = client.get("/api/v1/sessions")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["sessions"] == []


# A created session shows up in the session list.
def test_list_contains_created(client):
    sid = _create(client)
    wait_for_state(client, sid, timeout=5.0)
    resp = client.get("/api/v1/sessions").json()
    ids = {s["session_id"] for s in resp["sessions"]}
    assert sid in ids
    assert resp["total"] == len(resp["sessions"])


# Status exposes the session id, terminal state, per-stage progress and paths.
def test_status_correct(client):
    sid = _create(client)
    state = wait_for_state(client, sid, timeout=5.0)
    assert state == "completed"
    status = client.get(f"/api/v1/sessions/{sid}/status").json()
    assert status["session_id"] == sid
    assert status["state"] == "completed"
    assert status["stages"]["transcribe"] == "done"
    assert status["output_dir"]
    assert status["started_at"]


# Status for an unknown session id returns 404.
def test_status_missing_returns_404(client):
    resp = client.get("/api/v1/sessions/20260903-000000-dead/status")
    assert resp.status_code == 404


# The /running filter lists only sessions still in the running state.
def test_running_only_lists_running(client, _mock_orchestrator):
    import threading
    hold = threading.Event()
    # held session: transcribe blocked; completed session: mindmap (not blocked)
    _mock_orchestrator["pipeline"].run_transcription.side_effect = \
        lambda *a, **k: (hold.wait(), iter([]))[1]
    running_resp = client.post("/api/v1/sessions/process",
                               json={"stages": ["transcribe"], "audio_path": _fake_audio()})
    assert running_resp.status_code == 200
    running_sid = running_resp.json()["session_id"]

    completed_resp = client.post("/api/v1/sessions/process",
                                 json={"stages": ["mindmap"]})
    assert completed_resp.status_code == 200
    completed_sid = completed_resp.json()["session_id"]
    wait_for_state(client, completed_sid, timeout=5.0)
    try:
        running = client.get("/api/v1/sessions/running").json()
        running_ids = {s["session_id"] for s in running["sessions"]}
        assert running_sid in running_ids
        assert completed_sid not in running_ids
    finally:
        hold.set()
        wait_for_state(client, running_sid, timeout=5.0)


# Deleting a finished session removes it from the list.
def test_delete_completed_removes(client):
    sid = _create(client)
    wait_for_state(client, sid, timeout=5.0)
    resp = client.delete(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # gone from list
    ids = {s["session_id"] for s in client.get("/api/v1/sessions").json()["sessions"]}
    assert sid not in ids


# A running session cannot be deleted, returning 409.
def test_delete_running_returns_409(client, _mock_orchestrator):
    import threading
    hold = threading.Event()
    _mock_orchestrator["pipeline"].run_transcription.side_effect = \
        lambda *a, **k: (hold.wait(), iter([]))[1]
    sid = _create(client)
    try:
        resp = client.delete(f"/api/v1/sessions/{sid}")
        assert resp.status_code == 409
    finally:
        hold.set()
        wait_for_state(client, sid, timeout=5.0)


# Deleting an unknown session returns 404.
def test_delete_missing_returns_404(client):
    resp = client.delete("/api/v1/sessions/20260903-000000-dead")
    assert resp.status_code == 404