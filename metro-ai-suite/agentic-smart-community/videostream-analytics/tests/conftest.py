"""Shared test fixtures for videostream-analytics tests."""

from pathlib import Path

import cv2
import numpy as np
import pytest

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture(scope="session")
def test_video_path(tmp_path_factory):
    """Create a short MP4 with deterministic motion for video pipeline tests."""
    video_path = tmp_path_factory.mktemp("video") / "moving-square.mp4"
    width, height, fps, frame_count = 1280, 720, 30, 900
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    assert writer.isOpened(), "Cannot create temporary test video"

    for frame_index in range(frame_count):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        x_position = (frame_index * 10) % (width - 160)
        cv2.rectangle(frame, (x_position, 270), (x_position + 160, 450), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()

    return str(video_path)


@pytest.fixture
def video_capture(test_video_path):
    """OpenCV VideoCapture on the test video, auto-released after test."""
    cap = cv2.VideoCapture(test_video_path)
    assert cap.isOpened(), f"Cannot open video: {test_video_path}"
    yield cap
    cap.release()


@pytest.fixture
def video_frames(video_capture):
    """Read enough frames to exercise deterministic motion detection."""
    video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    frames = []
    for _ in range(600):
        ret, frame = video_capture.read()
        if not ret:
            break
        frames.append(frame)
    assert len(frames) > 0, "No frames read from video"
    return frames


@pytest.fixture
def test_config_path():
    """Path to the test config YAML."""
    return str(FIXTURES_DIR / "test_config.yaml")
