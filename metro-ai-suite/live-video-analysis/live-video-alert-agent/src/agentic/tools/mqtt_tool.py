# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
publish_mqtt tool — publishes alert notifications to an MQTT broker.

Configuration (environment variables):
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_BASE_TOPIC

Published topic: {MQTT_BASE_TOPIC}/{stream_id}/{alert_name}
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from src.config import settings

logger = logging.getLogger(__name__)


async def publish_mqtt(
    stream_id: str,
    alert_name: str,
    answer: str,
    reason: str,
    topic_override: Optional[str] = None,
) -> dict:
    """Publish an alert event to an MQTT broker."""
    broker = settings.MQTT_BROKER
    if not broker:
        logger.warning("publish_mqtt: MQTT_BROKER not configured — skipping")
        return {"status": "skipped", "reason": "MQTT_BROKER not configured"}

    topic = topic_override or (
        f"{settings.MQTT_BASE_TOPIC}/"
        f"{stream_id.replace(' ', '_')}/"
        f"{alert_name.replace(' ', '_')}"
    )

    payload = json.dumps({
        "stream_id": stream_id,
        "alert_name": alert_name,
        "answer": answer,
        "reason": reason,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    })

    def _publish():
        client = mqtt.Client(
            client_id=f"live-video-alert-{int(time.time())}",
            protocol=mqtt.MQTTv5,
        )
        if settings.MQTT_USERNAME:
            client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        client.connect(broker, settings.MQTT_PORT, keepalive=10)
        result = client.publish(topic, payload, qos=1)
        result.wait_for_publish(timeout=5)
        client.disconnect()
        return result.rc  # 0 = MQTT_ERR_SUCCESS

    try:
        rc = await asyncio.to_thread(_publish)
        if rc == 0:
            logger.info(f"MQTT published | topic={topic} | alert={alert_name}")
            return {"status": "published", "topic": topic, "rc": rc}
        else:
            logger.error(f"MQTT publish failed | rc={rc}")
            return {"status": "error", "topic": topic, "rc": rc}
    except Exception as exc:
        logger.error(f"publish_mqtt error: {exc}")
        return {"status": "error", "reason": str(exc)}
