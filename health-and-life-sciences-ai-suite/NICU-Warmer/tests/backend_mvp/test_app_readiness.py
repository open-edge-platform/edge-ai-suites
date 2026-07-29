from pathlib import Path

from backend_mvp.app import create_app


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_config(tmp_path: Path, assume_reachable: bool = True) -> Path:
    m1 = tmp_path / "person.xml"
    m2 = tmp_path / "patient.xml"
    m3 = tmp_path / "latch.xml"
    vid = tmp_path / "input.mp4"
    template = tmp_path / "pipeline.template.json"
    resolved = tmp_path / "pipeline.resolved.json"

    for p in [m1, m2, m3, vid]:
        _write_file(p, "x")
    _write_file(template, '{"source":"{{VIDEO_PATH}}"}')

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
                f"  assume_reachable: {str(assume_reachable).lower()}",
            ]
        ),
    )
    return cfg


def test_readiness_ready_when_checks_pass(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path, assume_reachable=True)
    app = create_app(str(cfg))
    client = app.test_client()

    response = client.get("/readiness")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ready"] is True
    assert data["lifecycle"] == "ready"
    assert data["errors"] == []


def test_duplicate_start_returns_409(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path, assume_reachable=True)
    app = create_app(str(cfg))
    client = app.test_client()

    first = client.post("/start")
    assert first.status_code in (200, 500)

    second = client.post("/start")
    assert second.status_code == 409
    payload = second.get_json()
    assert payload["error"] == "Start allowed only in ready state"
