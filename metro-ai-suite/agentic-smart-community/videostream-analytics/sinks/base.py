"""EventSink abstraction — pipeline output decoupling."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EventSink(ABC):
    """Stream monitor event output. Pipeline doesn't care who consumes events."""

    @abstractmethod
    def emit(self, event: dict) -> bool:
        """Emit an event. Returns True if successfully delivered."""
        ...

    def close(self) -> None:
        """Release resources. Called on shutdown."""
