import time
from pathlib import Path

from backend_mvp.app import create_app
from backend_mvp.dlsps_controller import DLSPSController, DLSPSControllerConfig


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_config(tmp_path: Path) -> Path:
    m1 = tmp_path / "person.xml"
    m2 = tmp_path / "patient.xml"
    m3 = tmp_path / "latch.xml"
    vid = tmp_path / "input.mp4"
    template = tmp_path / "pipeline.template.json"
    resolved = tmp_path / "pipeline.resolved.json"

    for p in [m1, m2, m3, vid]:
        _write_file(p, "x")
    _write_file(template, '{"source":{"path":"{{VIDEO_PATH}}","loop":{{LOOP_ENABLED}},"max_loops":{{LOOP_MAX}}}}')

    cfg = tmp_path / "config.yaml"
    _write_file(
        cfg,
        "\n".join(
            [
                "preparation:",
                f"  model_paths:\n    - {m1}\n    - {m2}\n    - {m3}",
                f"  video_path: {vid}",
                f"  pipeline_template: {template}",
                f"  resolved_pipeline: {resolved}",
                "dlsps:",
                "  base_url: http://localhost:8080",
                "  assume_reachable: true",
                "  status_poll_interval_seconds: 0.01",
            ]
        ),
    )
    return cfg


class _FakeResponse:
    def __init__(self, ok: bool, status_code: int = 200, text: str = "", payload=None):
        self.ok = ok
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._payload


def test_dlsps_controller_start_status_stop(monkeypatch) -> None:
    calls = {"start": 0, "status": 0, "stop": 0}

    def fake_post(url, json=None, timeout=0):  # noqa: ANN001
        if url.endswith("/pipelines/start"):
            calls["start"] += 1
            return _FakeResponse(True, payload={"pipeline_id": "abc"})
        if url.endswith("/pipelines/stop"):
            calls["stop"] += 1
            assert json == {"pipeline_id": "abc"}
            return _FakeResponse(True)
        return _FakeResponse(False, status_code=404, text="not found")

    def fake_get(url, params=None, timeout=0):  # noqa: ANN001
        if url.endswith("/pipelines/status"):
            calls["status"] += 1
            assert params == {"pipeline_id": "abc"}
            return _FakeResponse(True, payload={"status": "running", "frame_count": 1})
        return _FakeResponse(True)

    monkeypatch.setattr("backend_mvp.dlsps_controller.requests.post", fake_post)
    monkeypatch.setattr("backend_mvp.dlsps_controller.requests.get", fake_get)

    ctl = DLSPSController(DLSPSControllerConfig(base_url="http://localhost:8080"))
    ok, msg = ctl.start("/tmp/pipeline.json")
    assert ok is True
    assert msg == "started"

    status_ok, payload = ctl.status()
    assert status_ok is True
    assert payload["status"] == "running"

    stop_ok, stop_msg = ctl.stop()
    assert stop_ok is True
    assert stop_msg == "stopped"

    assert calls == {"start": 1, "status": 1, "stop": 1}


def test_app_loop_count_increments_on_wrap(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    app = create_app(str(cfg))
    backend = app.config["MVP_BACKEND"]

    statuses = [
        {"status": "running", "frame_count": 5, "fps": 15.0, "latency_ms": 10.0},
        {"status": "running", "frame_count": 1, "fps": 14.0, "latency_ms": 11.0},
    ]

    def fake_start(_pipeline_path: str):
        return True, "started"

    def fake_status():
        if statuses:
            return True, statuses.pop(0)
        return True, {"status": "running", "frame_count": 2, "fps": 13.0, "latency_ms": 12.0}

    def fake_stop():
        return True, "stopped"

    backend.dlsps.start = fake_start
    backend.dlsps.status = fake_status
    backend.dlsps.stop = fake_stop

    client = app.test_client()
    start_response = client.post("/start")
    assert start_response.status_code == 200

    # Allow the background status poller to process at least two samples.
    deadline = time.time() + 1.0
    loop_count = 0
    while time.time() < deadline:
        metrics = client.get("/metrics").get_json()
        loop_count = int(metrics["loop_count"])
        if loop_count >= 1:
            break
        time.sleep(0.02)

    assert loop_count >= 1

    stop_response = client.post("/stop")
    assert stop_response.status_code == 200
