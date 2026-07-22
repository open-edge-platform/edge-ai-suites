"""StdoutSink — JSON per line to stdout (CLI / debugging)."""

from __future__ import annotations

import json
import sys

from .base import EventSink


class StdoutSink(EventSink):
    def emit(self, event: dict) -> bool:
        try:
            line = json.dumps(event, default=str, ensure_ascii=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
            return True
        except Exception:
            return False
