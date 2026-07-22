"""Tests for SegmentExtractor using real video frames."""

import os

import cv2
import pytest

from shared.config import SegmentConfig
from stream_monitor.pipeline.segment_extractor import SegmentExtractor, SegmentResult


class TestSegmentExtractorWithRealVideo:
    @pytest.fixture
    def extractor(self, tmp_path):
        config = SegmentConfig(max_duration=5.0, min_duration=0.5)
        return SegmentExtractor(
            config=config,
            output_dir=str(tmp_path / "motion_events"),
            source_id="test_cam",
            fps=30.0,
            frame_size=(1280, 720),
        )

    def test_start_segment_enables_recording(self, extractor):
        extractor.start_segment()
        assert extractor.is_recording is True

    def test_add_frames_below_interval_returns_none(self, extractor, video_frames):
        """Adding frames below the interval threshold should not produce a result."""
        extractor.start_segment()
        # Add 30 frames (1 second at 30fps) — well below 5s interval
        for frame in video_frames[:30]:
            result = extractor.add_frame(frame)
        assert result is None
        assert extractor.is_recording is True

    def test_interval_reached_produces_segment(self, extractor, video_frames):
        """Adding enough frames to exceed interval should produce a SegmentResult."""
        extractor.start_segment()
        result = None
        # 5s interval × 30fps = 150 frames needed
        for frame in video_frames[:160]:
            r = extractor.add_frame(frame)
            if r is not None:
                result = r
                break
        assert result is not None
        assert isinstance(result, SegmentResult)

    def test_finish_produces_segment(self, extractor, video_frames):
        """Calling finish() mid-recording should produce a valid segment."""
        extractor.start_segment()
        for frame in video_frames[:90]:  # 3s of frames
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is not None
        assert isinstance(result, SegmentResult)
        assert 2.5 <= result.duration_s <= 3.5

    def test_output_file_exists_and_readable(self, extractor, video_frames):
        """Produced clip file should exist and be openable by OpenCV."""
        extractor.start_segment()
        for frame in video_frames[:90]:
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is not None
        assert os.path.exists(result.path)
        assert result.file_size > 0

        cap = cv2.VideoCapture(result.path)
        assert cap.isOpened()
        frame_count = 0
        while True:
            ret, _ = cap.read()
            if not ret:
                break
            frame_count += 1
        cap.release()
        assert frame_count > 0

    def test_output_frame_count_matches_duration(self, extractor, video_frames):
        """Frame count in output file should match frames written."""
        extractor.start_segment()
        result = None
        # 5s interval × 30fps = 150 frames
        for frame in video_frames[:160]:
            r = extractor.add_frame(frame)
            if r is not None:
                result = r
                break
        assert result is not None

        cap = cv2.VideoCapture(result.path)
        frame_count = 0
        while cap.read()[0]:
            frame_count += 1
        cap.release()

        expected = 30.0 * 5.0  # fps × interval
        assert abs(frame_count - expected) / expected < 0.1, (
            f"Frame count {frame_count} too far from expected {expected}"
        )

    def test_duration_in_result(self, extractor, video_frames):
        """SegmentResult duration should reflect actual frames written."""
        extractor.start_segment()
        result = None
        for frame in video_frames[:160]:
            r = extractor.add_frame(frame)
            if r is not None:
                result = r
                break
        assert result is not None
        assert 4.5 <= result.duration_s <= 5.5

    def test_finish_below_min_duration_returns_none(self, tmp_path, video_frames):
        """Segment shorter than min_duration should be discarded."""
        config = SegmentConfig(max_duration=60.0, min_duration=2.0)
        extractor = SegmentExtractor(
            config=config,
            output_dir=str(tmp_path / "motion_events"),
            source_id="test_cam",
            fps=30.0,
            frame_size=(1280, 720),
        )
        extractor.start_segment()
        # Write only 10 frames (0.33s < 2.0s min_duration)
        for frame in video_frames[:10]:
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is None

    def test_output_directory_has_date_structure(self, extractor, video_frames):
        """Output path should include date subdirectory."""
        extractor.start_segment()
        for frame in video_frames[:90]:
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is not None
        parts = result.path.split(os.sep)
        date_parts = [p for p in parts if len(p) == 10 and p[4] == "-" and p[7] == "-"]
        assert len(date_parts) == 1

    def test_filename_contains_source_id(self, extractor, video_frames):
        """Output filename should include the source_id."""
        extractor.start_segment()
        for frame in video_frames[:90]:
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is not None
        filename = os.path.basename(result.path)
        assert "test_cam" in filename

    def test_close_releases_writer(self, extractor, video_frames):
        extractor.start_segment()
        for frame in video_frames[:10]:
            extractor.add_frame(frame)
        extractor.close()
        assert extractor.is_recording is False
