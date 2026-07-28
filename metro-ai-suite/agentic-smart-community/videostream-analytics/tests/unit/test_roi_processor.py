"""Phase 9 — ROI crop helper (`prepare_roi_segment`) tests.

`prepare_roi_segment` is the worker that turns a finished motion clip into
`<stem>_input.mp4` — a zoomed-in / highlighted version VLM consumes. The
contract is **never raise**: any failure (bad path, tiny region, ffmpeg
missing) becomes `None` so the caller falls back to the original clip.

These tests use a tiny synthetic clip produced via cv2.VideoWriter so they
don't depend on real RTSP / a real model.
"""

from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from stream_monitor.pipeline.roi_processor import (
    _expand_roi,
    prepare_roi_segment,
)


@pytest.fixture
def tiny_clip(tmp_path):
    """Produce a 1 s, 320x240 BGR mp4v clip with a moving box."""
    path = str(tmp_path / "seg.mp4")
    w, h, fps = 320, 240, 15
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    assert writer.isOpened()
    for i in range(fps):
        frame = np.full((h, w, 3), 30, dtype=np.uint8)
        x = 100 + i * 5
        cv2.rectangle(frame, (x, 80), (x + 60, 160), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    assert os.path.exists(path)
    return path


class TestExpandRoi:
    def test_clamps_to_unit_range(self):
        # Box near corners + 0.5 expand → clamped at 0/1.
        cx1, cy1, cx2, cy2 = _expand_roi([0.05, 0.05, 0.95, 0.95], 0.5)
        assert cx1 == 0.0 and cy1 == 0.0
        assert cx2 == 1.0 and cy2 == 1.0

    def test_no_expand_returns_input(self):
        cx1, cy1, cx2, cy2 = _expand_roi([0.2, 0.3, 0.6, 0.7], 0.0)
        assert (cx1, cy1, cx2, cy2) == (0.2, 0.3, 0.6, 0.7)


class TestPrepareRoiSegment:
    def test_crop_mode_writes_input_mp4(self, tiny_clip):
        out = prepare_roi_segment(
            tiny_clip, [0.3, 0.3, 0.7, 0.7], mode="crop", expand=0.1,
        )
        assert out is not None
        assert out.endswith("_input.mp4")
        assert os.path.exists(out)
        # Verify it's a non-empty video readable by cv2.
        cap = cv2.VideoCapture(out)
        assert cap.isOpened()
        assert cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        cap.release()

    def test_invalid_path_returns_none(self, tmp_path):
        out = prepare_roi_segment(
            str(tmp_path / "does_not_exist.mp4"), [0.1, 0.1, 0.5, 0.5],
        )
        assert out is None

    def test_invalid_roi_returns_none(self, tiny_clip):
        # Wrong shape — must not raise.
        assert prepare_roi_segment(tiny_clip, []) is None
        assert prepare_roi_segment(tiny_clip, [0.1, 0.2]) is None

    def test_tiny_region_returns_none(self, tiny_clip):
        # Effective crop region < 32x32 px in a 320x240 frame.
        # ROI 0.5..0.55 × 0.5..0.55, no expand → 16x12 px after rounding.
        out = prepare_roi_segment(
            tiny_clip, [0.5, 0.5, 0.55, 0.55], mode="crop", expand=0.0,
        )
        assert out is None

    def test_ffmpeg_missing_keeps_mp4v(self, tiny_clip):
        """When ffmpeg fails, the mp4v output must still exist."""
        # Simulate ffmpeg missing via FileNotFoundError.
        with patch(
            "stream_monitor.pipeline.roi_processor.subprocess.run",
            side_effect=FileNotFoundError("no ffmpeg"),
        ):
            out = prepare_roi_segment(
                tiny_clip, [0.3, 0.3, 0.7, 0.7], mode="crop", expand=0.1,
            )
        assert out is not None
        assert os.path.exists(out)
        # No partial _h264 leftover.
        assert not os.path.exists(out.replace(".mp4", "_h264.mp4"))

    def test_ffmpeg_calledprocesserror_keeps_mp4v(self, tiny_clip):
        with patch(
            "stream_monitor.pipeline.roi_processor.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
        ):
            out = prepare_roi_segment(
                tiny_clip, [0.3, 0.3, 0.7, 0.7], mode="crop", expand=0.1,
            )
        assert out is not None
        assert os.path.exists(out)
