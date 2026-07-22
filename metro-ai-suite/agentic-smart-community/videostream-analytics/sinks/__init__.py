"""EventSink abstraction + implementations."""

from .base import EventSink
from .null import NullSink
from .stdout import StdoutSink
from .webhook import WebhookSink

__all__ = ["EventSink", "WebhookSink", "StdoutSink", "NullSink"]
