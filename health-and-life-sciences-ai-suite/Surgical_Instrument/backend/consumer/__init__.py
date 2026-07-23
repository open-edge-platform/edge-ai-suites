"""Pipeline control-plane consumer package.

`InferenceConsumer` is the backend-side adapter for pipeline start/stop,
health polling, and rolling latency snapshots used by SSE emission.
"""
from .inference_consumer import InferenceConsumer  # noqa: F401
