import json
from pathlib import Path

from backend_mvp.asset_preparation import (
    AssetPreparationService,
    REASON_MISSING_MODEL,
    REASON_MISSING_PIPELINE_TEMPLATE,
    REASON_MISSING_VIDEO,
    REASON_RPPG_CONVERSION_FAILED,
)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_prepare_success_writes_resolved_pipeline_and_manifest(tmp_path: Path) -> None:
    m1 = tmp_path / "person.xml"
    m2 = tmp_path / "patient.xml"
    m3 = tmp_path / "latch.xml"
    vid = tmp_path / "input.mp4"
    template = tmp_path / "pipeline.template.json"
    resolved = tmp_path / "pipeline.resolved.json"

    for p in [m1, m2, m3, vid]:
        _write_file(p, "x")

    _write_file(
        template,
        '{"p":"{{PERSON_MODEL_PATH}}","v":"{{VIDEO_PATH}}","r":"{{RPPG_MODEL_PATH}}"}',
    )

    cfg = tmp_path / "config.yaml"
    _write_file(
        cfg,
        "\n".join(
            [
                "preparation:",
                f"  model_paths:\n    - {m1}\n    - {m2}\n    - {m3}",
                f"  video_path: {vid}",
                "  rppg_model_path: /models/rppg/mtts_can.xml",
                f"  pipeline_template: {template}",
                f"  resolved_pipeline: {resolved}",
                "dlsps:\n  base_url: http://localhost:8080",
            ]
        ),
    )

    result = AssetPreparationService(cfg).prepare()
    assert result.errors == []
    assert result.checks["models_ready"] is True
    assert result.checks["video_ready"] is True
    assert result.checks["pipeline_ready"] is True
    # dlsps_reachable is evaluated by the app bootstrap layer, not asset preparation.
    assert result.checks["dlsps_reachable"] is False
    assert resolved.exists()

    manifest_path = resolved.with_suffix(".manifest.json")
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["video_path"] == str(vid)


def test_prepare_missing_assets_reports_reason_catalog(tmp_path: Path) -> None:
    template = tmp_path / "pipeline.template.json"
    _write_file(template, "{}")
    cfg = tmp_path / "config.yaml"
    _write_file(
        cfg,
        "\n".join(
            [
                "preparation:",
                f"  model_paths:\n    - {tmp_path / 'missing1.xml'}",
                f"  video_path: {tmp_path / 'missing.mp4'}",
                f"  pipeline_template: {tmp_path / 'missing.template.json'}",
                f"  resolved_pipeline: {tmp_path / 'out.json'}",
            ]
        ),
    )

    result = AssetPreparationService(cfg).prepare()
    codes = {e["code"] for e in result.errors}
    assert REASON_MISSING_MODEL in codes
    assert REASON_MISSING_VIDEO in codes
    assert REASON_MISSING_PIPELINE_TEMPLATE in codes


def test_prepare_rppg_conversion_success_writes_artifacts(tmp_path: Path) -> None:
    m1 = tmp_path / "person.xml"
    m2 = tmp_path / "patient.xml"
    m3 = tmp_path / "latch.xml"
    vid = tmp_path / "input.mp4"
    template = tmp_path / "pipeline.template.json"
    resolved = tmp_path / "pipeline.resolved.json"
    hdf5 = tmp_path / "rppg" / "mtts_can.hdf5"
    xml = tmp_path / "rppg" / "mtts_can.xml"

    for p in [m1, m2, m3, vid, hdf5]:
        _write_file(p, "x")
    _write_file(template, '{"r":"{{RPPG_MODEL_PATH}}","loop":{{LOOP_ENABLED}},"max":{{LOOP_MAX}}}')

    cfg = tmp_path / "config.yaml"
    _write_file(
        cfg,
        "\n".join(
            [
                "preparation:",
                f"  model_paths:\n    - {m1}\n    - {m2}\n    - {m3}",
                f"  video_path: {vid}",
                f"  rppg_model_path: {xml}",
                "  rppg:",
                "    enabled: true",
                f"    hdf5_path: {hdf5}",
                "    converter_command:",
                "      - /bin/sh",
                "      - -c",
                "      - cp {hdf5_path} {ir_xml_path} && cp {hdf5_path} {ir_bin_path}",
                f"  pipeline_template: {template}",
                f"  resolved_pipeline: {resolved}",
                "dlsps:",
                "  loop:",
                "    enabled: true",
                "    max_loops: 3",
            ]
        ),
    )

    result = AssetPreparationService(cfg).prepare()
    assert result.errors == []
    assert xml.exists()
    assert xml.with_suffix(".bin").exists()
    assert result.resolved_manifest["rppg"]["xml"] == str(xml)


def test_prepare_rppg_conversion_missing_command_fails(tmp_path: Path) -> None:
    m1 = tmp_path / "person.xml"
    m2 = tmp_path / "patient.xml"
    m3 = tmp_path / "latch.xml"
    vid = tmp_path / "input.mp4"
    template = tmp_path / "pipeline.template.json"
    resolved = tmp_path / "pipeline.resolved.json"
    hdf5 = tmp_path / "rppg" / "mtts_can.hdf5"
    xml = tmp_path / "rppg" / "mtts_can.xml"

    for p in [m1, m2, m3, vid, hdf5]:
        _write_file(p, "x")
    _write_file(template, '{}')

    cfg = tmp_path / "config.yaml"
    _write_file(
        cfg,
        "\n".join(
            [
                "preparation:",
                f"  model_paths:\n    - {m1}\n    - {m2}\n    - {m3}",
                f"  video_path: {vid}",
                f"  rppg_model_path: {xml}",
                "  rppg:",
                "    enabled: true",
                f"    hdf5_path: {hdf5}",
                "    converter_command: []",
                f"  pipeline_template: {template}",
                f"  resolved_pipeline: {resolved}",
            ]
        ),
    )

    result = AssetPreparationService(cfg).prepare()
    codes = {e["code"] for e in result.errors}
    assert REASON_RPPG_CONVERSION_FAILED in codes
