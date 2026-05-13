# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
trigger_webhook tool — HTTP POST to a configured external endpoint.

Configuration (environment variables):
    WEBHOOK_URL     — default endpoint (overridable per call)
    WEBHOOK_SECRET  — if set, adds an HMAC-SHA256 signature header
                      ``X-Alert-Signature: sha256=<hex>``

Requires: aiohttp
"""

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

import aiohttp

from src.config import settings

logger = logging.getLogger(__name__)


async def trigger_webhook(
    payload: Dict[str, Any],
    url: Optional[str] = None,
) -> dict:
    """POST a JSON payload to a webhook URL, optionally HMAC-signed."""
    endpoint = url or settings.WEBHOOK_URL
    if not endpoint:
        logger.warning("trigger_webhook: WEBHOOK_URL not configured — skipping")
        return {"status": "skipped", "reason": "WEBHOOK_URL not configured"}

    try:
        body = json.dumps(payload, default=str).encode()
        headers = {"Content-Type": "application/json"}

        if settings.WEBHOOK_SECRET:
            sig = hmac.new(
                settings.WEBHOOK_SECRET.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Alert-Signature"] = f"sha256={sig}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                status = resp.status
                text = await resp.text()

        log_fn = logger.info if status < 400 else logger.error
        log_fn(f"Webhook POST {endpoint} → HTTP {status}")
        return {"status": "ok" if status < 400 else "error", "http_status": status, "response": text[:200]}

    except Exception as exc:
        logger.error(f"trigger_webhook failed: {exc}")
        return {"status": "error", "reason": str(exc)}
