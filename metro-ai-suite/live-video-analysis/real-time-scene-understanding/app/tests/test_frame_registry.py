# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.frame_registry.SegmentFrameRegistry."""

from __future__ import annotations

import uuid

from backend.services.frame_registry import FrameRecord
from backend.services.frame_registry import SegmentFrameRegistry


def _make_record(stream_id: str = "stream-a", segment_path: str = "segments/a_0001.mp4") -> FrameRecord:
    return FrameRecord(
        frame_id=uuid.uuid4(),
        stream_id=stream_id,
        rtsp_url="rtsp://example/cam",
        segment_path=segment_path,
        pts_seconds=1.0,
    )


class TestRegisterAndLookup:
    def test_register_then_get_record_returns_same_record(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        record = _make_record()

        registry.register(record)

        assert registry.get_record(record.frame_id) is record

    def test_get_record_returns_none_for_unknown_frame_id(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        assert registry.get_record(uuid.uuid4()) is None

    def test_get_segment_returns_segment_path(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        record = _make_record(segment_path="segments/a_0002.mp4")
        registry.register(record)

        assert registry.get_segment(record.frame_id) == "segments/a_0002.mp4"

    def test_get_segment_returns_none_for_unknown_frame_id(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        assert registry.get_segment(uuid.uuid4()) is None


class TestEviction:
    def test_evicts_oldest_record_once_over_per_stream_cap(self):
        registry = SegmentFrameRegistry(max_records_per_stream=2)
        first = _make_record()
        second = _make_record()
        third = _make_record()

        registry.register(first)
        registry.register(second)
        registry.register(third)

        assert registry.get_record(first.frame_id) is None
        assert registry.get_record(second.frame_id) is second
        assert registry.get_record(third.frame_id) is third

    def test_eviction_is_scoped_per_stream(self):
        registry = SegmentFrameRegistry(max_records_per_stream=1)
        record_a1 = _make_record(stream_id="stream-a")
        record_a2 = _make_record(stream_id="stream-a")
        record_b1 = _make_record(stream_id="stream-b")

        registry.register(record_a1)
        registry.register(record_b1)
        registry.register(record_a2)

        # stream-a's own oldest was evicted, but stream-b is untouched.
        assert registry.get_record(record_a1.frame_id) is None
        assert registry.get_record(record_a2.frame_id) is record_a2
        assert registry.get_record(record_b1.frame_id) is record_b1


class TestRemoveSegment:
    def test_removes_only_matching_stream_and_segment(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        target = _make_record(stream_id="stream-a", segment_path="segments/a_0001.mp4")
        other_segment = _make_record(stream_id="stream-a", segment_path="segments/a_0002.mp4")
        other_stream = _make_record(stream_id="stream-b", segment_path="segments/a_0001.mp4")
        registry.register(target)
        registry.register(other_segment)
        registry.register(other_stream)

        removed = registry.remove_segment("stream-a", "segments/a_0001.mp4")

        assert removed == 1
        assert registry.get_record(target.frame_id) is None
        assert registry.get_record(other_segment.frame_id) is other_segment
        assert registry.get_record(other_stream.frame_id) is other_stream

    def test_returns_zero_for_unknown_stream(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        assert registry.remove_segment("unknown-stream", "segments/x.mp4") == 0


class TestLatestAndStats:
    def test_latest_filters_by_stream_and_respects_limit(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        for _ in range(3):
            registry.register(_make_record(stream_id="stream-a"))
        registry.register(_make_record(stream_id="stream-b"))

        latest_a = registry.latest(stream_id="stream-a", limit=2)

        assert len(latest_a) == 2
        assert all(r.stream_id == "stream-a" for r in latest_a)

    def test_latest_without_stream_id_returns_all_streams(self):
        registry = SegmentFrameRegistry(max_records_per_stream=10)
        registry.register(_make_record(stream_id="stream-a"))
        registry.register(_make_record(stream_id="stream-b"))

        assert len(registry.latest(limit=50)) == 2

    def test_stats_reports_totals_and_per_stream_breakdown(self):
        registry = SegmentFrameRegistry(max_records_per_stream=5)
        registry.register(_make_record(stream_id="stream-a"))
        registry.register(_make_record(stream_id="stream-a"))
        registry.register(_make_record(stream_id="stream-b"))

        stats = registry.stats()

        assert stats == {
            "total": 3,
            "per_stream_capacity": 5,
            "per_stream": {"stream-a": 2, "stream-b": 1},
        }
