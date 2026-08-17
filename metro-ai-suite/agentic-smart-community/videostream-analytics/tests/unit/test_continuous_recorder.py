"""Tests for ContinuousRecorder."""

import os
import subprocess
import time
from unittest.mock import MagicMock

import pytest

from shared.config import RecordingConfig, SourceConfig, merge_config
from stream_monitor.continuous_recorder import ContinuousRecorder
from stream_monitor.base_monitor import BaseMonitor
from sinks import EventSink


def make_recorder(tmp_path, sink, backend="copy", interval=5, fps=15, source_id="test_recorder", source_url="rtsp://localhost:8554/live/test"):
    source = SourceConfig(source_id=source_id, source_url=source_url)
    cfg = RecordingConfig(interval=interval, fps=fps, backend=backend)
    return ContinuousRecorder(
        source=source,
        recording_cfg=cfg,
        data_dir=str(tmp_path),
        sink=sink,
    )


class TestRecordingConfigBackend:
    def test_default_backend_is_copy(self):
        assert RecordingConfig().backend == "copy"

    def test_x264_backend_accepted(self):
        assert RecordingConfig(backend="x264").backend == "x264"

    def test_invalid_backend_rejected(self):
        with pytest.raises(Exception):
            RecordingConfig(backend="bogus")

    def test_merge_config_keeps_default_backend(self):
        merged = merge_config(RecordingConfig(), RecordingConfig(interval=30))
        assert merged.backend == "copy"
        assert merged.interval_seconds == 30


class TestContinuousRecorderLifecycle:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    @pytest.fixture
    def recorder(self, tmp_path, mock_sink):
        return make_recorder(tmp_path, mock_sink)

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


def recording_events(sink):
    return [
        call.args[0] for call in sink.emit.call_args_list
        if call.args[0].get("type") == "recording"
    ]


def assert_recording_event_contract(event, source_id):
    assert event["sourceId"] == source_id
    payload = event["payload"]
    assert payload["duration_seconds"] > 0
    assert payload["recording_path"].endswith(".mp4")
    assert os.path.exists(payload["recording_path"])
    assert "recording_start" in payload
    assert "recording_end" in payload
    assert "file_size_bytes" in payload
    # recordings must stay under <data_dir>/recordings/<YYYY-MM-DD>/ —
    # MCP storage-cleaner prunes by that date-dir layout.
    assert os.path.basename(os.path.dirname(payload["recording_path"])).count("-") == 2


@pytest.mark.parametrize("backend", ["copy", "x264"])
class TestContinuousRecorderWithVideo:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    @pytest.fixture
    def recorder(self, test_video_path, tmp_path, mock_sink, backend):
        return make_recorder(
            tmp_path, mock_sink, backend=backend, interval=2, fps=30,
            source_id="test_recording", source_url=test_video_path,
        )

    def test_recorder_produces_segments(self, recorder, mock_sink, backend):
        """Recorder should produce at least 1 segment from a real video.

        Events use the nested envelope `{sourceId, type, timestamp, payload}`;
        recording payload uses `recording_path` (not `clip_path`).
        """
        recorder.start()
        time.sleep(8)
        recorder.stop()

        events = recording_events(mock_sink)
        assert len(events) >= 1
        assert_recording_event_contract(events[0], "test_recording")

        payload = events[0]["payload"]
        # copy backend: duration comes from ffmpeg's segment list (packet
        # timeline), so a full segment ≈ the configured interval.
        if backend == "copy":
            assert 1.5 <= payload["duration_seconds"] <= 3.5


class TestCopyBackend:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    def test_pause_mid_segment_emits_partial(self, test_video_path, tmp_path, mock_sink):
        """Pausing mid-segment SIGINTs ffmpeg; the partial segment is finalized
        and emitted (same contract as the x264 backend's paused cut)."""
        recorder = make_recorder(
            tmp_path, mock_sink, interval=30,
            source_id="test_pause", source_url=test_video_path,
        )
        recorder.start()
        time.sleep(4)
        recorder.pause()
        # pause -> finalize -> emit happens in the recorder thread; give it a moment
        time.sleep(1)
        try:
            assert recorder.status == "paused"
            events = recording_events(mock_sink)
            assert len(events) == 1
            payload = events[0]["payload"]
            assert 2.0 <= payload["duration_seconds"] <= 8.0
            assert_recording_event_contract(events[0], "test_pause")
        finally:
            recorder.stop()

    def test_stop_mid_segment_emits_partial(self, test_video_path, tmp_path, mock_sink):
        recorder = make_recorder(
            tmp_path, mock_sink, interval=30,
            source_id="test_stop", source_url=test_video_path,
        )
        recorder.start()
        time.sleep(4)
        recorder.stop()

        assert recorder.status == "stopped"
        events = recording_events(mock_sink)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert 2.0 <= payload["duration_seconds"] <= 8.0

    def test_no_list_files_left_behind(self, test_video_path, tmp_path, mock_sink):
        recorder = make_recorder(
            tmp_path, mock_sink, interval=2,
            source_id="test_clean", source_url=test_video_path,
        )
        recorder.start()
        time.sleep(5)
        recorder.stop()

        leftovers = [
            n for n in os.listdir(os.path.join(str(tmp_path), "recordings"))
            if n.startswith(".segments_")
        ]
        assert leftovers == []

    def test_segment_start_from_path(self, tmp_path, mock_sink):
        recorder = make_recorder(tmp_path, mock_sink)
        path = "/data/recordings/2026-08-17/cam1_132045.mp4"
        dt = recorder._segment_start_from_path(path)
        assert dt is not None
        assert (dt.year, dt.month, dt.day) == (2026, 8, 17)
        assert (dt.hour, dt.minute, dt.second) == (13, 20, 45)

    def test_segment_start_from_path_bad_input(self, tmp_path, mock_sink):
        recorder = make_recorder(tmp_path, mock_sink)
        assert recorder._segment_start_from_path("/data/recordings/cam1.mp4") is None

    def test_drain_skips_malformed_lines(self, tmp_path, mock_sink):
        recorder = make_recorder(tmp_path, mock_sink)
        list_path = os.path.join(str(tmp_path), "recordings", ".list.csv")
        with open(list_path, "w") as f:
            f.write("garbage\n")
            f.write("no-floats,here,please\n")
            f.write("missing.mp4,0.000000,4.000000\n")  # file doesn't exist
        emitted = set()
        recorder._drain_segment_list(list_path, emitted)
        mock_sink.emit.assert_not_called()
        assert emitted == set()

    def test_finalize_ffmpeg_interrupts_long_process(self, tmp_path, mock_sink):
        recorder = make_recorder(tmp_path, mock_sink)
        proc = subprocess.Popen(["sleep", "60"])
        start = time.monotonic()
        recorder._finalize_ffmpeg(proc)
        elapsed = time.monotonic() - start
        assert proc.poll() is not None
        assert elapsed < 10

    def test_connection_error_reconnects_and_stops(self, mock_sink, tmp_path):
        """Unreachable source: copy session fails fast, _run backs off, stop() exits."""
        recorder = make_recorder(
            tmp_path, mock_sink, interval=2,
            source_id="test_down", source_url="rtsp://127.0.0.1:1/none",
        )
        recorder.start()
        time.sleep(3)
        recorder.stop()
        assert recorder.status == "stopped"
        # no recording events for a dead source
        assert recording_events(mock_sink) == []
