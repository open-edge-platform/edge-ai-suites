"""Thread-safe performance metric stores."""
import threading


class LatencyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: float | None = None

    def record(self, latency_ms: float) -> None:
        with self._lock:
            self._last = round(latency_ms, 1)

    def stats(self) -> dict:
        with self._lock:
            return {"last_ms": self._last}


class LLMPerformanceStore(LatencyStore):
    def __init__(self) -> None:
        super().__init__()
        self._ttft_ms: float | None = None
        self._tokens_per_sec: float | None = None
        self._total_tokens: int | None = None

    def record_metrics(
        self,
        ttft_ms: float | None,
        tokens_per_sec: float | None,
        total_tokens: int | None,
    ) -> None:
        with self._lock:
            self._ttft_ms = round(ttft_ms, 1) if ttft_ms is not None and ttft_ms >= 0 else None
            self._tokens_per_sec = (
                round(tokens_per_sec, 2)
                if tokens_per_sec is not None and tokens_per_sec >= 0
                else None
            )
            self._total_tokens = int(total_tokens) if total_tokens is not None and total_tokens >= 0 else None

    def stats(self) -> dict:
        with self._lock:
            return {
                "last_ms": self._last,
                "ttft_ms": self._ttft_ms,
                "tokens_per_sec": self._tokens_per_sec,
                "total_tokens": self._total_tokens,
            }


llm_latency = LLMPerformanceStore()
retrieval_latency = LatencyStore()
