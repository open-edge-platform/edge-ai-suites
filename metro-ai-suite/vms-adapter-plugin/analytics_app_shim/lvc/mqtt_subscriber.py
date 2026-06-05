# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""LVC-specific aiomqtt subscriber.

Subscribes to ``live-video-captioning/#`` on the MQTT broker and routes
incoming caption results to per-run ``asyncio.Queue`` instances consumed
by the SSE result-stream route.

Same pattern as :mod:`analytics_app_shim.object_detection.mqtt_subscriber` —
each Analytics App owns its own MQTT subscriber; there is no shared global client.

Topic convention: ``live-video-captioning/{run_id}``
Payload (LVC format): ``{"metadata": {"result": "...", "timestamp_seconds": 41.94}, "blob": ""}``
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Callable, Optional

import structlog

logger = structlog.get_logger(__name__)

_TOPIC = "live-video-captioning/#"
_QUEUE_MAX = 500


class LvcMqttSubscriber:
    """aiomqtt subscriber that routes LVC caption results to per-run async queues.

    Usage (orchestrator)::

        subscriber = LvcMqttSubscriber()
        task = asyncio.create_task(subscriber.run(mqtt_host, mqtt_port))
        shim.set_subscriber(subscriber)
        # on shutdown:
        task.cancel()
    """

    def __init__(self) -> None:
        # run_id → asyncio.Queue
        self._run_queues: dict[str, asyncio.Queue] = {}
        # Broadcast queue — receives ALL run messages
        self._broadcast: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        # Optional Nx write-back: async (run_id, caption) → None
        self._nx_write_back: Callable[[str, str], object] | None = None

    def set_nx_write_back(self, callback: Callable[[str, str], object]) -> None:
        """Register an async callback invoked for every caption to push to Nx Witness."""
        self._nx_write_back = callback

    # ── Queue management (called by SSE route via shim) ───────────────────────

    def subscribe_run(self, run_id: str) -> asyncio.Queue:
        """Return a per-run queue (creates one if not existing)."""
        if run_id not in self._run_queues:
            self._run_queues[run_id] = asyncio.Queue(maxsize=_QUEUE_MAX)
        return self._run_queues[run_id]

    def release_run(self, run_id: str) -> None:
        """Remove the per-run queue when the SSE client disconnects."""
        self._run_queues.pop(run_id, None)

    def broadcast_queue(self) -> asyncio.Queue:
        """Return the broadcast queue that receives all run messages."""
        return self._broadcast

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(self, mqtt_host: str, mqtt_port: int = 1883) -> None:
        """Subscribe to LVC MQTT and dispatch messages until cancelled.

        Reconnects automatically on broker disconnection (5 s backoff).
        """
        try:
            import aiomqtt
        except ImportError:
            logger.error(
                "lvc_mqtt_aiomqtt_missing",
                detail="Install aiomqtt: pip install aiomqtt",
            )
            return

        logger.info("lvc_mqtt_subscriber_starting", host=mqtt_host, port=mqtt_port, topic=_TOPIC)

        while True:
            try:
                async with aiomqtt.Client(mqtt_host, port=mqtt_port) as client:
                    await client.subscribe(_TOPIC)
                    logger.info("lvc_mqtt_subscriber_subscribed", topic=_TOPIC)
                    async for message in client.messages:
                        await self._handle_message(
                            str(message.topic),
                            message.payload,  # type: ignore[arg-type]
                        )
            except asyncio.CancelledError:
                logger.info("lvc_mqtt_subscriber_stopped")
                return
            except Exception as exc:  # noqa: BLE001 — reconnect on any broker error
                logger.warning(
                    "lvc_mqtt_subscriber_disconnected",
                    error=str(exc),
                    retrying_in_seconds=5,
                )
                await asyncio.sleep(5)

    # ── Message dispatch ──────────────────────────────────────────────────────

    async def _handle_message(self, topic: str, payload: bytes | str) -> None:
        """Parse LVC payload and dispatch to per-run + broadcast queues."""
        # Topic: "live-video-captioning/{run_id}"
        parts = topic.rsplit("/", 1)
        if len(parts) != 2:  # noqa: PLR2004
            logger.warning("lvc_mqtt_unexpected_topic", topic=topic)
            return

        run_id = parts[1]

        try:
            raw = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            logger.warning("lvc_mqtt_payload_parse_failed", topic=topic)
            return

        # Unwrap LVC envelope: {"metadata": {...}, "blob": ""}
        data = raw.get("metadata", raw) if isinstance(raw, dict) else raw

        if not isinstance(data, dict) or "result" not in data:
            logger.debug("lvc_mqtt_no_result_skipped", topic=topic)
            return

        envelope = {
            "runId": run_id,
            "data": data,
            "received_at": time.time(),
        }

        self._put_nowait(self._run_queues.get(run_id), envelope)
        self._put_nowait(self._broadcast, envelope)

        logger.debug("lvc_mqtt_dispatched", run_id=run_id, result_len=len(data.get("result", "")))

        # Push caption to Nx Witness as a bookmark (fire-and-forget).
        if self._nx_write_back is not None:
            caption = data.get("result", "")
            if caption:
                asyncio.ensure_future(self._nx_write_back(run_id, caption))

    @staticmethod
    def _put_nowait(queue: Optional[asyncio.Queue], item: object) -> None:
        """Put item in queue, dropping oldest if full."""
        if queue is None:
            return
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(item)
            except asyncio.QueueEmpty:
                pass
