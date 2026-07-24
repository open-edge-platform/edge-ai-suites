"""Tests for ContinuousRecorder."""

import os
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path

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
        cfg = RecordingConfig(interval=5, fps=15, retention_days=3)
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
        # Phase 7: data_dir is the per-source root (already resolved by caller);
        # recorder appends "recordings/" without re-prepending source_id.
        expected = os.path.join(str(tmp_path), "recordings")
        assert os.path.isdir(expected)


class TestContinuousRecorderCleanup:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    @pytest.fixture
    def recorder(self, tmp_path, mock_sink):
        source = SourceConfig(
            source_id="test_cleanup", source_url="rtsp://localhost:8554/live/test"
        )
        cfg = RecordingConfig(interval=60, fps=15, retention_days=2)
        r = ContinuousRecorder(
            source=source,
            recording_cfg=cfg,
            data_dir=str(tmp_path),
            sink=mock_sink,
        )
        return r

    def test_cleanup_removes_old_directories(self, recorder):
        base = Path(recorder._output_dir)

        # Create old dir (4 days ago)
        old_date = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        old_dir = base / old_date
        old_dir.mkdir(parents=True)
        (old_dir / "segment.mp4").touch()

        # Create recent dir (today)
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = base / today
        today_dir.mkdir(parents=True)
        (today_dir / "segment.mp4").touch()

        recorder._cleanup_old_segments()

        assert not old_dir.exists()
        assert today_dir.exists()
        assert (today_dir / "segment.mp4").exists()

    def test_cleanup_ignores_non_date_dirs(self, recorder):
        base = Path(recorder._output_dir)
        misc_dir = base / "misc_data"
        misc_dir.mkdir(parents=True)
        (misc_dir / "file.txt").touch()

        recorder._cleanup_old_segments()

        assert misc_dir.exists()


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
        cfg = RecordingConfig(interval=3, fps=30, retention_days=5)
        return ContinuousRecorder(
            source=source,
            recording_cfg=cfg,
            data_dir=str(tmp_path),
            sink=mock_sink,
        )

    def test_recorder_produces_segments(self, recorder, mock_sink, tmp_path):
        """Recorder should produce at least 1 segment from a real video.

        Phase 7: events are nested envelope `{sourceId, type, timestamp, payload}`,
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
