"""NullSink — discards all events (testing / benchmarking)."""

from __future__ import annotations

from .base import EventSink


class NullSink(EventSink):
    def emit(self, event: dict) -> bool:
        return True
