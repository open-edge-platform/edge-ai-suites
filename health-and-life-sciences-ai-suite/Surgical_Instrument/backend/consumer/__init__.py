"""MQTT + JPEG + latency-log consumer package.

Replaces the inline OpenCV+Ultralytics worker in
`backend/pipeline/inference.py`. See `InferenceConsumer` for the public API
that `backend.server.app` binds against.
"""
from .inference_consumer import InferenceConsumer  # noqa: F401
