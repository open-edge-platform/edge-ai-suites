"""Tests for ContinuousRecorder."""

import os
import time
from unittest.mock import MagicMock

import pytest

from shared.config import RecordingConfig, SourceConfig
from stream_monitor.continuous_recorder import ContinuousRecorder
from stream_monitor.base_monitor import BaseMonitor
from sinks import EventSink


class TestContinuousRecorderLifecycle:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    @pytest.fixture
    def recorder(self, tmp_path, mock_sink):
        source = SourceConfig(
            source_id="test_recorder", source_url="rtsp://localhost:8554/live/test"
        )
        cfg = RecordingConfig(interval=5, fps=15)
        return ContinuousRecorder(
            source=source,
            recording_cfg=cfg,
            data_dir=str(tmp_path),
            sink=mock_sink,
        )

    def test_inherits_base_monitor(self, recorder):
        assert isinstance(recorder, BaseMonitor)

    def test_initial_status_is_stopped(self, recorder):
        assert recorder.status == "stopped"
        assert recorder.is_running is False

    def test_pause_sets_status(self, recorder):
        recorder._running = True
        recorder._status = "recording"
        recorder.pause()
        assert recorder.status == "paused"
        assert not recorder._paused.is_set()

    def test_resume_sets_status(self, recorder):
        recorder._running = True
        recorder._status = "paused"
        recorder._paused.clear()
        recorder.resume()
        assert recorder.status == "recording"
        assert recorder._paused.is_set()

    def test_pause_when_not_running_is_noop(self, recorder):
        recorder._running = False
        recorder.pause()
        assert recorder.status == "stopped"

    def test_resume_when_not_paused_is_noop(self, recorder):
        recorder._running = True
        recorder._status = "recording"
        recorder.resume()
        assert recorder.status == "recording"

    def test_stop_unblocks_paused(self, recorder):
        recorder._running = True
        recorder._paused.clear()
        recorder.stop()
        assert recorder._paused.is_set()
        assert recorder.status == "stopped"

    def test_output_dir_created(self, recorder, tmp_path):
        # data_dir is the per-source root (already resolved by caller);
        # recorder appends "recordings/" without re-prepending source_id.
        expected = os.path.join(str(tmp_path), "recordings")
        assert os.path.isdir(expected)


class TestContinuousRecorderWithVideo:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    @pytest.fixture
    def recorder(self, test_video_path, tmp_path, mock_sink):
        source = SourceConfig(
            source_id="test_recording",
            source_url=test_video_path,
        )
        cfg = RecordingConfig(interval=3, fps=30)
        return ContinuousRecorder(
            source=source,
            recording_cfg=cfg,
            data_dir=str(tmp_path),
            sink=mock_sink,
        )

    def test_recorder_produces_segments(self, recorder, mock_sink, tmp_path):
        """Recorder should produce at least 1 segment from a real video.

        Events use the nested envelope `{sourceId, type, timestamp, payload}`;
        recording payload uses `recording_path` (not `clip_path`).
        """
        recorder.start()
        time.sleep(8)
        recorder.stop()

        recording_events = [
            call.args[0] for call in mock_sink.emit.call_args_list
            if call.args[0].get("type") == "recording"
        ]
        assert len(recording_events) >= 1

        event = recording_events[0]
        assert event["sourceId"] == "test_recording"
        payload = event["payload"]
        assert payload["duration_seconds"] > 0
        assert payload["recording_path"].endswith(".mp4")
        assert os.path.exists(payload["recording_path"])
        assert "recording_start" in payload
        assert "recording_end" in payload
        assert "file_size_bytes" in payload
