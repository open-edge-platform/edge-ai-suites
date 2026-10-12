# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Bounded, thread-safe metadata index mapping sampled frames to segment files.

Each :class:`StreamManager` writes rolling ``.mp4`` segments to disk and, at a
lower rate, registers metadata for the frames it samples for VLM/detector
consumption. The registry lets a downstream deep analyzer resolve a
``frame_id`` — surfaced by a fast detector — back to the segment file that
contains it, without persisting any frame image data.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Optional


@dataclass
class FrameRecord:
    frame_id: uuid.UUID
    stream_id: str
    rtsp_url: str
    segment_path: str
    pts_seconds: Optional[float] = None
    created_ts: float = field(default_factory=time.time)


class SegmentFrameRegistry:
    """Thread-safe registry with a fixed per-stream cap; evicts a stream's own oldest record on overflow."""

    def __init__(self, max_records_per_stream: int = 500):
        """Initialize the registry with a per-stream record limit."""
        self._records: Dict[uuid.UUID, FrameRecord] = {}
        # Per-stream insertion order, used to evict only within the offending stream.
        self._stream_order: Dict[str, "OrderedDict[uuid.UUID, None]"] = {}
        self._lock = threading.Lock()
        self._max_records_per_stream = max_records_per_stream

    def register(self, record: FrameRecord) -> None:
        """Add a new record, evicting the oldest for this stream if over capacity."""
        with self._lock:
            self._records[record.frame_id] = record
            order = self._stream_order.setdefault(record.stream_id, OrderedDict())
            order[record.frame_id] = None
            if len(order) > self._max_records_per_stream:
                oldest_id, _ = order.popitem(last=False)
                del self._records[oldest_id]

    def get_record(self, frame_id: uuid.UUID) -> Optional[FrameRecord]:
        """Return the record for a given frame_id, or None if not found."""
        with self._lock:
            return self._records.get(frame_id)

    def get_segment(self, frame_id: uuid.UUID) -> Optional[str]:
        """Return the segment .mp4 that contains this frame."""
        record = self.get_record(frame_id)
        return record.segment_path if record else None

    def remove_segment(self, stream_id: str, segment_path: str) -> int:
        """Purge every record for a reclaimed segment file. Returns the count removed."""
        with self._lock:
            order = self._stream_order.get(stream_id)
            if not order:
                return 0
            # Scan only this stream's own frame_ids (via _stream_order) instead of
            # every record across all streams — segment rotation is frequent, so
            # this keeps the cost proportional to one stream's frame count, not
            # the whole registry.
            stale = [
                frame_id
                for frame_id in order
                if self._records[frame_id].segment_path == segment_path
            ]
            for frame_id in stale:
                del self._records[frame_id]
                order.pop(frame_id, None)
            return len(stale)

    def latest(self, stream_id: Optional[str] = None, limit: int = 50) -> List[FrameRecord]:
        """Return the most recently registered records, optionally filtered by stream."""
        with self._lock:
            records = list(self._records.values())
        if stream_id is not None:
            records = [r for r in records if r.stream_id == stream_id]
        return records[-limit:]

    def stats(self) -> dict:
        """Return a summary of the registry's current state."""
        with self._lock:
            total = len(self._records)
            per_stream: Dict[str, int] = {}
            for record in self._records.values():
                per_stream[record.stream_id] = per_stream.get(record.stream_id, 0) + 1
        return {
            "total": total,
            "per_stream_capacity": self._max_records_per_stream,
            "per_stream": per_stream,
        }

