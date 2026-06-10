# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
# -*- encoding: utf-8 -*-
"""Synchronous client for an external TTS service.

Design:
- Main process only sends text when needed.
- Service process handles model readiness check, generation, and playback.
- No local TTS model loading.
- No background thread/event-loop in client.

Public APIs:
- submit_tts(text)
- health_check()
- self_test()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl as ssl_lib
import uuid
from typing import Any, Dict

import websockets


logger = logging.getLogger(__name__)


class TTSClient:
    """Simple synchronous WebSocket client for TTS service."""

    SUCCESS_STATUSES = {"ok", "success", "done", "completed", "accepted", "ready"}
    PENDING_STATUSES = {"queued", "running", "processing", "working"}
    ERROR_STATUSES = {"error", "failed", "failure"}

    def __init__(
        self,
        host: str = "localhost",
        port: int = 10096,
        use_ssl: int = 0,
        language: str = "EN",
        request_timeout: float = 120.0,
    ):
        self.host = host
        self.port = port
        self.use_ssl = bool(use_ssl)
        self.language = language
        self.request_timeout = request_timeout

    @property
    def uri(self) -> str:
        scheme = "wss" if self.use_ssl else "ws"
        return f"{scheme}://{self.host}:{self.port}"

    def _get_ssl_context(self):
        if not self.use_ssl:
            return None
        ssl_context = ssl_lib.create_default_context()
        # configure SSL context to require certificate verification and hostname checking
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl_lib.CERT_REQUIRED
        return ssl_context

    async def _send_request_async(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ssl_context = self._get_ssl_context()
        logger.info("[TTS client] connect to %s", self.uri)
        async with websockets.connect(
            self.uri,
            subprotocols=["json"],
            ping_interval=None,
            ssl=ssl_context,
        ) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            return await self._wait_terminal_message_async(websocket, payload["request_id"])

    async def _wait_terminal_message_async(self, websocket, request_id: str) -> Dict[str, Any]:
        while True:
            raw_message = await asyncio.wait_for(websocket.recv(), timeout=self.request_timeout)
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise RuntimeError("TTS service returned non-object JSON payload")

            msg_request_id = message.get("request_id")
            if msg_request_id not in (None, request_id):
                continue

            status = str(message.get("status", "")).lower().strip()
            if status in self.PENDING_STATUSES:
                continue
            # Terminal negative response (e.g. {"status": "busy", "accepted": false})
            if message.get("accepted") is False:
                return message
            if status in self.ERROR_STATUSES:
                raise RuntimeError(message.get("error") or message.get("message") or "TTS service error")
            if status in self.SUCCESS_STATUSES:
                return message

            # Compatibility fallback: some services may omit status but return accepted/error fields.
            if message.get("accepted") is True:
                return message
            if message.get("error"):
                raise RuntimeError(str(message["error"]))

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self._send_request_async(payload))

    @staticmethod
    def _normalize_response(response: Dict[str, Any]) -> Dict[str, Any]:
        status = str(response.get("status", "")).lower().strip()
        accepted = bool(response.get("accepted", status in TTSClient.SUCCESS_STATUSES))
        normalized = {
            "request_id": response.get("request_id"),
            "accepted": accepted,
            "status": response.get("status", "unknown"),
            "message": response.get("message") or response.get("detail") or "",
        }
        if response.get("error"):
            normalized["accepted"] = False
            normalized["status"] = "error"
            normalized["message"] = str(response["error"])
        return normalized

    def submit_tts(self, text: str) -> Dict[str, Any]:
        """Submit text once; service handles generate + play internally."""
        if not text or not text.strip():
            return {
                "request_id": None,
                "accepted": False,
                "status": "error",
                "message": "empty input text",
            }

        request_id = str(uuid.uuid4())
        payload = {
            "action": "submit_tts",
            "request_id": request_id,
            "text": text,
            "language": self.language,
        }

        try:
            response = self._send_request(payload)
            normalized = self._normalize_response(response)
            logger.info("[TTS client] submit_tts response: %s", normalized)
            return normalized
        except Exception as exc:
            logger.warning("[TTS client] submit_tts failed: %s", exc)
            return {
                "request_id": request_id,
                "accepted": False,
                "status": "error",
                "message": str(exc),
            }

    def health_check(self) -> Dict[str, Any]:
        """Check if service and model state are ready."""
        request_id = str(uuid.uuid4())
        payload = {
            "action": "health",
            "request_id": request_id,
        }
        try:
            response = self._send_request(payload)
            normalized = self._normalize_response(response)
            logger.info("[TTS client] health response: %s", normalized)
            return normalized
        except Exception as exc:
            logger.warning("[TTS client] health_check failed: %s", exc)
            return {
                "request_id": request_id,
                "accepted": False,
                "status": "error",
                "message": str(exc),
            }

    def self_test(self) -> Dict[str, Any]:
        """Trigger service-side end-to-end TTS self test."""
        request_id = str(uuid.uuid4())
        payload = {
            "action": "test",
            "request_id": request_id,
        }
        try:
            response = self._send_request(payload)
            normalized = self._normalize_response(response)
            logger.info("[TTS client] self-test response: %s", normalized)
            return normalized
        except Exception as exc:
            logger.warning("[TTS client] self_test failed: %s", exc)
            return {
                "request_id": request_id,
                "accepted": False,
                "status": "error",
                "message": str(exc),
            }


_default_tts_client = TTSClient(
    host=os.getenv("TTS_SERVER_HOST", "localhost"),
    port=int(os.getenv("TTS_SERVER_PORT", "10096")),
    use_ssl=int(os.getenv("TTS_SERVER_SSL", "0")),
    language=os.getenv("TTS_SERVER_LANGUAGE", "EN"),
    request_timeout=float(os.getenv("TTS_SERVER_TIMEOUT", "120")),
)


def submit_tts(text: str):
    return _default_tts_client.submit_tts(text)


def health_check():
    return _default_tts_client.health_check()


def self_test():
    return _default_tts_client.self_test()
