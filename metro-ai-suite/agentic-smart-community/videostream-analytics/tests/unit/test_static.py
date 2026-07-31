"""Unit tests for `type=static` close-out emission (VSA side).

Drives `_process_loop` directly with a synthetic frame sequence
(motion → quiet → motion) through a fake VideoCapture, and a fake wall-clock
so the quiet-period duration is deterministic regardless of test speed.

Asserts the strict Motion → static → Motion close-out model:
  * a `static` envelope is emitted when the quiet span ≥ min_duration,
  * its payload carries start_time / end_time / duration_seconds,
  * a quiet span shorter than min_duration is suppressed,
  * a quiet period open at shutdown is drained as a final static,
  * no leading static is fabricated before the first motion.
"""

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from shared.config import (
    SourceConfig,
    DefaultsConfig,
    MotionConfig,
    SegmentConfig,
    StaticConfig,
    PrefilterConfig,
    HealthConfig,
)
from stream_monitor import rtsp_monitor
from stream_monitor.rtsp_monitor import StreamPipeline
from sinks import EventSink


H, W = 48, 64
BLACK = np.zeros((H, W, 3), np.uint8)
WHITE = np.full((H, W, 3), 255, np.uint8)
GRAY = np.full((H, W, 3), 127, np.uint8)
FPS = 10.0
DT = 1.0 / FPS


class _Clock:
    """Monotone fake wall-clock advanced one frame-interval per cap.read()."""

    def __init__(self, start: float = 1000.0):
        self.t = start

    def tick(self, dt: float):
        self.t += dt

    def time(self) -> float:
        return self.t


class _FakeCap:
    """Minimal cv2.VideoCapture stand-in that plays a scripted frame list."""

    def __init__(self, frames, clock: _Clock):
        self._frames = frames
        self._i = 0
        self._clock = clock

    def isOpened(self):
        return True

    def read(self):
        # Advance the fake wall-clock exactly one frame interval per read, so
        # the static duration reflects the number of quiet frames consumed.
        self._clock.tick(DT)
        if self._i < len(self._frames):
            frame = self._frames[self._i]
            self._i += 1
            return True, frame.copy()
        return False, None

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return FPS
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return W
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return H
        return 0

    def release(self):
        pass


def _make_pipeline(data_dir, sink, static_cfg: StaticConfig):
    source = SourceConfig(source_id="cam_static", source_url="fake://stream")
    defaults = DefaultsConfig(
        # stable_frames=3 → motion ends quickly once frames go quiet.
        motion=MotionConfig(diff_threshold=25, area_ratio=0.015, stable_frames=3),
        segment=SegmentConfig(max_duration=10.0, min_duration=0.0),
        static=static_cfg,
        # keep prefilter off so _should_exit_motion == detector.is_static
        prefilter=PrefilterConfig(enabled=False),
        # low threshold so a handful of trailing failed reads ends the loop
        health=HealthConfig(max_failures=3),
    )
    return StreamPipeline(source=source, defaults=defaults, data_dir=data_dir, sink=sink)


def _run(pipeline, frames, clock):
    """Drive _process_loop once over a scripted frame list + trailing EOF."""
    pipeline._cap = _FakeCap(frames, clock)
    pipeline._fps = FPS
    pipeline._running = True
    with patch.object(rtsp_monitor.time, "time", clock.time):
        pipeline._process_loop()


def _static_events(sink):
    return [
        call.args[0]
        for call in sink.emit.call_args_list
        if call.args and call.args[0].get("type") == "static"
    ]


# motion (alternating) → long quiet (gray) → motion again → EOF.
# No trailing padding: once the list is exhausted _FakeCap.read() returns
# False, and health.max_failures=3 consecutive failures end _process_loop.
# (Repeated identical padding frames would themselves read as a new quiet
# period and emit a spurious static.)
_SEQ_MOTION_QUIET_MOTION = (
    [BLACK, WHITE] * 4          # ~8 frames of motion
    + [GRAY] * 40               # quiet period (~4s of wall-clock)
    + [WHITE, BLACK, WHITE]     # second motion → closes out the quiet period
)


@pytest.fixture
def data_dir(tmp_path):
    return str(tmp_path / "static_data")


@pytest.fixture
def mock_sink():
    sink = MagicMock(spec=EventSink)
    sink.emit.return_value = True
    return sink


def test_static_emitted_between_two_motions(data_dir, mock_sink):
    """Quiet span between two motions (≥ min_duration) is emitted as static."""
    clock = _Clock()
    pipeline = _make_pipeline(
        data_dir, mock_sink, StaticConfig(enabled=True, min_duration=1.0)
    )
    _run(pipeline, list(_SEQ_MOTION_QUIET_MOTION), clock)

    events = _static_events(mock_sink)
    assert len(events) >= 1, "Expected at least one static event"

    ev = events[0]
    assert ev["sourceId"] == "cam_static"
    payload = ev["payload"]
    assert isinstance(payload["start_time"], str)
    assert isinstance(payload["end_time"], str)
    assert payload["duration_seconds"] >= 1.0, payload


def test_short_quiet_period_suppressed(data_dir, mock_sink):
    """A quiet span shorter than min_duration is NOT emitted."""
    clock = _Clock()
    # Same ~4s quiet span, but min_duration raised above it → suppressed.
    pipeline = _make_pipeline(
        data_dir, mock_sink, StaticConfig(enabled=True, min_duration=60.0)
    )
    _run(pipeline, list(_SEQ_MOTION_QUIET_MOTION), clock)

    assert _static_events(mock_sink) == [], "Sub-threshold quiet should not emit"


def test_static_drained_on_shutdown(data_dir, mock_sink):
    """A quiet period still open at shutdown is drained as a final static."""
    clock = _Clock()
    pipeline = _make_pipeline(
        data_dir, mock_sink, StaticConfig(enabled=True, min_duration=1.0)
    )
    # motion → long quiet → EOF (no second motion): drain must close it out.
    seq = [BLACK, WHITE] * 4 + [GRAY] * 40
    _run(pipeline, seq, clock)

    events = _static_events(mock_sink)
    assert len(events) == 1, f"Expected exactly one drained static, got {len(events)}"
    assert events[0]["payload"]["duration_seconds"] >= 1.0


def test_no_leading_static_before_first_motion(data_dir, mock_sink):
    """Startup → first motion is system uptime, never emitted as static."""
    clock = _Clock()
    pipeline = _make_pipeline(
        data_dir, mock_sink, StaticConfig(enabled=True, min_duration=0.0)
    )
    # Long quiet FIRST (no prior motion), then a motion, then EOF.
    seq = [GRAY] * 40 + [WHITE, BLACK, WHITE]
    _run(pipeline, seq, clock)

    # The leading quiet has no preceding motion to close out → no static.
    # (The trailing motion is still open at EOF → drained as motion, not static.)
    assert _static_events(mock_sink) == []


def test_static_disabled_emits_nothing(data_dir, mock_sink):
    """With static.enabled=False, no static events regardless of quiet spans."""
    clock = _Clock()
    pipeline = _make_pipeline(
        data_dir, mock_sink, StaticConfig(enabled=False, min_duration=0.0)
    )
    _run(pipeline, list(_SEQ_MOTION_QUIET_MOTION), clock)

    assert _static_events(mock_sink) == []
