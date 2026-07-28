from __future__ import annotations

import logging
import re
import statistics
import sys
import threading
import time
from collections import deque
from typing import TextIO

PIPELINE_LATENCY_RE = re.compile(r"(?<!element-)latency,.*time=\(guint64\)(\d+)")


def _nearest_rank(values: list[float], percentile: int) -> float:
    index = max(0, min(len(values) - 1, int((percentile / 100.0) * len(values) + 0.5) - 1))
    return values[index]


class RollingLatency:
    def __init__(self, max_samples: int = 200) -> None:
        self._samples: deque[float] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._updated_at = 0.0

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._updated_at = 0.0

    def consume_line(self, line: str) -> bool:
        match = PIPELINE_LATENCY_RE.search(line)
        if not match:
            return False
        latency_ms = int(match.group(1)) / 1e6
        with self._lock:
            self._samples.append(latency_ms)
            self._updated_at = time.time()
        return True

    def snapshot(self) -> dict[str, float | int | bool]:
        with self._lock:
            values = sorted(self._samples)
            updated_at = self._updated_at
        if not values:
            return {
                "available": False,
                "samples": 0,
            }
        return {
            "available": True,
            "samples": len(values),
            "mean_ms": round(statistics.mean(values), 3),
            "p50_ms": round(_nearest_rank(values, 50), 3),
            "p90_ms": round(_nearest_rank(values, 90), 3),
            "p95_ms": round(_nearest_rank(values, 95), 3),
            "p99_ms": round(_nearest_rank(values, 99), 3),
            "max_ms": round(values[-1], 3),
            "updated_at": round(updated_at, 3),
        }


def pump_stream(
    stream: TextIO,
    collector: RollingLatency,
    *,
    log: logging.Logger | None = None,
    passthrough: TextIO | None = None,
    summary_interval_s: float = 5.0,
) -> None:
    next_summary_at = time.monotonic() + summary_interval_s
    for line in stream:
        collector.consume_line(line)
        if passthrough is not None:
            passthrough.write(line)
            passthrough.flush()
        if log is not None and time.monotonic() >= next_summary_at:
            snapshot = collector.snapshot()
            if snapshot.get("available"):
                log.info(
                    "latency window: samples=%s mean=%.3f p95=%.3f p99=%.3f",
                    snapshot["samples"],
                    snapshot["mean_ms"],
                    snapshot["p95_ms"],
                    snapshot["p99_ms"],
                )
            next_summary_at = time.monotonic() + summary_interval_s


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
    collector = RollingLatency()
    pump_stream(sys.stdin, collector, log=logging.getLogger("latency-tracer"), passthrough=sys.stderr)


if __name__ == "__main__":
    main()