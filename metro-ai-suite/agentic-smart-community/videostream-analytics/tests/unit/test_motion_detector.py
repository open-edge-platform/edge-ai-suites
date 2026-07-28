"""Tests for MotionDetector using real video frames."""

import cv2
import numpy as np
import pytest

from shared.config import MotionConfig
from stream_monitor.pipeline.motion_detector import MotionDetector


class TestMotionDetectorWithRealVideo:
    def test_first_frame_returns_false(self, video_frames):
        detector = MotionDetector(MotionConfig())
        result = detector.detect(video_frames[0])
        assert result is False

    def test_detects_motion_in_video(self, video_frames):
        """child_safety_demo.mp4 contains a moving child — should detect motion."""
        detector = MotionDetector(MotionConfig())
        motion_count = 0
        for frame in video_frames:
            if detector.detect(frame):
                motion_count += 1
        assert motion_count > 0, (
            f"Should detect motion in child safety video "
            f"(checked {len(video_frames)} frames starting from 40s)"
        )

    def test_motion_ratio_reasonable(self, video_frames):
        """With a sensitive threshold, motion should be detected in some frames."""
        detector = MotionDetector(MotionConfig(area_ratio=0.005))
        motion_count = sum(1 for f in video_frames if detector.detect(f))
        ratio = motion_count / len(video_frames)
        assert ratio > 0, f"Motion ratio {ratio:.4f} — expected > 0 with sensitive threshold"

    def test_static_detection_after_identical_frames(self):
        """Feeding identical frames should trigger is_static."""
        detector = MotionDetector(MotionConfig(stable_frames=5))
        static_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # First frame
        detector.detect(static_frame)
        # Feed 10 identical frames
        for _ in range(10):
            detector.detect(static_frame)
        assert detector.is_static is True

    def test_motion_resets_static_count(self, video_frames):
        """After detecting motion, is_static should be False."""
        detector = MotionDetector(MotionConfig(stable_frames=5))
        # Feed frames until motion is detected
        for frame in video_frames[:300]:
            if detector.detect(frame):
                assert detector.is_static is False
                break

    def test_reset_clears_state(self, video_frames):
        detector = MotionDetector(MotionConfig())
        detector.detect(video_frames[0])
        detector.detect(video_frames[1])
        detector.reset()
        assert detector._prev_gray is None
        assert detector._static_count == 0

    def test_sensitive_threshold_detects_more(self, video_frames):
        """Lower area_ratio should detect more motion."""
        normal = MotionDetector(MotionConfig(area_ratio=0.015))
        sensitive = MotionDetector(MotionConfig(area_ratio=0.005))

        normal_count = sum(1 for f in video_frames if normal.detect(f))
        sensitive_count = sum(1 for f in video_frames if sensitive.detect(f))
        assert sensitive_count >= normal_count

    def test_high_threshold_detects_less(self, video_frames):
        """Higher diff_threshold should detect less motion."""
        normal = MotionDetector(MotionConfig(diff_threshold=25))
        strict = MotionDetector(MotionConfig(diff_threshold=60))

        normal_count = sum(1 for f in video_frames if normal.detect(f))
        strict_count = sum(1 for f in video_frames if strict.detect(f))
        assert strict_count <= normal_count

    def test_works_with_different_resolutions(self, video_frames):
        """Should work regardless of frame resolution."""
        detector = MotionDetector(MotionConfig())
        # Resize to 320x240
        small_frames = [cv2.resize(f, (320, 240)) for f in video_frames[:30]]
        results = [detector.detect(f) for f in small_frames]
        assert isinstance(results[0], bool)
