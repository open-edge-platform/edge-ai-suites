# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.stream_manager._calculate_scaled_dimensions."""

from __future__ import annotations

import errno
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from backend.services import stream_manager as stream_manager_module
from backend.services.stream_manager import StreamManager
from backend.services.stream_manager import StreamHealth
from backend.services.stream_manager import _calculate_scaled_dimensions
from backend.services.stream_manager import _close_quietly
from backend.services.stream_manager import _encode_frame_jpeg_bytes


class TestCalculateScaledDimensions:
    def test_landscape_16_9_uses_16_9_preset(self):
        assert _calculate_scaled_dimensions(1920, 1080) == stream_manager_module.settings.SEGMENT_DIM_16_9

    def test_landscape_4_3_uses_4_3_preset(self):
        assert _calculate_scaled_dimensions(640, 480) == stream_manager_module.settings.SEGMENT_DIM_4_3

    def test_square_uses_1_1_preset(self):
        assert _calculate_scaled_dimensions(500, 500) == stream_manager_module.settings.SEGMENT_DIM_1_1

    def test_portrait_swaps_width_and_height_of_matching_preset(self):
        landscape_w, landscape_h = _calculate_scaled_dimensions(1920, 1080)
        portrait_w, portrait_h = _calculate_scaled_dimensions(1080, 1920)

        assert (portrait_w, portrait_h) == (landscape_h, landscape_w)

    def test_picks_nearest_preset_for_unusual_aspect_ratio(self, monkeypatch):
        # An ultra-wide source (21:9 ~= 2.33) is closer to 16:9 (1.78) than 4:3 (1.33) or 1:1.
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_DIM_1_1", (100, 100))
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_DIM_4_3", (120, 90))
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_DIM_16_9", (160, 90))

        assert _calculate_scaled_dimensions(2100, 900) == (160, 90)

    def test_rounds_odd_preset_dimensions_down_to_even(self, monkeypatch):
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_DIM_16_9", (577, 321))

        width, height = _calculate_scaled_dimensions(1920, 1080)

        assert width % 2 == 0
        assert height % 2 == 0
        assert (width, height) == (576, 320)

    def test_portrait_4_3_uses_matching_orientation(self):
        assert _calculate_scaled_dimensions(480, 640) == (384, 512)

    def test_matches_nearest_preset_for_around_1_33_ratio(self):
        assert _calculate_scaled_dimensions(800, 600) == stream_manager_module.settings.SEGMENT_DIM_4_3


