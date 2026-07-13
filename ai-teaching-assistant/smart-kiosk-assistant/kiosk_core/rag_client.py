import json
from collections.abc import Generator
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from kiosk_core import config


class RagClient:
    def __init__(self, rag_url: str, timeout_seconds: float | None = None):
        self.rag_url = rag_url
        self.timeout_seconds = timeout_seconds or config.DEFAULT_HTTP_TIMEOUT_SECONDS

    def get_performance_metrics(self) -> dict:
        """Fetch aggregate retrieval/LLM latency stats from rag-service.

        This mirrors the Ubuntu flow where UI KPIs read from /api/v1/performance.
        """
        parts = urlsplit(self.rag_url)
        perf_url = urlunsplit((parts.scheme, parts.netloc, "/api/v1/performance", "", ""))
        with httpx.Client(timeout=min(self.timeout_seconds, 8.0), trust_env=False) as client:
            response = client.get(perf_url)
            response.raise_for_status()
            payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def stream_answer(
        self,
        transcription: str,
        history: list[dict[str, str]] | None = None,
        include_sources: bool = False,
        include_performance_metrics: bool = True,
        include_llm_metrics: bool = True,
        on_event: Callable[[dict], None] | None = None,
    ) -> Generator[str, None, None]:
        payload: dict[str, object] = {
            "transcription": transcription,
            "include_sources": include_sources,
            "include_performance_metrics": include_performance_metrics,
            "include_llm_metrics": include_llm_metrics,
        }
        if history:
            # Keep only role/content fields and drop empties; rag-service
            # validates role ∈ {user, assistant}.
            cleaned = [
                {"role": str(t.get("role", "")), "content": str(t.get("content", ""))}
                for t in history
                if t.get("content")
            ]
            if cleaned:
                payload["history"] = cleaned
        with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
            with client.stream(
                "POST",
                self.rag_url,
                headers={"Accept": "text/event-stream"},
                json=payload,
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break

                    event = json.loads(payload)
                    if "error" in event:
                        raise RuntimeError(str(event["error"]))

                    token = str(event.get("token", ""))
                    if token:
                        yield token
                        continue

                    if on_event is not None:
                        on_event(event)