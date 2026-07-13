from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChunkRecord:
    text: str
    index: int
    metadata: dict | None = None
