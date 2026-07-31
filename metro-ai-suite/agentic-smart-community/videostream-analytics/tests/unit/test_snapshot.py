"""Tests for latest.jpg snapshot writing.

Regression guard for the bug found during Phase 7 stage-A integration:
cv2.imwrite dispatches by file extension, so an `<x>.jpg.tmp` tmp filename
fails with "could not find a writer for the specified extension". The
exception was being swallowed by the broad try/except, making the failure
silent — no log line, no latest.jpg.

These tests directly drive `_maybe_write_snapshot()` so the bug is caught
at unit-test time, not at integration.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import cv2  # noqa: F401 — imported so test fails fast if env is broken
import numpy as np
import pytest

from shared.config import DefaultsConfig, PrefilterConfig, SourceConfig
from sinks import NullSink
from stream_monitor.rtsp_monitor import StreamPipeline


def _make_pipeline(tmp_path):
    source = SourceConfig(
        source_id="snap_cam",
        source_url="rtsp://x/y",
        prefilter=PrefilterConfig(enabled=False),
    )
    with patch("stream_monitor.rtsp_monitor.cv2.VideoCapture"):
        return StreamPipeline(
            source=source,
            defaults=DefaultsConfig(),
            data_dir=str(tmp_path),
            sink=NullSink(),
        )


class TestSnapshotWrite:
    def test_first_frame_writes_latest_jpg(self, tmp_path):
        """A single frame at frame_count=1 must produce latest.jpg.

        Catches the regression where tmp filename had wrong extension
        and cv2.imwrite raised silently.
        """
        pipeline = _make_pipeline(tmp_path)
        pipeline._fps = 15.0  # mimic post-connect
        pipeline._frame_count = 1
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        pipeline._maybe_write_snapshot(frame)

        latest = tmp_path / "latest.jpg"
        assert latest.exists(), (
            f"latest.jpg missing. Files in {tmp_path}: "
            f"{[p.name for p in tmp_path.iterdir()]}"
        )
        assert latest.stat().st_size > 0

    def test_jpg_is_valid_image(self, tmp_path):
        """Written file must be a real readable JPEG."""
        pipeline = _make_pipeline(tmp_path)
        pipeline._fps = 15.0
        pipeline._frame_count = 1
        # Use a non-trivial frame so JPEG isn't degenerate
        frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
        pipeline._maybe_write_snapshot(frame)

        img = cv2.imread(str(tmp_path / "latest.jpg"))
        assert img is not None, "latest.jpg unreadable as image"
        assert img.shape == (720, 1280, 3)

    def test_no_tmp_file_left_behind_on_success(self, tmp_path):
        """After atomic rename, no .tmp.jpg should remain."""
        pipeline = _make_pipeline(tmp_path)
        pipeline._fps = 15.0
        pipeline._frame_count = 1
        pipeline._maybe_write_snapshot(np.zeros((720, 1280, 3), dtype=np.uint8))

        stragglers = [p for p in tmp_path.iterdir() if p.name != "latest.jpg"]
        assert stragglers == [], f"unexpected files after rename: {stragglers}"

    def test_throttle_respects_snapshot_hz(self, tmp_path):
        """Second call before next_idx must NOT rewrite the file."""
        pipeline = _make_pipeline(tmp_path)
        pipeline._fps = 15.0
        pipeline._snapshot_hz = 1.0  # default: step = 15 frames
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Frame 1 → writes (snapshot_next_idx = 0, frame_count=1 >= 0)
        pipeline._frame_count = 1
        pipeline._maybe_write_snapshot(frame)
        mtime_first = (tmp_path / "latest.jpg").stat().st_mtime_ns

        # Frame 5 → should be throttled (next_idx is now 1 + 15 = 16)
        pipeline._frame_count = 5
        pipeline._maybe_write_snapshot(frame)
        mtime_after = (tmp_path / "latest.jpg").stat().st_mtime_ns
        assert mtime_first == mtime_after, "snapshot should be throttled"

        # Frame 20 → past next_idx, rewrites
        pipeline._frame_count = 20
        # bump time so mtime can differ
        import time as _time
        _time.sleep(0.01)
        pipeline._maybe_write_snapshot(frame)
        mtime_third = (tmp_path / "latest.jpg").stat().st_mtime_ns
        assert mtime_third > mtime_first, "snapshot should rewrite past throttle window"

    def test_none_frame_is_safe(self, tmp_path):
        """frame=None must early-return, not raise."""
        pipeline = _make_pipeline(tmp_path)
        pipeline._fps = 15.0
        pipeline._frame_count = 1
        # Must not raise
        pipeline._maybe_write_snapshot(None)
        assert not (tmp_path / "latest.jpg").exists()

    def test_tmp_filename_has_jpg_extension(self, tmp_path):
        """The tmp path must end in .jpg so cv2.imwrite can dispatch correctly.

        Direct regression test for the original bug — if someone reverts
        the path back to `<...>.jpg.tmp`, this test still catches it
        because the file would never appear.
        """
        # Reuse the above test logic but assert by reading the source
        import inspect
        from stream_monitor import rtsp_monitor
        src = inspect.getsource(rtsp_monitor.StreamPipeline._maybe_write_snapshot)
        # The tmp path must use a .jpg ending (not .jpg.tmp)
        assert ".jpg.tmp" not in src or '"latest.tmp.jpg"' in src, (
            "tmp filename appears to use '.jpg.tmp' suffix — "
            "cv2.imwrite cannot dispatch on .tmp extension; "
            "use '.tmp.jpg' instead"
        )
