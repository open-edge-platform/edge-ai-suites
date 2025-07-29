# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from cProfile import label
import json
import paho.mqtt.client as mqtt
from service.rule_engine import process_event
from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_USER, MQTT_PASSWORD
import logging
import threading

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt-listener")

# Create and run an asyncio event loop in a separate thread
event_loop = asyncio.new_event_loop()


def start_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


threading.Thread(target=start_event_loop, args=(event_loop,), daemon=True).start()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("✅ Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"📡 Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"❌ Failed to connect to MQTT broker, code: {rc}")


def on_message(client, userdata, msg):
    logger.info(f"📥 Received message on topic: {msg.topic}")
    try:
        payload = json.loads(msg.payload)

        # Prefer 'after' values, fallback to 'before'
        event_data = payload.get("after") or payload.get("before") or {}

        label = event_data.get("label")
        camera_name = event_data.get("camera")
        start_time = event_data.get("start_time")
        end_time = event_data.get("end_time")

        # Proceed only if all required fields are present AND duration >= 3 seconds
        if (
            label
            and camera_name
            and start_time
            and end_time
            and (end_time - start_time) >= 10
        ):
            logger.info(f"🔍 Event label: {label} | 🎥 Camera: {camera_name} | ⏱ Start Time: {start_time} | ⏱ End Time: {end_time}")

            logger.info("🚀 Submitting event to process_event coroutine")
            future = asyncio.run_coroutine_threadsafe(
                process_event(
                    event_data, context={"source": "mqtt", "topic": msg.topic}
                ),
                event_loop,
            )
            # Optional: log completion/failure if needed
            future.add_done_callback(
                lambda fut: (
                    logger.info(f"✅ process_event completed: {fut.result()}")
                    if not fut.exception()
                    else logger.error(
                        f"❌ process_event failed: {fut.exception()}", exc_info=True
                    )
                )
            )
        else:
            logger.warning(
                "⚠️ Skipping event due to missing required fields or short duration (< 10s)."
            )

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to decode MQTT message: {e}")
    except Exception as e:
        logger.error(f"❌ Exception while processing MQTT message: {e}", exc_info=True)


async def start_mqtt():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        logger.info(f"${MQTT_BROKER}  ${MQTT_PORT}  ${MQTT_USER}  ${MQTT_PASSWORD}")
        logger.info(f"🚀 Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
        client.loop_start()
    except Exception as e:
        logger.error(f"❌ Error connecting to MQTT: {e}")
