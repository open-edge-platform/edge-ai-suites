def _post(client, body):
    return client.post("/api/v1/sessions/process", json=body)


# Rejects a POST with an empty stages array before any session is created.
def test_empty_stages_returns_400(client):
    resp = _post(client, {"stages": []})
    assert resp.status_code == 400
    assert "stages required" in resp.json()["detail"]


# Rejects a POST that omits stages entirely (Pydantic treats it as required).
def test_missing_stages_returns_422(client):
    resp = _post(client, {})
    assert resp.status_code == 422


# Rejects a stages entry that is not one of the known pipeline stages.
def test_unknown_stage_returns_400(client):
    resp = _post(client, {"stages": ["unknown"]})
    assert resp.status_code == 400
    assert "unknown stage" in resp.json()["detail"]


# Rejects transcribe without the audio file path it requires as a prerequisite.
def test_transcribe_without_audio_returns_400(client):
    resp = _post(client, {"stages": ["transcribe"]})
    assert resp.status_code == 400
    assert "requires audio_path" in resp.json()["detail"]


# Rejects an audio_path that does not point to an existing file.
def test_nonexistent_audio_path_returns_400(client):
    resp = _post(client, {"stages": ["transcribe"], "audio_path": "/definitely/nope.wav"})
    assert resp.status_code == 400
    assert "file not found" in resp.json()["detail"]


# Rejects a video source whose local path does not exist on disk.
def test_nonexistent_video_source_returns_400(client, tmp_path):
    missing = tmp_path / "missing_video.mp4"
    resp = _post(client, {"stages": ["va"], "video_sources": {"front": str(missing)}})
    assert resp.status_code == 400
    assert "file not found" in resp.json()["detail"]


# An rtsp URL is a valid video source, so it bypasses the file-exists check.
def test_rtsp_video_source_is_accepted(client):
    resp = _post(client, {
        "stages": ["va"],
        "video_sources": {"front": "rtsp://127.0.0.1:8554/live"},
    })
    assert resp.status_code == 200
    from tests.integration.conftest import wait_for_state
    wait_for_state(client, resp.json()["session_id"], timeout=5.0)


# A non-list stages field fails Pydantic schema validation, returning 422.
def test_stages_not_a_list_returns_422(client):
    resp = _post(client, {"stages": "transcribe"})
    assert resp.status_code == 422