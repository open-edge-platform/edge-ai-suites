def _post(client, body):
    return client.post("/api/v1/sessions/process", json=body)


def test_v1_empty_stages_returns_400(client):
    resp = _post(client, {"stages": []})
    assert resp.status_code == 400
    assert "stages required" in resp.json()["detail"]


def test_v2_missing_stages_returns_422(client):
    resp = _post(client, {})
    assert resp.status_code == 422


def test_v3_unknown_stage_returns_400(client):
    resp = _post(client, {"stages": ["unknown"]})
    assert resp.status_code == 400
    assert "unknown stage" in resp.json()["detail"]


def test_v4_transcribe_without_audio_returns_400(client):
    resp = _post(client, {"stages": ["transcribe"]})
    assert resp.status_code == 400
    assert "requires audio_path" in resp.json()["detail"]


def test_v5_nonexistent_audio_path_returns_400(client):
    resp = _post(client, {"stages": ["transcribe"], "audio_path": "/definitely/nope.wav"})
    assert resp.status_code == 400
    assert "file not found" in resp.json()["detail"]


def test_v6_nonexistent_video_source_returns_400(client, tmp_path):
    missing = tmp_path / "missing_video.mp4"
    resp = _post(client, {"stages": ["va"], "video_sources": {"front": str(missing)}})
    assert resp.status_code == 400
    assert "file not found" in resp.json()["detail"]


def test_v7_rtsp_video_source_is_accepted(client):
    resp = _post(client, {
        "stages": ["va"],
        "video_sources": {"front": "rtsp://127.0.0.1:8554/live"},
    })
    assert resp.status_code == 200
    from tests.integration.conftest import wait_for_state
    wait_for_state(client, resp.json()["session_id"], timeout=5.0)


def test_v8_stages_not_a_list_returns_422(client):
    resp = _post(client, {"stages": "transcribe"})
    assert resp.status_code == 422