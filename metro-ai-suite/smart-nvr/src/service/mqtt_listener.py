# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import logging
import threading
import ssl
import time
import paho.mqtt.client as mqtt
from service.rule_engine import process_event
from datetime import datetime
from datetime import timedelta
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_USER, MQTT_PASSWORD,
    SCENESCAPE_MQTT_BROKER, SCENESCAPE_MQTT_PORT, SCENESCAPE_MQTT_TOPIC,
    SCENESCAPE_MQTT_USER, SCENESCAPE_MQTT_PASSWORD,
    SCENESCAPE_CA_CERT_PATH, SCENESCAPE_CLIENT_CERT_PATH, SCENESCAPE_CLIENT_KEY_PATH, NVR_SCENESCAPE_ENABLED,  
    SCENESCAPE_THROTTLE_INTERVAL
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt-listener")

event_loop = asyncio.new_event_loop()

def start_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=start_event_loop, args=(event_loop,), daemon=True).start()

def process_scenescape_objects(objects, scenescape_camera, start_time, end_time, num_vehicles, num_pedestrians, msg_topic):
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

            future = asyncio.run_coroutine_threadsafe(
                process_event(event_data, context={"source": "scenescape", "topic": msg_topic}),
                event_loop,
            )
            future.add_done_callback(
                lambda fut: (
                    logger.info(f" process_event completed for {obj_type}: {fut.result()}")
                    if not fut.exception()
                    else logger.error(
                        f" process_event failed for {obj_type}: {fut.exception()}",
                        exc_info=True,
                    )
                )
            )

# Convert ISO 8601 timestamp to float seconds since epoch
def iso_to_frigate_timestamp(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return f"{dt.timestamp():.6f}"
    except Exception as e:
        logger.warning(f"Failed to parse timestamp {iso_timestamp}: {e}")
        return iso_timestamp  

# Store last processed time for scenescape throttling
throttle_state = {"last_processed": 0}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        if userdata == "frigate":
            client.subscribe(MQTT_TOPIC)
            logger.info(f" Subscribed to Frigate topic: {MQTT_TOPIC}")
        elif userdata == "scenescape":
            client.subscribe(SCENESCAPE_MQTT_TOPIC, qos=1)  # QoS 1 subscription
            logger.info(f" Subscribed to Scenescape topic: {SCENESCAPE_MQTT_TOPIC}")
    else:
        logger.error(f" Failed to connect to MQTT broker ({userdata}), code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))

        if msg.topic.startswith("frigate/"):
            event_data = payload.get("after") or payload.get("before") or {}
            logger.info(f" Message received on topic: {msg.topic} at {event_data.get('frame_time')}")
            label = event_data.get("label")
            camera_name = event_data.get("camera")
            start_time = event_data.get("start_time")
            end_time = event_data.get("end_time")

            if label and camera_name and start_time and end_time and (end_time - start_time) >= 10:
                logger.info(
                    f" Event label: {label} |  Camera: {camera_name} |  Start: {start_time} |  End: {end_time}"
                )
                future = asyncio.run_coroutine_threadsafe(
                    process_event(event_data, context={"source": "frigate", "topic": msg.topic}),
                    event_loop,
                )
                future.add_done_callback(
                    lambda fut: (
                        logger.info(f" process_event completed: {fut.result()}")
                        if not fut.exception()
                        else logger.error(f" process_event failed: {fut.exception()}", exc_info=True)
                    )
                )
            else:
                return
                #logger.warning(
                    #" Skipping Frigate summary due to missing fields or short duration (<10s)."
                #)

        elif msg.topic.startswith("scenescape/"):
            now = time.time()
            if now - throttle_state["last_processed"] < SCENESCAPE_THROTTLE_INTERVAL:
                return
            throttle_state["last_processed"] = now

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
            scenescape_camera = payload.get("id")
            
            start_time = float(formatted_timestamp) - 15
            end_time = float(formatted_timestamp) - 5

            logger.info(f" Scenescape event: {msg.topic} | Camera: {scenescape_camera} | Vehicles: {num_vehicles} | Pedestrians: {num_pedestrians} | Timestamp: {formatted_timestamp} | Clip: {start_time}-{end_time} | Throttle: {SCENESCAPE_THROTTLE_INTERVAL}s")
            process_scenescape_objects(objects, scenescape_camera, start_time, end_time, num_vehicles, num_pedestrians, msg.topic)

        else:
            logger.warning(f" Unknown topic: {msg.topic}")

    except json.JSONDecodeError as e:
        logger.error(f" Failed to decode MQTT message: {e}")
    except Exception as e:
        logger.error(f" Exception processing MQTT message: {e}", exc_info=True)

def start_mqtt(broker, port, user, password, userdata,
               ca_cert=None, client_cert=None, client_key=None):
    client = mqtt.Client(userdata=userdata)
    if user and password:
        client.username_pw_set(user, password)
    if ca_cert:
        client.tls_set(
            ca_certs=ca_cert,
            certfile=client_cert,
            keyfile=client_key,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        client.tls_insecure_set(True) 
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port)
    client.loop_start()
    logger.info(f" Connecting to MQTT broker {userdata} at {broker}:{port}")

async def start_mqtt_clients():
    await asyncio.to_thread(
        start_mqtt,
        MQTT_BROKER,
        MQTT_PORT,
        MQTT_USER,
        MQTT_PASSWORD,
        "frigate"
    )
    logger.info(f" Scenescape is enabled {NVR_SCENESCAPE_ENABLED}, starting Scenescape MQTT client")
    if NVR_SCENESCAPE_ENABLED:
        await asyncio.to_thread(
            start_mqtt,
            SCENESCAPE_MQTT_BROKER,
            SCENESCAPE_MQTT_PORT,
            SCENESCAPE_MQTT_USER,
            SCENESCAPE_MQTT_PASSWORD,
            "scenescape",
            ca_cert=SCENESCAPE_CA_CERT_PATH,
            client_cert=SCENESCAPE_CLIENT_CERT_PATH,
            client_key=SCENESCAPE_CLIENT_KEY_PATH,
        )