class TestStreamManagerHelpers:
    def test_non_rtsp_input_has_no_options(self):
        mgr = StreamManager("stream-1", "file:///camera.mp4")

        assert mgr._input_options() == {}

    def test_source_fps_returns_zero_for_invalid_rate(self):
        class _FakeStream:
            average_rate = "invalid"

        assert StreamManager._source_fps(_FakeStream()) == 0.0

    def test_health_returns_independent_snapshot(self):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        mgr.health = StreamHealth(
            publishing=True,
            resolution="640x360",
            codec="h264",
            caption="Decision: No",
            caption_history=[{"response": "old"}],
            ttft_ms=5.0,
        )

        snapshot = mgr.get_health()
        snapshot.caption_history.append({"response": "mutated"})

        assert snapshot.publishing is True
        assert snapshot.resolution == "640x360"
        assert mgr.health.caption_history == [{"response": "old"}]

    def test_start_does_not_start_twice_without_prompt(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        started = []

        class _Thread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def start(self):
                started.append(self.kwargs["name"])

            def join(self, timeout):
                return None

        monkeypatch.setattr(stream_manager_module.threading, "Thread", _Thread)
        monkeypatch.setattr(mgr, "_stream_loop", lambda: None)

        mgr.start()
        mgr.start()

        assert started == ["stream-stream-1"]

    def test_close_quietly_swallows_close_error(self):
        class _BrokenContainer:
            def close(self):
                raise RuntimeError("close failed")

        _close_quietly(_BrokenContainer())

    def test_jpeg_encoder_returns_empty_for_missing_frame(self):
        assert _encode_frame_jpeg_bytes(None) == b""

    def test_stream_loop_returns_when_no_consumer_is_enabled(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        monkeypatch.setattr(stream_manager_module.settings, "WEBRTC_AUTO_PUBLISH", False)
        mgr._running = True

        mgr._stream_loop()

        assert mgr._running is True

    def test_open_relay_configures_h264_output(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        output = type("Output", (), {})()
        output.mux = lambda packets: None
        out_stream = type("OutStream", (), {"encode": lambda self, frame: []})()
        output.add_stream = lambda *args, **kwargs: out_stream
        monkeypatch.setattr(stream_manager_module.av, "open", lambda *args, **kwargs: output)

        result = mgr._open_relay(type("Stream", (), {"average_rate": 25})(), 640, 360)

        assert result == (output, out_stream.encode, output.mux)
        assert out_stream.width == 640
        assert out_stream.height == 360
        assert out_stream.gop_size == 50
        assert mgr.health.publishing is True

    def test_open_segment_writer_configures_sampling(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        output = type("Output", (), {})()
        output.mux = lambda packets: None
        out_stream = type("OutStream", (), {"encode": lambda self, frame: []})()
        output.add_stream = lambda *args, **kwargs: out_stream
        monkeypatch.setattr(stream_manager_module.av, "open", lambda *args, **kwargs: output)
        monkeypatch.setattr(stream_manager_module.settings, "FRAME_SAMPLE_FPS", 5.0)

        result = mgr._open_segment_writer(type("Stream", (), {"average_rate": 25})(), 640, 360, start_number=4)

        assert result.container is output
        assert result.avg_fps == 25.0
        assert result.sample_every == 5
        assert out_stream.width == 640

    def test_open_relay_uses_fallback_gop_without_fps(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        output = type("Output", (), {})()
        output.mux = lambda packets: None
        out_stream = type("OutStream", (), {"encode": lambda self, frame: []})()
        output.add_stream = lambda *args, **kwargs: out_stream
        monkeypatch.setattr(stream_manager_module.av, "open", lambda *args, **kwargs: output)

        mgr._open_relay(type("Stream", (), {"average_rate": None})(), 640, 360)

        assert out_stream.gop_size == stream_manager_module._RELAY_FALLBACK_GOP

    def test_open_segment_writer_returns_none_after_open_error(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        monkeypatch.setattr(stream_manager_module.av, "open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))

        result = mgr._open_segment_writer(type("Stream", (), {"average_rate": 25})(), 640, 360)

        assert result is None
    def test_input_options_are_rtsp_tuned(self):
        mgr = StreamManager("stream-1", "rtsp://camera/live")

        assert mgr._input_options() == {
            "rtsp_transport": "tcp",
            "fflags": "nobuffer",
            "flags": "low_delay",
        }

    def test_source_fps_returns_zero_for_missing_rate(self):
        class _FakeStream:
            average_rate = None

        assert StreamManager._source_fps(_FakeStream()) == 0.0

    def test_delete_segment_removes_file_and_registry_entries(self, monkeypatch, tmp_path):
        segment = tmp_path / "old_segment.mp4"
        segment.write_bytes(b"x")
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        mgr.frame_registry = type("FrameRegistry", (), {"remove_segment": lambda self, sid, p: 3})()
        removed = {"count": 0}

        def fake_unlink(self, missing_ok=False):
            removed["count"] += 1

        monkeypatch.setattr(Path, "unlink", fake_unlink)
        mgr._delete_segment(str(segment))

        assert removed["count"] == 1

    def test_reclaim_old_segments_keeps_reserved_segments(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        mgr._finalized_segments = ["a.mp4", "b.mp4", "c.mp4"]
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_MAX_ON_DISK", 2)
        monkeypatch.setattr(stream_manager_module, "get_deep_analyzer", lambda: type("DA", (), {"is_segment_active": lambda self, p: p == "b.mp4"})())
        deleted = []
        monkeypatch.setattr(mgr, "_delete_segment", lambda path: deleted.append(path))

        mgr._reclaim_old_segments("c.mp4")

        assert deleted == ["a.mp4", "c.mp4"]

    def test_notify_segment_finalized_and_reserved_state(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        called = []
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", True)
        monkeypatch.setattr(stream_manager_module, "get_deep_analyzer", lambda: type("DA", (), {"on_segment_finalized": lambda self, p: called.append(p)})())

        mgr._notify_segment_finalized("z.mp4")

        assert called == ["z.mp4"]

    def test_finalize_open_segment_runs_reclaim_then_notify(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        calls = []
        monkeypatch.setattr(mgr, "_reclaim_old_segments", lambda p: calls.append(("reclaim", p)))
        monkeypatch.setattr(mgr, "_notify_segment_finalized", lambda p: calls.append(("notify", p)))

        mgr._finalize_open_segment("segments/chunk_0001.mp4")

        assert calls == [
            ("reclaim", "segments/chunk_0001.mp4"),
            ("notify", "segments/chunk_0001.mp4"),
        ]

    def test_finalize_open_segment_noop_for_none(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        calls = []
        monkeypatch.setattr(mgr, "_reclaim_old_segments", lambda p: calls.append(("reclaim", p)))
        monkeypatch.setattr(mgr, "_notify_segment_finalized", lambda p: calls.append(("notify", p)))

        mgr._finalize_open_segment(None)

        assert calls == []

    def test_infer_worker_handles_yes_verdict_and_triggers_deep_analysis(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt", alert_event="fire")
        mgr._running = True
        mgr._playback_start_ts = 0.0
        mgr._latest_frame = __import__("numpy").zeros((2, 2, 3), dtype="uint8")
        mgr._latest_frame_ts = 1.0
        mgr._latest_frame_id = "frame-1"
        mgr.frame_registry = type("Registry", (), {"get_segment": lambda self, fid: "segments/seg_001.mp4"})()

        class _FakeEvent:
            def __init__(self, manager):
                self._manager = manager

            def wait(self, timeout=0.5):
                self._manager._running = False
                return True

            def clear(self):
                return None

        class _FakeEngine:
            def caption_with_metrics(self, frame, prompt=None, priority=False):
                return "Decision: Yes\nDescription: Visible fire.", {"ttft_ms": 10.0, "tpot_ms": 2.0, "throughput_tps": 12.0, "total_tokens_generated": 21.0}

        called = []

        class _FakeDA:
            def submit(self, **kwargs):
                called.append(kwargs["segment_path"])

        monkeypatch.setattr(stream_manager_module, "get_vlm_engine", lambda: _FakeEngine())
        monkeypatch.setattr(stream_manager_module, "parse_yes_no", lambda caption: True)
        monkeypatch.setattr(stream_manager_module, "get_deep_analyzer", lambda: _FakeDA())
        monkeypatch.setattr(stream_manager_module, "_encode_frame_jpeg_bytes", lambda frame: b"jpeg")
        mgr._frame_event = _FakeEvent(mgr)

        mgr._infer_worker()

        assert called == ["segments/seg_001.mp4"]

    def test_encode_frame_jpeg_bytes_returns_encoded_payload(self, monkeypatch):
        frame = np.zeros((4, 4, 3), dtype="uint8")

        class _Packet:
            def __init__(self, payload):
                self.payload = payload

            def __bytes__(self):
                return self.payload

        class _Codec:
            width = 0
            height = 0
            pix_fmt = ""

            def open(self):
                return None

            def encode(self, frame_obj):
                return [_Packet(b"img")] if frame_obj is not None else [_Packet(b"-end")]

        class _VideoFrameFactory:
            @staticmethod
            def from_ndarray(_array, format="rgb24"):
                assert format == "rgb24"

                class _Src:
                    width = 8
                    height = 4

                    def reformat(self, **kwargs):
                        return SimpleNamespace(width=kwargs["width"], height=kwargs["height"])

                return _Src()

        monkeypatch.setattr(stream_manager_module.av, "VideoFrame", _VideoFrameFactory)
        monkeypatch.setattr(
            stream_manager_module.av,
            "CodecContext",
            SimpleNamespace(create=lambda *args, **kwargs: _Codec()),
        )

        assert _encode_frame_jpeg_bytes(frame, max_width=6) == b"img-end"

    def test_encode_frame_jpeg_bytes_returns_empty_when_source_size_invalid(self, monkeypatch):
        frame = np.zeros((2, 2, 3), dtype="uint8")

        class _VideoFrameFactory:
            @staticmethod
            def from_ndarray(_array, format="rgb24"):
                assert format == "rgb24"
                return SimpleNamespace(width=0, height=4)

        monkeypatch.setattr(stream_manager_module.av, "VideoFrame", _VideoFrameFactory)

        assert _encode_frame_jpeg_bytes(frame) == b""

    def test_start_creates_segments_dir_and_infer_thread(self, monkeypatch):
        class _Registry:
            def register(self, _record):
                return None

        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt", frame_registry=_Registry())
        started = []
        mkdir_calls = []

        class _Thread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def start(self):
                started.append(self.kwargs["name"])

            def join(self, timeout):
                return None

        def fake_mkdir(self, parents=False, exist_ok=False):
            mkdir_calls.append((str(self), parents, exist_ok))

        monkeypatch.setattr(stream_manager_module.threading, "Thread", _Thread)
        monkeypatch.setattr(Path, "mkdir", fake_mkdir)
        monkeypatch.setattr(mgr, "_stream_loop", lambda: None)
        monkeypatch.setattr(mgr, "_infer_worker", lambda: None)

        mgr.start()

        assert started == ["stream-stream-1", "infer-stream-1"]
        assert mkdir_calls and mkdir_calls[0][1:] == (True, True)

    def test_stop_joins_threads_and_marks_not_publishing(self):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        joined = []

        class _Joinable:
            def __init__(self, name):
                self.name = name

            def join(self, timeout):
                joined.append((self.name, timeout))

        mgr._thread = _Joinable("stream")
        mgr._infer_thread = _Joinable("infer")
        mgr.health.publishing = True

        mgr.stop()

        assert mgr._running is False
        assert joined == [("stream", 5.0), ("infer", 5.0)]
        assert mgr.health.publishing is False

    def test_stream_loop_reconnects_after_input_error(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        mgr._running = True

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            mgr._running = False

        monkeypatch.setattr(stream_manager_module.settings, "WEBRTC_AUTO_PUBLISH", True)
        monkeypatch.setattr(stream_manager_module.settings, "RTSP_TIMEOUT", 1)
        monkeypatch.setattr(stream_manager_module.time, "sleep", fake_sleep)
        monkeypatch.setattr(
            stream_manager_module.av,
            "open",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        mgr._stream_loop()

        assert sleep_calls == [1.0]
        assert mgr.health.reconnect_count == 1
        assert mgr.health.publishing is False

    def test_stream_loop_handles_segment_mux_recovery(self, monkeypatch):
        class _Registry:
            def __init__(self):
                self.records = []

            def register(self, record):
                self.records.append(record)

        registry = _Registry()
        mgr = StreamManager("stream-1", "file:///video.mp4", vlm_prompt="prompt", frame_registry=registry)
        mgr._running = True

        class _Frame:
            width = 320
            height = 180
            format = SimpleNamespace(name="yuv420p")
            pts = 1

            def to_ndarray(self, format="rgb24"):
                assert format == "rgb24"
                return np.zeros((2, 2, 3), dtype="uint8")

        frame = _Frame()

        class _Packet:
            def __init__(self, manager):
                self.manager = manager
                self.dts = 1
                self.duration = 1

            def decode(self):
                self.manager._running = False
                return [frame]

        class _Input:
            def __init__(self, manager):
                self.streams = SimpleNamespace(
                    video=[
                        SimpleNamespace(
                            width=320,
                            height=180,
                            average_rate=25,
                            time_base=1.0,
                            thread_type=None,
                            thread_count=None,
                        )
                    ]
                )
                self.manager = manager

            def demux(self, _stream):
                return [_Packet(self.manager)]

            def close(self):
                return None

        relay_muxed = []

        def fake_open_relay(_in_stream, _w, _h):
            return (
                SimpleNamespace(close=lambda: None),
                lambda payload: [payload],
                lambda payloads: relay_muxed.extend(payloads),
            )

        first_mux_call = {"seen": False}

        class _Seg:
            def __init__(self, failing=False):
                self.container = SimpleNamespace(close=lambda: None)
                self.encode = lambda payload: [payload]

                def _mux(_payloads):
                    if failing and not first_mux_call["seen"]:
                        first_mux_call["seen"] = True
                        raise RuntimeError("segment mux fail")

                self.mux = _mux
                self.avg_fps = 25.0
                self.sample_every = 1

        open_calls = []

        def fake_open_segment_writer(_in_stream, _w, _h, start_number=0):
            open_calls.append(start_number)
            return _Seg(failing=len(open_calls) == 1)

        monotonic_values = iter([0.0, 0.0, 5.0, 5.0, 5.0, 5.0, 6.0, 6.0, 6.0])
        sleep_calls = []

        monkeypatch.setattr(stream_manager_module.settings, "WEBRTC_AUTO_PUBLISH", True)
        monkeypatch.setattr(stream_manager_module.settings, "ALERT_VLM_INTERVAL", 0.0)
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_TIME_SECONDS", 1.0)
        monkeypatch.setattr(stream_manager_module.settings, "RTSP_TIMEOUT", 1)
        monkeypatch.setattr(stream_manager_module.time, "sleep", lambda s: sleep_calls.append(s))
        monkeypatch.setattr(stream_manager_module.time, "monotonic", lambda: next(monotonic_values))
        monkeypatch.setattr(stream_manager_module, "_calculate_scaled_dimensions", lambda w, h: (w, h))
        monkeypatch.setattr(stream_manager_module.av, "open", lambda *args, **kwargs: _Input(mgr))
        monkeypatch.setattr(mgr, "_open_relay", fake_open_relay)
        monkeypatch.setattr(mgr, "_open_segment_writer", fake_open_segment_writer)
        monkeypatch.setattr(mgr, "_finalize_open_segment", lambda _path: None)

        mgr._stream_loop()

        assert open_calls == [0, 6]
        assert relay_muxed
        assert registry.records
        assert sleep_calls

    def test_infer_worker_returns_when_engine_unavailable(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt")
        mgr._running = True

        monkeypatch.setattr(
            stream_manager_module,
            "get_vlm_engine",
            lambda: (_ for _ in ()).throw(RuntimeError("missing")),
        )

        mgr._infer_worker()

    def test_infer_worker_ignores_when_event_times_out(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt")
        mgr._running = True

        class _FakeEvent:
            def wait(self, timeout=0.5):
                mgr._running = False
                return False

            def clear(self):
                return None

        class _FakeEngine:
            def caption_with_metrics(self, _frame, prompt=None, priority=False):
                raise AssertionError("caption should not be called")

        mgr._frame_event = _FakeEvent()
        monkeypatch.setattr(stream_manager_module, "get_vlm_engine", lambda: _FakeEngine())

        mgr._infer_worker()

    def test_infer_worker_skips_none_frame_and_duplicate_timestamp(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt")
        mgr._running = True
        mgr._latest_frame = None
        mgr._latest_frame_ts = 1.0

        class _FakeEvent:
            def __init__(self):
                self.calls = 0

            def wait(self, timeout=0.5):
                self.calls += 1
                if self.calls == 1:
                    return True
                mgr._latest_frame = np.zeros((2, 2, 3), dtype="uint8")
                mgr._running = False
                return True

            def clear(self):
                return None

        class _FakeEngine:
            def caption_with_metrics(self, _frame, prompt=None, priority=False):
                raise AssertionError("duplicate timestamp should be skipped")

        mgr._frame_event = _FakeEvent()
        monkeypatch.setattr(stream_manager_module, "get_vlm_engine", lambda: _FakeEngine())

        mgr._infer_worker()

    def test_infer_worker_handles_caption_errors_and_none_caption(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt")
        mgr._running = True
        mgr._latest_frame = np.zeros((2, 2, 3), dtype="uint8")
        mgr._latest_frame_ts = 1.0
        mgr._latest_frame_id = "f1"

        class _FakeEvent:
            def __init__(self):
                self.calls = 0

            def wait(self, timeout=0.5):
                self.calls += 1
                if self.calls == 1:
                    return True
                mgr._latest_frame_ts = 2.0
                mgr._latest_frame_id = "f2"
                return True

            def clear(self):
                return None

        class _FakeEngine:
            def __init__(self):
                self.calls = 0

            def caption_with_metrics(self, _frame, prompt=None, priority=False):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("infer fail")
                mgr._running = False
                return None, {}

        mgr._frame_event = _FakeEvent()
        monkeypatch.setattr(stream_manager_module, "get_vlm_engine", lambda: _FakeEngine())

        mgr._infer_worker()

    def test_infer_worker_handles_thumbnail_and_submit_errors(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt", deep_analyzer_prompt="dp")
        mgr._running = True
        mgr._playback_start_ts = 0.0
        mgr._latest_frame = np.zeros((2, 2, 3), dtype="uint8")
        mgr._latest_frame_ts = 1.0
        mgr._latest_frame_id = "frame-1"
        mgr.frame_registry = SimpleNamespace(get_segment=lambda _fid: "seg-1.mp4")

        class _FakeEvent:
            def wait(self, timeout=0.5):
                mgr._running = False
                return True

            def clear(self):
                return None

        class _FakeEngine:
            def caption_with_metrics(self, _frame, prompt=None, priority=False):
                return "Decision: Yes", {}

        class _FakeDA:
            def submit(self, **kwargs):
                raise RuntimeError("submit fail")

        mgr._frame_event = _FakeEvent()
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", True)
        monkeypatch.setattr(stream_manager_module, "get_vlm_engine", lambda: _FakeEngine())
        monkeypatch.setattr(stream_manager_module, "parse_yes_no", lambda _caption: True)
        monkeypatch.setattr(
            stream_manager_module,
            "_encode_frame_jpeg_bytes",
            lambda _frame: (_ for _ in ()).throw(RuntimeError("jpeg fail")),
        )
        monkeypatch.setattr(stream_manager_module, "get_deep_analyzer", lambda: _FakeDA())

        mgr._infer_worker()

    def test_infer_worker_warns_when_no_segment_found(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live", vlm_prompt="prompt")
        mgr._running = True
        mgr._latest_frame = np.zeros((2, 2, 3), dtype="uint8")
        mgr._latest_frame_ts = 1.0
        mgr._latest_frame_id = "frame-1"
        mgr.frame_registry = SimpleNamespace(get_segment=lambda _fid: None)

        class _FakeEvent:
            def wait(self, timeout=0.5):
                mgr._running = False
                return True

            def clear(self):
                return None

        class _FakeEngine:
            def caption_with_metrics(self, _frame, prompt=None, priority=False):
                return "Decision: Yes", {}

        mgr._frame_event = _FakeEvent()
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", True)
        monkeypatch.setattr(stream_manager_module, "get_vlm_engine", lambda: _FakeEngine())
        monkeypatch.setattr(stream_manager_module, "parse_yes_no", lambda _caption: True)

        mgr._infer_worker()

    def test_reclaim_old_segments_noop_when_limit_disabled(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        mgr._finalized_segments = ["a.mp4"]
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_MAX_ON_DISK", 0)

        mgr._reclaim_old_segments("b.mp4")

        assert mgr._finalized_segments == ["a.mp4"]

    def test_reclaim_old_segments_noop_when_no_excess(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        mgr._finalized_segments = ["a.mp4"]
        monkeypatch.setattr(stream_manager_module.settings, "SEGMENT_MAX_ON_DISK", 2)

        mgr._reclaim_old_segments("b.mp4")

        assert mgr._finalized_segments == ["a.mp4", "b.mp4"]

    def test_segment_reserved_returns_false_when_deep_disabled(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", False)

        assert mgr._segment_reserved("x.mp4") is False

    def test_segment_reserved_handles_analyzer_failure(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", True)
        monkeypatch.setattr(
            stream_manager_module,
            "get_deep_analyzer",
            lambda: (_ for _ in ()).throw(RuntimeError("da fail")),
        )

        assert mgr._segment_reserved("x.mp4") is False

    def test_notify_segment_finalized_noop_when_deep_disabled(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", False)

        mgr._notify_segment_finalized("x.mp4")

    def test_notify_segment_finalized_handles_analyzer_error(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")
        monkeypatch.setattr(stream_manager_module.settings, "DEEP_ANALYZER_ENABLED", True)

        class _DA:
            def on_segment_finalized(self, _path):
                raise RuntimeError("notify fail")

        monkeypatch.setattr(stream_manager_module, "get_deep_analyzer", lambda: _DA())

        mgr._notify_segment_finalized("x.mp4")

    def test_delete_segment_handles_unlink_oserror(self, monkeypatch):
        mgr = StreamManager("stream-1", "rtsp://camera/live")

        def fail_unlink(self, missing_ok=False):
            raise OSError(errno.EIO, "io")

        monkeypatch.setattr(Path, "unlink", fail_unlink)

        mgr._delete_segment("x.mp4")
