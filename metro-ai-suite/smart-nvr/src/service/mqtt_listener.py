# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import logging
import time
import aiomqtt
from service.rule_engine import process_event
from datetime import datetime
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_USER, MQTT_PASSWORD,
    SCENESCAPE_THROTTLE_INTERVAL, BROKER_RECONNECT_DELAY,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt-listener")


async def process_scenescape_objects(objects, scenescape_camera, start_time, end_time, num_vehicles, num_pedestrians, msg_topic):
    """Process scenescape objects and trigger events for each object type."""
    for obj_type, obj_list in objects.items():
        if isinstance(obj_list, list) and obj_list:
            event_data = {
                "label": obj_type,
                "camera": scenescape_camera,
                "start_time": start_time,
                "end_time": end_time,
                "num_vehicles": num_vehicles,
                "num_pedestrians": num_pedestrians,
            }
            logger.info(f" Scenescape generated event: {event_data}")
            try:
                result = await process_event(event_data, context={"source": "scenescape", "topic": msg_topic})
                logger.info(f" process_event completed for {obj_type}: {result}")
            except Exception as e:
                logger.error(f" process_event failed for {obj_type}: {e}", exc_info=True)

# Convert ISO 8601 timestamp to float seconds since epoch
def iso_to_frigate_timestamp(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return f"{dt.timestamp():.6f}"
    except Exception as e:
        logger.warning(f"Failed to parse timestamp {iso_timestamp}: {e}")
        return iso_timestamp  

throttle_state = {"last_processed": 0}


async def handle_frigate_message(payload, topic):
    event_data = payload.get("after") or payload.get("before") or {}
    logger.info(f" Message received on topic: {topic} at {event_data.get('frame_time')}")
    label = event_data.get("label")
    camera_name = event_data.get("camera")
    start_time = event_data.get("start_time")
    end_time = event_data.get("end_time")

    if label and camera_name and start_time and end_time and (end_time - start_time) >= 10:
        logger.info(
            f" Event label: {label} |  Camera: {camera_name} |  Start: {start_time} |  End: {end_time}"
        )
        try:
            result = await process_event(event_data, context={"source": "frigate", "topic": topic})
            logger.info(f" process_event completed: {result}")
        except Exception as e:
            logger.error(f" process_event failed: {e}", exc_info=True)


async def handle_scenescape_message(payload, topic, state=None, broker_id=None):
    if state is None:
        state = throttle_state
    interval = state.get("interval", SCENESCAPE_THROTTLE_INTERVAL)
    now = time.time()
    if now - state["last_processed"] < interval:
        return
    state["last_processed"] = now

    objects = payload.get("objects", {})
    vehicle_list = []
    pedestrian_list = []
    if isinstance(objects, dict):
        vehicle_list = objects.get("vehicle", [])
        pedestrian_list = objects.get("pedestrian", [])
    num_vehicles = len(vehicle_list)
    num_pedestrians = len(pedestrian_list)
    if num_vehicles <= 0 and num_pedestrians <= 0:
        return

    iso_timestamp = payload.get("timestamp", "")
    logger.info(f" Scenescape raw timestamp: {iso_timestamp}")
    formatted_timestamp = iso_to_frigate_timestamp(iso_timestamp)
    raw_camera = payload.get("id")
    scenescape_camera = f"{broker_id}-{raw_camera}" if broker_id else raw_camera

    start_time = float(formatted_timestamp) - 15
    end_time = float(formatted_timestamp) - 5

    logger.info(f" Scenescape event: {topic} | Camera: {scenescape_camera} | Vehicles: {num_vehicles} | Pedestrians: {num_pedestrians} | Timestamp: {formatted_timestamp} | Clip: {start_time}-{end_time} | Throttle: {SCENESCAPE_THROTTLE_INTERVAL}s")
    await process_scenescape_objects(objects, scenescape_camera, start_time, end_time, num_vehicles, num_pedestrians, topic)


async def start_frigate_client():
    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_BROKER,
                port=MQTT_PORT,
                username=MQTT_USER or None,
                password=MQTT_PASSWORD or None,
            ) as client:
                await client.subscribe(MQTT_TOPIC)
                logger.info(f" Subscribed to Frigate topic: {MQTT_TOPIC} at {MQTT_BROKER}:{MQTT_PORT}")
                async for message in client.messages:
                    topic = str(message.topic)
                    try:
                        payload = json.loads(message.payload.decode("utf-8", errors="ignore"))
                        if topic.startswith("frigate/"):
                            await handle_frigate_message(payload, topic)
                        else:
                            logger.warning(f" Unknown topic: {topic}")
                    except json.JSONDecodeError as e:
                        logger.error(f" Failed to decode MQTT message: {e}")
                    except Exception as e:
                        logger.error(f" Exception processing MQTT message: {e}", exc_info=True)
        except aiomqtt.MqttError as e:
            logger.error(f" Frigate MQTT connection error: {e}; reconnecting in {BROKER_RECONNECT_DELAY}s")
            await asyncio.sleep(BROKER_RECONNECT_DELAY)

