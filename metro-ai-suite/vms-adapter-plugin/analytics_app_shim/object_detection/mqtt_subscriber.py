# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""MQTT subscriber for object detection inference metadata.

Subscribes to the MQTT broker and routes incoming DLStreamer inference
metadata to the appropriate VMS shim for analytics push.

Topic convention: ``/{vms_name}/{analytics_app_id}/{camera_id}``
Example:         ``/nx-main/dls_vision/abc123-device-uuid``

On each message:
1. Parse vms_name, analytics_app_id, camera_id from topic.
2. Look up the VMS shim by vms_name.
3. Translate DLS metadata to Nx object-push format.
4. Call ``vms_shim.push_analytics_objects(device_id, objects, timestamp_ms)``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

from .translator import translate_dls_metadata

if TYPE_CHECKING:
    from plugin.core.factory import VmsShimSet

logger = structlog.get_logger(__name__)


class MqttSubscriber:
    """Async MQTT subscriber that routes DLS inference metadata to VMS shims.

    Usage::

        subscriber = MqttSubscriber()
        task = asyncio.create_task(
            subscriber.run(mqtt_host, mqtt_port, vms_shim_sets)
        )
        # on shutdown:
        task.cancel()
    """

    async def run(
        self,
        mqtt_host: str,
        mqtt_port: int,
        vms_shim_sets: list[VmsShimSet],
        analytics_app_id: str = "dls_vision",
        label_type_map: dict[str, str] | None = None,
        timestamp_offset_ms: int = 0,
    ) -> None:
        """Subscribe to MQTT and dispatch messages until cancelled.

        Topic wildcard: ``+/{analytics_app_id}/+`` (matches ``/{vms_name}/{analytics_app_id}/{camera_id}``)
        Leading slash is optional — both ``/nx-main/dls_vision/device`` and ``nx-main/dls_vision/device`` are
        handled by stripping the leading slash before splitting.
        """
        try:
            import aiomqtt  # type: ignore[import]
        except ImportError:
            logger.error(
                "mqtt_subscriber_aiomqtt_missing",
                detail="Install aiomqtt: pip install aiomqtt",
            )
            return

        # Build a name → shim lookup for fast dispatch
        shim_map: dict[str, Any] = {ss.name: ss.vms_shim for ss in vms_shim_sets}
        _label_map: dict[str, str] = {k.lower(): v for k, v in (label_type_map or {}).items()}

        # Wildcard: single-level + matches any vms_name; trailing + matches any camera_id
        topic_filter = f"+/{analytics_app_id}/+"

        logger.info(
            "mqtt_subscriber_starting",
            host=mqtt_host,
            port=mqtt_port,
            topic_filter=topic_filter,
        )

        while True:
            try:
                async with aiomqtt.Client(mqtt_host, port=mqtt_port) as client:
                    await client.subscribe(topic_filter)
                    logger.info("mqtt_subscriber_subscribed", topic_filter=topic_filter)
                    async for message in client.messages:
                        await self._handle_message(
                            str(message.topic),
                            message.payload,
                            shim_map,
                            analytics_app_id,
                            _label_map,
                            timestamp_offset_ms,
                        )
            except asyncio.CancelledError:
                logger.info("mqtt_subscriber_stopped")
                return
            except Exception as exc:  # noqa: BLE001 — reconnect on any broker error
                logger.warning(
                    "mqtt_subscriber_disconnected",
                    error=str(exc),
                    retrying_in_seconds=5,
                )
                await asyncio.sleep(5)

    async def _handle_message(
        self,
        topic: str,
        payload: bytes,
        shim_map: dict[str, Any],
        analytics_app_id: str,
        label_type_map: dict[str, str] | None = None,
        timestamp_offset_ms: int = 0,
    ) -> None:
        """Parse topic, translate payload, and dispatch to VMS shim."""
        import json

        # Normalise: strip optional leading slash, split into parts
        parts = topic.lstrip("/").split("/")
        if len(parts) != 3:  # noqa: PLR2004
            logger.warning("mqtt_unexpected_topic_format", topic=topic)
            return

        vms_name, _, camera_id = parts

        # Exact match first (e.g. "nx-main"), then prefix match (e.g. "nx" → "nx-main")
        shim = shim_map.get(vms_name) or next(
            (v for k, v in shim_map.items() if k.startswith(vms_name)), None
        )
        if shim is None:
            logger.warning(
                "mqtt_unknown_vms",
                vms_name=vms_name,
                known=list(shim_map.keys()),
            )
            return

        try:
            metadata = json.loads(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("mqtt_payload_parse_failed", topic=topic, error=str(exc))
            return

        objects, timestamp_ms = translate_dls_metadata(metadata, label_type_map, timestamp_offset_ms)
        if not objects:
            logger.debug("mqtt_no_objects_in_frame", topic=topic)
            return

        # device_id = camera_id without vendor prefix (e.g. "nx:abc" → "abc")
        device_id = camera_id.split(":", 1)[-1] if ":" in camera_id else camera_id

        ok = await shim.push_analytics_objects(device_id, objects, timestamp_ms)
        if not ok:
            logger.warning(
                "mqtt_push_failed",
                vms_name=vms_name,
                device_id=device_id,
                objects_count=len(objects),
            )
        else:
            logger.debug(
                "mqtt_pushed_objects",
                vms_name=vms_name,
                device_id=device_id,
                objects_count=len(objects),
                timestamp_ms=timestamp_ms,
            )
