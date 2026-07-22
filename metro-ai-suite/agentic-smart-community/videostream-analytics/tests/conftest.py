"""Shared test fixtures for videostream-analytics tests."""

from pathlib import Path

import cv2
import pytest

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
PROJECT_DIR = TESTS_DIR.parent
REPO_DIR = PROJECT_DIR.parent

TEST_VIDEO_PATH = REPO_DIR / "demo-videos" / "cam_child" / "child_safety_demo.mp4"


@pytest.fixture
def test_video_path():
    """Path to the test video file."""
    assert TEST_VIDEO_PATH.exists(), f"Test video not found: {TEST_VIDEO_PATH}"
    return str(TEST_VIDEO_PATH)


@pytest.fixture
def video_capture(test_video_path):
    """OpenCV VideoCapture on the test video, auto-released after test."""
    cap = cv2.VideoCapture(test_video_path)
    assert cap.isOpened(), f"Cannot open video: {test_video_path}"
    yield cap
    cap.release()


@pytest.fixture
def video_frames(video_capture):
    """Read 600 frames starting from frame 1200 (40s in) to capture motion region."""
    video_capture.set(cv2.CAP_PROP_POS_FRAMES, 1200)
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
