import re

from tests.integration.conftest import wait_for_state

_SESSION_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")


def _create(client, stages, **extra):
    body = {"stages": stages, **extra}
    resp = client.post("/api/v1/sessions/process", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json(), client


def _await_status(client, session_id):
    state = wait_for_state(client, session_id, timeout=5.0)
    resp = client.get(f"/api/v1/sessions/{session_id}/status")
    return state, resp.json()


# va + report without segmentation must still complete, because the VA thread
# is joined before the session is marked completed (orchestrator finally).
def test_va_report_without_segmentation_completes(client):
    data, client = _create(client, ["va", "report"],
                           video_sources={"front": "rtsp://127.0.0.1:8554/live"})
    session_id = data["session_id"]
    state, status = _await_status(client, session_id)
    assert state == "completed"
    assert status["stages"]["va"] == "done"
    assert status["stages"]["report"] == "done"


# A single transcribe stage completes and all other stages stay skipped.
def test_transcribe_only(client, tmp_path):
    audio = tmp_path / "lecture.wav"
    audio.write_bytes(b"RIFF")
    data, client = _create(client, ["transcribe"], audio_path=str(audio))
    state, status = _await_status(client, data["session_id"])
    assert state == "completed"
    assert status["stages"]["transcribe"] == "done"
    for stage, val in status["stages"].items():
        if stage != "transcribe":
            assert val == "skipped", f"{stage} should be skipped, got {val}"


# Multiple audio stages run serially, each reaching done.
def test_multiple_stages_serial(client, tmp_path):
    audio = tmp_path / "lecture.wav"
    audio.write_bytes(b"RIFF")
    data, client = _create(client, ["transcribe", "summarize", "mindmap"],
                           audio_path=str(audio))
    state, status = _await_status(client, data["session_id"])
    assert state == "completed"
    assert status["stages"]["transcribe"] == "done"
    assert status["stages"]["summarize"] == "done"
    assert status["stages"]["mindmap"] == "done"


# A pure VA session completes on its own.
def test_va_only(client):
    data, client = _create(client, ["va"],
                           video_sources={"front": "rtsp://127.0.0.1:8554/live"})
    state, status = _await_status(client, data["session_id"])
    assert state == "completed"
    assert status["stages"]["va"] == "done"


# va then segmentation: segmentation waits for the VA thread to finish first.
def test_va_then_segmentation(client, _mock_orchestrator):
    data, client = _create(client, ["va", "segmentation"],
                           video_sources={"front": "rtsp://127.0.0.1:8554/live"})
    session_id = data["session_id"]
    state, status = _await_status(client, session_id)
    assert state == "completed"
    assert status["stages"]["va"] == "done"
    assert status["stages"]["segmentation"] == "done"


# All six stages in one session all complete.
def test_all_stages(client, tmp_path):
    audio = tmp_path / "lecture.wav"
    audio.write_bytes(b"RIFF")
    data, client = _create(
        client,
        ["transcribe", "summarize", "mindmap", "va", "segmentation", "report"],
        audio_path=str(audio),
        video_sources={"front": "rtsp://127.0.0.1:8554/live"},
    )
    state, status = _await_status(client, data["session_id"])
    assert state == "completed"
    for stage in ("transcribe", "summarize", "mindmap", "va", "segmentation", "report"):
        assert status["stages"][stage] == "done", f"{stage} should be done"


# Response body carries a well-formed session_id, absolute output dir and start time.
def test_response_shape(client, tmp_path):
    audio = tmp_path / "lecture.wav"
    audio.write_bytes(b"RIFF")
    data, client = _create(client, ["transcribe"], audio_path=str(audio))
    assert _SESSION_ID_RE.match(data["session_id"])
    assert data["output_dir"] and __import__("os").path.isabs(data["output_dir"])
    assert data["started_at"]
    wait_for_state(client, data["session_id"], timeout=5.0)