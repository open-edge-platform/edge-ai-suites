"""Prefilter config contract tests.

Why this file exists
--------------------
Per design §7.3 "Register Source Request" and dev tracker §22 / §23.3:
- The MCP Server decides per-use-case whether to enable prefilter (e.g.
  pet_safety / fridge → off; child_safety / elder_wakeup → on) and emits the
  resulting `prefilter` block in the register payload.
- This microservice is a faithful executor: `source.prefilter` (when present)
  must completely override `defaults.prefilter`, and an absent `source.prefilter`
  must fall through to defaults verbatim.

A previous incident (dev tracker §23.3.2) showed prefilter init can fail
silently when the model file does not exist — the pipeline must degrade to
"no prefilter" rather than crash, so an unrelated config error doesn't take
down a healthy stream.

These tests pin the override / fall-through / graceful-degrade contracts so
future changes to the merge logic can't quietly break them.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from shared.config import (
    DefaultsConfig,
    PrefilterConfig,
    SourceConfig,
)
from sinks import NullSink
from stream_monitor.rtsp_monitor import StreamPipeline


def _make_pipeline(source: SourceConfig, defaults: DefaultsConfig | None = None):
    if defaults is None:
        defaults = DefaultsConfig()
    with patch("stream_monitor.rtsp_monitor.cv2"):
        return StreamPipeline(
            source=source,
            defaults=defaults,
            data_dir="/tmp/test-prefilter-contract",
            sink=NullSink(),
        )


class TestPrefilterOverride:
    """source.prefilter overrides explicit fields and inherits omitted ones."""

    def test_source_disables_overrides_enabled_default(self):
        defaults = DefaultsConfig(
            prefilter=PrefilterConfig(
                enabled=True,
                model_path="/models/yolo11s.xml",
                target_classes=["person"],
                detect_fps=2.0,
            )
        )
        source = SourceConfig(
            source_id="cam_pet",
            source_url="rtsp://x/y",
            prefilter=PrefilterConfig(enabled=False),
        )
        pipeline = _make_pipeline(source, defaults)
        assert pipeline._prefilter_cfg.enabled is False
        assert pipeline._prefilter_cfg.model_path == "/models/yolo11s.xml"
        assert pipeline._prefilter_cfg.detect_fps == 2.0
        assert pipeline._prefilter is None

    def test_source_overrides_target_classes(self):
        """Explicit source fields override defaults while omitted ones inherit."""
        defaults = DefaultsConfig(
            prefilter=PrefilterConfig(
                enabled=False,
                model_path="/models/yolo11s.xml",
                target_classes=["person"],
                device="NPU",
            )
        )
        source = SourceConfig(
            source_id="cam_pet",
            source_url="rtsp://x/y",
            prefilter=PrefilterConfig(
                enabled=False, target_classes=["cat", "dog"]
            ),
        )
        pipeline = _make_pipeline(source, defaults)
        assert pipeline._prefilter_cfg.target_classes == ["cat", "dog"]
        assert pipeline._prefilter_cfg.model_path == "/models/yolo11s.xml"
        assert pipeline._prefilter_cfg.device == "NPU"

    def test_partial_source_prefilter_inherits_missing_fields(self):
        defaults = DefaultsConfig(
            prefilter=PrefilterConfig(
                enabled=True,
                model_path="/models/yolo11s.xml",
                target_classes=["person"],
                min_confidence=0.4,
                detect_fps=2.0,
            )
        )
        source = SourceConfig(
            source_id="cam_child",
            source_url="rtsp://x/y",
            prefilter=PrefilterConfig(min_confidence=0.75),
        )
        pipeline = _make_pipeline(source, defaults)
        assert pipeline._prefilter_cfg.enabled is True
        assert pipeline._prefilter_cfg.model_path == "/models/yolo11s.xml"
        assert pipeline._prefilter_cfg.target_classes == ["person"]
        assert pipeline._prefilter_cfg.min_confidence == 0.75
        assert pipeline._prefilter_cfg.detect_fps == 2.0

    def test_absent_source_prefilter_inherits_defaults(self):
        defaults = DefaultsConfig(
            prefilter=PrefilterConfig(
                enabled=False,  # disabled in defaults to avoid touching disk
                model_path="/some/path.xml",
                target_classes=["person"],
                min_confidence=0.42,
                detect_fps=3.5,
            )
        )
        source = SourceConfig(
            source_id="cam_x",
            source_url="rtsp://x/y",
            prefilter=None,
        )
        pipeline = _make_pipeline(source, defaults)
        assert pipeline._prefilter_cfg is defaults.prefilter
        assert pipeline._prefilter_cfg.min_confidence == 0.42
        assert pipeline._prefilter_cfg.detect_fps == 3.5


class TestPrefilterGracefulDegrade:
    """Prefilter init must never propagate exceptions to the caller."""

    def test_enabled_with_empty_model_path_skips_init(self):
        """Per current implementation: empty model_path silently skips."""
        source = SourceConfig(
            source_id="cam_x",
            source_url="rtsp://x/y",
            prefilter=PrefilterConfig(enabled=True, model_path=""),
        )
        pipeline = _make_pipeline(source)
        assert pipeline._prefilter is None

    def test_enabled_with_missing_model_file_degrades(self, caplog):
        source = SourceConfig(
            source_id="cam_x",
            source_url="rtsp://x/y",
            prefilter=PrefilterConfig(
                enabled=True,
                model_path="/does/not/exist.xml",
            ),
        )
        with caplog.at_level("WARNING"):
            pipeline = _make_pipeline(source)
        assert pipeline._prefilter is None
        # Some warning must be logged so operators can see why prefilter is off
        assert any(
            "Prefilter init failed" in rec.message
            for rec in caplog.records
        )

    def test_yolopfilter_exception_does_not_crash(self):
        source = SourceConfig(
            source_id="cam_x",
            source_url="rtsp://x/y",
            prefilter=PrefilterConfig(
                enabled=True,
                model_path="/anything.xml",
            ),
        )
        with patch(
            "stream_monitor.rtsp_monitor.YoloPrefilter",
            side_effect=RuntimeError("openvino blew up"),
        ):
            pipeline = _make_pipeline(source)
        # Pipeline still constructed, prefilter is None
        assert pipeline._prefilter is None


class TestPrefilterFromHTTPRegister:
    """End-to-end: HTTP POST /register_source body → resolved PrefilterConfig.

    Catches regressions in the register_source pydantic schema or in
    SourceManager wiring (e.g. accidentally dropping the prefilter field).
    """

    def _resolve(self, payload: dict, defaults_prefilter: PrefilterConfig):
        """Simulate what FastAPI + SourceManager do, without starting threads.

        Payload is the new nested-pipeline format (Phase 7 hard cutover).
        """
        from service import RegisterSourceRequest
        req = RegisterSourceRequest(**payload)
        source = SourceConfig(
            source_id=req.source_id,
            source_url=req.source_url,
            webhook_url=req.webhook_url,
            data_dir=req.data_dir,
            motion=req.pipeline.motion,
            segment=req.pipeline.segment,
            prefilter=req.pipeline.prefilter,
            recording=req.pipeline.recording,
            health=req.pipeline.health,
        )
        defaults = DefaultsConfig(prefilter=defaults_prefilter)
        return _make_pipeline(source, defaults)._prefilter_cfg

    def test_pet_safety_disable_payload(self):
        """Payload like the one MCP Server sends for non-person use cases."""
        cfg = self._resolve(
            payload={
                "source_id": "cam_pet",
                "source_url": "rtsp://x/y",
                "pipeline": {"prefilter": {"enabled": False}},
            },
            defaults_prefilter=PrefilterConfig(
                enabled=True,
                model_path="/models/yolo.xml",
                target_classes=["person"],
            ),
        )
        assert cfg.enabled is False

    def test_child_safety_omits_prefilter_uses_defaults(self):
        """When MCP Server omits prefilter, defaults must take effect verbatim."""
        defaults = PrefilterConfig(
            enabled=False,
            model_path="/models/yolo.xml",
            target_classes=["person"],
            min_confidence=0.4,
        )
        cfg = self._resolve(
            payload={
                "source_id": "cam_child",
                "source_url": "rtsp://x/y",
            },
            defaults_prefilter=defaults,
        )
        assert cfg is defaults

    def test_empty_pipeline_block_uses_defaults(self):
        """Empty `pipeline` block must inherit prefilter defaults wholesale."""
        defaults = PrefilterConfig(enabled=False, target_classes=["person"])
        for sid in ("cam_a", "cam_b", "cam_c"):
            cfg = self._resolve(
                payload={
                    "source_id": sid,
                    "source_url": "rtsp://x/y",
                    "pipeline": {},
                },
                defaults_prefilter=defaults,
            )
            assert cfg is defaults, f"source {sid} unexpectedly changed prefilter resolution"

    def test_partial_prefilter_payload_inherits_model_path(self):
        defaults = PrefilterConfig(
            enabled=True,
            model_path="/models/yolo.xml",
            target_classes=["person"],
            min_confidence=0.4,
        )
        cfg = self._resolve(
            payload={
                "source_id": "cam_child",
                "source_url": "rtsp://x/y",
                "pipeline": {
                    "prefilter": {
                        "min_confidence": 0.8,
                    }
                },
            },
            defaults_prefilter=defaults,
        )
        assert cfg.enabled is True
        assert cfg.model_path == "/models/yolo.xml"
        assert cfg.min_confidence == 0.8
