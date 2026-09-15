from tests.integration.conftest import wait_for_state


def _post(client, body):
    return client.post("/api/v1/sessions/process", json=body)


def _await(client, session_id, timeout=5.0):
    return wait_for_state(client, session_id, timeout=timeout)


# A va stage with no video sources fails in the orchestrator, not the validator.
def test_va_without_sources_fails(client):
    resp = _post(client, {"stages": ["va"]})
    assert resp.status_code == 200
    state = _await(client, resp.json()["session_id"])
    assert state == "failed"


# Every requested VA pipeline fails to launch, so the whole session fails.
def test_va_launch_all_fail(client, _mock_orchestrator):
    _mock_orchestrator["va_service"].launch_pipeline.side_effect = lambda *a, **k: False
    resp = _post(client, {"stages": ["va"],
                          "video_sources": {"front": "rtsp://127.0.0.1:8554/live"}})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "failed"
    status = client.get(f"/api/v1/sessions/{sid}/status").json()
    assert "all va pipelines failed to launch" in status["error"]


# VA times out waiting for completion; the subprocesses must be torn down.
def test_va_timeout_tears_down(client, _mock_orchestrator):
    _mock_orchestrator["wait_completion"].side_effect = lambda *a, **k: False
    resp = _post(client, {"stages": ["va"],
                          "video_sources": {"front": "rtsp://127.0.0.1:8554/live"}})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "failed"
    status = client.get(f"/api/v1/sessions/{sid}/status").json()
    assert "va timed out" in status["error"]
    assert _mock_orchestrator["va_service"].stop_all_pipelines.called


# VA completes but every pipeline reports a failed final status -> session fails.
def test_va_no_success_status_fails(client, _mock_orchestrator):
    _mock_orchestrator["va_service"].launch_pipeline.side_effect = \
        lambda *a, **k: (setattr(_mock_orchestrator["va_service"],
                                 "pipeline_final_status", {"front": "failed"}) or True)
    resp = _post(client, {"stages": ["va"],
                          "video_sources": {"front": "rtsp://127.0.0.1:8554/live"}})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "failed"
    status = client.get(f"/api/v1/sessions/{sid}/status").json()
    assert "all va pipelines failed" in status["error"]


# VA completes with mixed statuses; at least one "eos" means the session succeeds.
def test_va_partial_success_completes(client, _mock_orchestrator):
    _mock_orchestrator["va_service"].launch_pipeline.side_effect = \
        lambda *a, **k: (setattr(_mock_orchestrator["va_service"],
                                 "pipeline_final_status",
                                 {"front": "eos", "back": "failed"}) or True)
    resp = _post(client, {"stages": ["va"],
                          "video_sources": {"front": "rtsp://x", "back": "rtsp://y"}})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "completed"
    assert client.get(f"/api/v1/sessions/{sid}/status").json()["stages"]["va"] == "done"


# A pipeline that raises as soon as it is called makes the session fail.
def test_pipeline_immediate_error_fails(client, _mock_orchestrator):
    audio = _fake_audio()
    _mock_orchestrator["pipeline"].run_transcription.side_effect = RuntimeError("boom")
    resp = _post(client, {"stages": ["transcribe"], "audio_path": audio})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "failed"
    status = client.get(f"/api/v1/sessions/{sid}/status").json()
    assert "unexpected error" in status["error"] or "boom" in status["error"]


# A pipeline that yields then raises mid-iteration also fails (drain path).
def test_pipeline_mid_iteration_error_fails(client, _mock_orchestrator):
    audio = _fake_audio()

    def _mid(*a, **k):
        def _gen():
            yield None
            raise RuntimeError("mid failure")
        return _gen()

    _mock_orchestrator["pipeline"].run_transcription.side_effect = _mid
    resp = _post(client, {"stages": ["transcribe"], "audio_path": audio})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "failed"


# A failing board-OCR startup must not fail the VA session itself.
def test_board_ocr_start_failure_does_not_fail(client, _mock_orchestrator):
    _mock_orchestrator["start_ocr"].side_effect = RuntimeError("ocr down")
    resp = _post(client, {"stages": ["va"],
                          "video_sources": {"content": "rtsp://127.0.0.1:8554/live"}})
    sid = resp.json()["session_id"]
    state = _await(client, sid)
    assert state == "completed"


def _fake_audio():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF")
        return f.name