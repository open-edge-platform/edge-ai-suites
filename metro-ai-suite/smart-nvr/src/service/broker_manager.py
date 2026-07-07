# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import logging
import os
import ssl

import aiomqtt
import yaml

from config import (
    BROKERS_CONFIG_PATH,
    MAX_CONCURRENT_EVENTS,
    BROKER_RECONNECT_DELAY,
    NVR_SCENESCAPE_ENABLED,
    SCENESCAPE_MQTT_BROKER,
    SCENESCAPE_MQTT_PORT,
    SCENESCAPE_MQTT_TOPIC,
)
from model.broker import Broker
from service import redis_store
from service.mqtt_listener import handle_frigate_message, handle_scenescape_message

logger = logging.getLogger("broker-manager")

_tasks: dict[str, asyncio.Task] = {}
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVENTS)


def _tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _dispatch(broker: Broker, payload, topic, state):
    async with _semaphore:
        if broker.type == "frigate":
            await handle_frigate_message(payload, topic)
        else:
            await handle_scenescape_message(payload, topic, state, broker_id=broker.id)


async def _run_broker(broker: Broker):
    state = {"last_processed": 0, "interval": broker.throttle_interval}
    while True:
        try:
            async with aiomqtt.Client(
                hostname=broker.host,
                port=broker.port,
                tls_context=_tls_context() if broker.use_tls else None,
            ) as client:
                await client.subscribe(broker.topic, qos=1)
                logger.info(f"[{broker.id}] subscribed to {broker.topic} at {broker.host}:{broker.port}")
                async for message in client.messages:
                    topic = str(message.topic)
                    try:
                        payload = json.loads(message.payload.decode("utf-8", errors="ignore"))
                        asyncio.create_task(_dispatch(broker, payload, topic, state))
                    except json.JSONDecodeError as e:
                        logger.error(f"[{broker.id}] failed to decode message: {e}")
                    except Exception as e:
                        logger.error(f"[{broker.id}] error processing message: {e}", exc_info=True)
        except aiomqtt.MqttError as e:
            logger.error(f"[{broker.id}] connection error: {e}; reconnecting in {BROKER_RECONNECT_DELAY}s")
            await asyncio.sleep(BROKER_RECONNECT_DELAY)


def _as_broker(broker) -> Broker:
    return broker if isinstance(broker, Broker) else Broker(**broker)


async def start_broker(broker):
    broker = _as_broker(broker)
    await stop_broker(broker.id)
    if not broker.enabled:
        logger.info(f"[{broker.id}] disabled, not starting")
        return
    _tasks[broker.id] = asyncio.create_task(_run_broker(broker))


async def stop_broker(broker_id: str):
    task = _tasks.pop(broker_id, None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def restart_broker(broker):
    broker = _as_broker(broker)
    await start_broker(broker)


async def start_all_from_redis(request=None):
    for data in await redis_store.get_brokers(request):
        await start_broker(data)


async def stop_all():
    for broker_id in list(_tasks.keys()):
        await stop_broker(broker_id)


async def _has_scenescape(request=None) -> bool:
    return any(b.get("type") == "scenescape" for b in await redis_store.get_brokers(request))


async def load_yaml_brokers(path: str = BROKERS_CONFIG_PATH, request=None):
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        yaml_entries = data.get("brokers") or []
        yaml_ids = {e["id"] for e in yaml_entries}
        if yaml_ids:
            for b in await redis_store.get_brokers(request):
                if b["id"] not in yaml_ids:
                    await stop_broker(b["id"])
                    await redis_store.delete_broker(b["id"], request)
        for entry in yaml_entries:
            broker = Broker(**entry)
            await redis_store.save_broker(broker.id, broker.model_dump(), request)

    if NVR_SCENESCAPE_ENABLED and not await _has_scenescape(request):
        legacy = Broker(
            id="si1",
            name="Smart Intersection 1",
            host=SCENESCAPE_MQTT_BROKER,
            port=SCENESCAPE_MQTT_PORT,
            topic=SCENESCAPE_MQTT_TOPIC,
            type="scenescape",
            use_tls=True,
        )
        await redis_store.save_broker(legacy.id, legacy.model_dump(), request)
        logger.info("Seeded default si1 broker from environment")


_YAML_HEADER = (
    "# Scenescape-mode MQTT brokers. Active when NVR_SCENESCAPE=true.\n"
    "# host = MQTT broker IP only. RTSP is configured separately in the Frigate config.\n"
    "# Broker id must match the SI node prefix in Frigate camera names (e.g. si1 -> si1-camera1).\n"
)


async def sync_yaml_from_redis(request=None, path: str = BROKERS_CONFIG_PATH):
    """Persist current Redis brokers to YAML. Best-effort — errors are logged, not raised."""
    try:
        brokers = await redis_store.get_brokers(request)
        with open(path, "w") as f:
            f.write(_YAML_HEADER)
            yaml.safe_dump({"brokers": brokers}, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Synced {len(brokers)} broker(s) to {path}")
    except OSError as e:
        logger.warning(f"Could not write brokers YAML at {path}: {e}")

