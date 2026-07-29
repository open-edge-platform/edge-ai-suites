"""Pipeline control-plane consumer package.

`InferenceConsumer` is the backend-side adapter for pipeline start/stop,
health polling, and rolling latency snapshots used by SSE emission.
`MetricsClient` is the thin proxy to the surgical-metrics-collector
sidecar that exposes host CPU/GPU/NPU/memory/power counters.
"""
from .inference_consumer import InferenceConsumer  # noqa: F401
from .metrics_client import MetricsClient  # noqa: F401
