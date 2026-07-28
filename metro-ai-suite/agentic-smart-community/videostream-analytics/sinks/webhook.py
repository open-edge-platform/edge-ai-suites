"""WebhookSink — POST events to MCP Server /events endpoint."""

from __future__ import annotations

from shared.config import WebhookConfig
from shared.webhook_client import WebhookClient
from sinks.base import EventSink


class WebhookSink(EventSink):
    def __init__(self, config: WebhookConfig):
        self._client = WebhookClient(config)

    @property
    def url(self) -> str:
        return self._client.url

    def emit(self, event: dict) -> bool:
        return self._client.send_event(event)

    def close(self) -> None:
        self._client.close()
