import os
import threading
import tempfile

import pytest

from tests.integration.conftest import wait_for_state


def _fake_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF")
        return f.name


def _hold(client, _mock, event):
    _mock["pipeline"].run_transcription.side_effect = \
        lambda *a, **k: (event.wait(), iter([]))[1]
    resp = client.post("/api/v1/sessions/process",
                       json={"stages": ["transcribe"], "audio_path": _fake_audio()})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


# Two sessions can run at once (both under the concurrency cap).
def test_two_concurrent_accepted(client, _mock_orchestrator):
    e1, e2 = threading.Event(), threading.Event()
    s1 = _hold(client, _mock_orchestrator, e1)
    s2 = _hold(client, _mock_orchestrator, e2)
    try:
        assert client.get("/api/v1/sessions").json()["total"] == 2
    finally:
        e1.set()
        e2.set()
        wait_for_state(client, s1, timeout=5.0)
        wait_for_state(client, s2, timeout=5.0)


# A third session beyond the cap is rejected with 429.
def test_third_request_returns_429(client, _mock_orchestrator):
    e1, e2 = threading.Event(), threading.Event()
    s1 = _hold(client, _mock_orchestrator, e1)
    s2 = _hold(client, _mock_orchestrator, e2)
    try:
        third = client.post("/api/v1/sessions/process",
                            json={"stages": ["transcribe"], "audio_path": _fake_audio()})
        assert third.status_code == 429
    finally:
        e1.set()
        e2.set()
        wait_for_state(client, s1, timeout=5.0)
        wait_for_state(client, s2, timeout=5.0)


# A rejected 429 must not leave a phantom pending session in the DB.
def test_no_phantom_row_after_429(client, _mock_orchestrator):
    e1, e2 = threading.Event(), threading.Event()
    s1 = _hold(client, _mock_orchestrator, e1)
    s2 = _hold(client, _mock_orchestrator, e2)
    try:
        third = client.post("/api/v1/sessions/process",
                            json={"stages": ["transcribe"], "audio_path": _fake_audio()})
        assert third.status_code == 429
        ids = {s["session_id"] for s in client.get("/api/v1/sessions").json()["sessions"]}
        assert ids == {s1, s2}
    finally:
        e1.set()
        e2.set()
        wait_for_state(client, s1, timeout=5.0)
        wait_for_state(client, s2, timeout=5.0)


# Once a session completes, its concurrency slot is freed for the next one.
def test_slot_released_after_completion(client):
    first = client.post("/api/v1/sessions/process",
                        json={"stages": ["transcribe"], "audio_path": _fake_audio()})
    assert first.status_code == 200
    wait_for_state(client, first.json()["session_id"], timeout=5.0)
    second = client.post("/api/v1/sessions/process",
                         json={"stages": ["transcribe"], "audio_path": _fake_audio()})
    assert second.status_code == 200
    wait_for_state(client, second.json()["session_id"], timeout=5.0)


# If thread start fails, the registry entry is rolled back and no DB row remains.
def test_thread_start_failure_cleans_registry(client, monkeypatch):
    from utils import orchestrator

    class _FailingThread:
        daemon = True

        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

    with monkeypatch.context() as m:
        m.setattr(orchestrator.threading, "Thread", _FailingThread)
        with pytest.raises(RuntimeError):
            orchestrator.start_process({"stages": ["transcribe"], "audio_path": _fake_audio()})

    assert orchestrator._RUNNING == {}
    assert client.get("/api/v1/sessions").json()["total"] == 0