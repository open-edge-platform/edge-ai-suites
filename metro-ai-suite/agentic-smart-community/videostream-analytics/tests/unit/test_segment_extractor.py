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

    def test_finish_short_segment_is_kept(self, tmp_path, video_frames):
        """min_duration is a cut-frequency guard, not a delete filter: a short
        segment (e.g. a motion-end tail) is still returned for emission."""
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
        assert result is not None
        assert os.path.exists(result.path)
        assert 0.2 <= result.duration_s <= 0.5

    def test_finish_with_zero_frames_returns_none(self, tmp_path):
        """An empty segment (0 frames written) is removed, not emitted."""
        config = SegmentConfig(max_duration=60.0, min_duration=2.0)
        extractor = SegmentExtractor(
            config=config,
            output_dir=str(tmp_path / "motion_events"),
            source_id="test_cam",
            fps=30.0,
            frame_size=(1280, 720),
        )
        extractor.start_segment()
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

    def test_output_codec_is_h264(self, extractor, video_frames):
        """Segments are browser-playable H.264 by construction — no post-hoc
        transcode pass exists anymore (rtsp_monitor emits the file as-is)."""
        extractor.start_segment()
        for frame in video_frames[:90]:
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is not None

        # stsd sample-entry fourcc: avc1 = H.264-in-mp4 (mp4v would be "mp4v").
        # Byte-probe instead of ffprobe — the production image ships none.
        with open(result.path, "rb") as f:
            data = f.read(64 * 1024)
        assert b"avc1" in data, "segment is not H.264 (no avc1 sample entry)"

    def test_output_has_faststart_moov(self, extractor, video_frames):
        """moov precedes mdat so the dashboard can seek with one range request."""
        extractor.start_segment()
        for frame in video_frames[:90]:
            extractor.add_frame(frame)
        result = extractor.finish()
        assert result is not None

        with open(result.path, "rb") as f:
            data = f.read()
        moov, mdat = data.find(b"moov"), data.find(b"mdat")
        assert 0 < moov < mdat, "moov must precede mdat (faststart)"

    def test_writer_open_failure_latches_and_recovers(self, tmp_path, video_frames, monkeypatch):
        """ffmpeg missing: segment is dropped with an error log, frames are
        counted (duration logic intact), and the NEXT segment retries."""
        from stream_monitor.pipeline import segment_extractor as se

        class DeadWriter:
            def __init__(self, *a, **k): pass
            def isOpened(self): return False
            def write(self, frame): pass
            def release(self): pass

        monkeypatch.setattr(se, "H264SegmentWriter", DeadWriter)
        extractor = SegmentExtractor(
            config=SegmentConfig(max_duration=5.0, min_duration=0.5),
            output_dir=str(tmp_path / "motion_events"),
            source_id="test_cam", fps=30.0, frame_size=(1280, 720),
        )
        extractor.start_segment()
        assert extractor.is_recording is False
        for frame in video_frames[:30]:
            assert extractor.add_frame(frame) is None
        assert extractor.finish() is None
        # Latch cleared by finish: next segment retries the writer.
        extractor.start_segment()
        assert extractor._write_failed is True  # DeadWriter still fails

    def test_writer_mid_segment_death_discards_segment(self, tmp_path, video_frames):
        """If the ffmpeg pipe dies mid-segment the mp4 has no moov — discard
        instead of emitting an unreadable file."""
        extractor = SegmentExtractor(
            config=SegmentConfig(max_duration=5.0, min_duration=0.5),
            output_dir=str(tmp_path / "motion_events"),
            source_id="test_cam", fps=30.0, frame_size=(1280, 720),
        )
        extractor.start_segment()
        for frame in video_frames[:30]:
            extractor.add_frame(frame)
        # Simulate ffmpeg dying mid-segment (broken pipe path in the writer).
        extractor._writer._proc = None
        result = extractor.finish()
        assert result is None
        assert extractor.is_recording is False
