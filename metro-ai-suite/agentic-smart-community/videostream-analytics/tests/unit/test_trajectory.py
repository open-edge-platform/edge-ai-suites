"""Phase 9 — trajectory accumulation + should_split early-cut.

Covers:
- `_postprocess` returns normalized xyxy alongside name/conf
- `FramePrefilter` accumulates union across hit frames
- `result()` clamps the union into [0, 1]
- `result.trajectory_region_xyxy is None` when there were no detections
- `should_split` threshold gating + disabled-by-zero / disabled-by-not-passed
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from stream_monitor.pipeline.prefilter_yolo import (
    FramePrefilter,
    PrefilterResult,
    _postprocess,
)


# ---------------------------------------------------------------------------
# _postprocess
# ---------------------------------------------------------------------------


def _yolo_output_one_box(cx: float, cy: float, bw: float, bh: float,
                         conf: float, class_id: int = 0,
                         nc: int = 80) -> np.ndarray:
    """Build a fake YOLO output tensor with a single detection above thresh."""
    n_anchors = 1
    out = np.zeros((1, 4 + nc, n_anchors), dtype=np.float32)
    out[0, 0, 0] = cx
    out[0, 1, 0] = cy
    out[0, 2, 0] = bw
    out[0, 3, 0] = bh
    out[0, 4 + class_id, 0] = conf
    return out


class TestPostprocessXyxy:
    def test_returns_xyxy_normalized(self):
        infer_w, infer_h = 640, 384
        out = _yolo_output_one_box(cx=320, cy=192, bw=200, bh=100, conf=0.9)
        dets = _postprocess(
            out, infer_w, infer_h,
            conf_thresh=0.4,
            class_names=["person"] + ["x"] * 79,
            target_classes=set(),
        )
        assert len(dets) == 1
        d = dets[0]
        assert d["name"] == "person"
        assert pytest.approx(d["conf"], abs=1e-5) == 0.9
        x1, y1, x2, y2 = d["xyxy"]
        # Center (320, 192), size 200×100 → corner (220,142)→(420,242)
        # Normalized: (220/640, 142/384) → (0.34375, 0.36979)
        assert pytest.approx(x1, abs=1e-3) == 220.0 / 640
        assert pytest.approx(y1, abs=1e-3) == 142.0 / 384
        assert pytest.approx(x2, abs=1e-3) == 420.0 / 640
        assert pytest.approx(y2, abs=1e-3) == 242.0 / 384

    def test_below_threshold_returns_empty(self):
        infer_w, infer_h = 320, 320
        out = _yolo_output_one_box(cx=160, cy=160, bw=80, bh=80, conf=0.1)
        dets = _postprocess(
            out, infer_w, infer_h,
            conf_thresh=0.4,
            class_names=["person"] + ["x"] * 79,
            target_classes=set(),
        )
        assert dets == []


# ---------------------------------------------------------------------------
# FramePrefilter union accumulation
# ---------------------------------------------------------------------------


def _fake_frame() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


@pytest.fixture
def yolo_mock():
    """A YoloPrefilter that returns whatever scripted detections we queue."""
    m = MagicMock()
    m.target_classes = {"person"}
    m._scripted_returns = []

    def predict(_frame):
        if m._scripted_returns:
            return m._scripted_returns.pop(0)
        return []

    m.predict.side_effect = predict
    return m


def _queue(yolo, *frames_dets):
    yolo._scripted_returns = list(frames_dets)


class TestFramePrefilterUnion:
    def test_accumulates_union_across_hits(self, yolo_mock):
        # Two frames, two distinct boxes → union is their bbox-bounding rect.
        _queue(
            yolo_mock,
            [{"name": "person", "conf": 0.9, "xyxy": [0.1, 0.1, 0.3, 0.4]}],
            [{"name": "person", "conf": 0.85, "xyxy": [0.5, 0.2, 0.7, 0.6]}],
        )
        pf = FramePrefilter(yolo_mock, detect_fps=2.0, min_frames_hit=1)
        pf.reset()
        pf.accumulate(_fake_frame(), src_fps=2.0)
        pf.accumulate(_fake_frame(), src_fps=2.0)
        # Force result() to bypass the empty-tail guard.
        result = pf.result()
        assert result.trajectory_region_xyxy is not None
        x0, y0, x1, y1 = result.trajectory_region_xyxy
        assert pytest.approx(x0) == 0.1
        assert pytest.approx(y0) == 0.1
        assert pytest.approx(x1) == 0.7
        assert pytest.approx(y1) == 0.6

    def test_result_clamps_union_into_unit_range(self, yolo_mock):
        # YOLO occasionally yields slightly out-of-bounds boxes — they must clamp.
        _queue(
            yolo_mock,
            [{"name": "person", "conf": 0.9, "xyxy": [-0.1, -0.05, 1.2, 1.3]}],
        )
        pf = FramePrefilter(yolo_mock, detect_fps=2.0, min_frames_hit=1)
        pf.reset()
        pf.accumulate(_fake_frame(), src_fps=2.0)
        result = pf.result()
        x0, y0, x1, y1 = result.trajectory_region_xyxy
        assert 0.0 <= x0 <= 1.0
        assert 0.0 <= y0 <= 1.0
        assert 0.0 <= x1 <= 1.0
        assert 0.0 <= y1 <= 1.0
        assert x0 == 0.0 and y0 == 0.0
        assert x1 == 1.0 and y1 == 1.0

    def test_no_detections_yields_none_trajectory(self, yolo_mock):
        # Three sampled frames, none with a hit.
        _queue(yolo_mock, [], [], [])
        pf = FramePrefilter(yolo_mock, detect_fps=2.0, min_frames_hit=1)
        pf.reset()
        pf.accumulate(_fake_frame(), src_fps=2.0)
        pf.accumulate(_fake_frame(), src_fps=2.0)
        pf.accumulate(_fake_frame(), src_fps=2.0)
        result = pf.result()
        assert result.passed is False
        assert result.trajectory_region_xyxy is None

    def test_reset_clears_union(self, yolo_mock):
        _queue(
            yolo_mock,
            [{"name": "person", "conf": 0.9, "xyxy": [0.1, 0.1, 0.3, 0.4]}],
        )
        pf = FramePrefilter(yolo_mock, detect_fps=2.0, min_frames_hit=1)
        pf.reset()
        pf.accumulate(_fake_frame(), src_fps=2.0)
        assert pf._union is not None
        pf.reset()
        assert pf._union is None
        # And reset_for_next_segment too
        pf._union = [0.0, 0.0, 0.5, 0.5]
        pf.reset_for_next_segment()
        assert pf._union is None


# ---------------------------------------------------------------------------
# should_split
# ---------------------------------------------------------------------------


class TestShouldSplit:
    def _pf_with_union_passed(self, yolo_mock, union):
        pf = FramePrefilter(yolo_mock, detect_fps=2.0, min_frames_hit=1)
        pf.reset()
        pf._union = list(union)
        pf._pass_decided = True
        return pf

    def test_above_threshold_returns_true(self, yolo_mock):
        # Box 0..0.7 × 0..0.7 → area 0.49 > 0.35
        pf = self._pf_with_union_passed(yolo_mock, [0.0, 0.0, 0.7, 0.7])
        assert pf.should_split(0.35) is True

    def test_below_threshold_returns_false(self, yolo_mock):
        pf = self._pf_with_union_passed(yolo_mock, [0.0, 0.0, 0.3, 0.3])
        # area 0.09 < 0.35
        assert pf.should_split(0.35) is False

    def test_disabled_by_zero_threshold(self, yolo_mock):
        pf = self._pf_with_union_passed(yolo_mock, [0.0, 0.0, 1.0, 1.0])
        assert pf.should_split(0.0) is False

    def test_skipped_when_not_passed_yet(self, yolo_mock):
        pf = FramePrefilter(yolo_mock, detect_fps=2.0, min_frames_hit=1)
        pf.reset()
        pf._union = [0.0, 0.0, 0.8, 0.8]
        pf._pass_decided = False  # explicit
        assert pf.should_split(0.35) is False
