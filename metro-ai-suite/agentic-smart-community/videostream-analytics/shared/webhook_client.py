"""Webhook client for posting events to the MCP Server."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import WebhookConfig

logger = logging.getLogger(__name__)


class WebhookClient:
    def __init__(self, config: WebhookConfig):
        self.url = config.url
        self.timeout = config.timeout
        self.retry_attempts = config.retry_attempts
        self.retry_delay = config.retry_delay
        self._client = httpx.Client(timeout=self.timeout)

    def close(self):
        self._client.close()

    def send_event(self, payload: dict[str, Any]) -> bool:
        for attempt in range(self.retry_attempts):
            try:
                resp = self._client.post(self.url, json=payload)
                if resp.status_code < 400:
                    return True
                logger.warning(
                    "Webhook returned %d: %s", resp.status_code, resp.text[:200]
                )
            except httpx.HTTPError as e:
                logger.warning(
                    "Webhook attempt %d/%d failed: %s",
                    attempt + 1,
                    self.retry_attempts,
                    e,
                )
            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay)
        return False
