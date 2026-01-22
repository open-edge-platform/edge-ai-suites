# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
MQTT Subscriber Service for receiving pipeline metadata via MQTT broker.
Replaces the previous file-polling mechanism with real-time MQTT subscriptions.
"""

import asyncio
import json
import logging
import time
from typing import Callable, Optional
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt

from ..config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_PREFIX

logger = logging.getLogger("app.mqtt_subscriber")


class MQTTSubscriber:
    """
    MQTT Subscriber that connects to the broker and receives messages
    for pipeline metadata. Messages are forwarded to registered callbacks.
    """

    def __init__(
        self,
        broker_host: str = MQTT_BROKER_HOST,
        broker_port: int = MQTT_BROKER_PORT,
        topic_prefix: str = MQTT_TOPIC_PREFIX,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._callbacks: dict[str, list[Callable]] = {}  # topic -> list of callbacks
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_topic_for_run(self, run_id: str) -> str:
        """Generate MQTT topic for a specific run."""
        return f"{self.topic_prefix}/{run_id}"

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self._connected = True
            self._reconnect_delay = 1
            # Re-subscribe to all registered topics
            for topic in self._callbacks.keys():
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self._connected = False

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback when disconnected from MQTT broker."""
        logger.warning(f"Disconnected from MQTT broker (rc={rc})")
        self._connected = False

    def _on_message(self, client, userdata, msg):
        """Callback when a message is received."""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")
            
            # Put message in queue for async processing
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._message_queue.put((topic, payload, time.time())),
                    self._loop
                )
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    async def connect(self):
        """Connect to the MQTT broker."""
        if self._client is not None:
            return

        self._loop = asyncio.get_event_loop()
        self._client = mqtt.Client(
            client_id=f"video-caption-service-{int(time.time())}",
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            self._client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()
            
            # Wait for connection with timeout
            for _ in range(50):  # 5 seconds timeout
                if self._connected:
                    break
                await asyncio.sleep(0.1)
            
            if not self._connected:
                logger.warning("MQTT connection timeout, will retry in background")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False
            logger.info("Disconnected from MQTT broker")

    def subscribe_to_run(self, run_id: str, callback: Callable[[str, dict, float], None]):
        """
        Subscribe to metadata for a specific run.
        
        Args:
            run_id: The run identifier
            callback: Function to call with (run_id, data, received_at) when message arrives
        """
        topic = self._get_topic_for_run(run_id)
        
        if topic not in self._callbacks:
            self._callbacks[topic] = []
            if self._client and self._connected:
                self._client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
        
        self._callbacks[topic].append(callback)
        logger.info(f"Registered callback for run {run_id}")

    def unsubscribe_from_run(self, run_id: str):
        """Unsubscribe from metadata for a specific run."""
        topic = self._get_topic_for_run(run_id)
        
        if topic in self._callbacks:
            del self._callbacks[topic]
            if self._client and self._connected:
                self._client.unsubscribe(topic)
                logger.info(f"Unsubscribed from topic: {topic}")

    async def process_messages(self):
        """
        Process messages from the queue and dispatch to callbacks.
        This should be run as an asyncio task.
        """
        while True:
            try:
                topic, payload, received_at = await self._message_queue.get()
                
                # Parse the payload
                try:
                    raw_data = json.loads(payload)
                except json.JSONDecodeError:
                    raw_data = {"raw": payload}
                
                # Extract the metadata field if present (pipeline server wraps data in metadata)
                # Expected format: {"metadata": {...}, "blob": ""}
                # We want to send the contents of metadata to the frontend
                if isinstance(raw_data, dict) and "metadata" in raw_data:
                    data = raw_data["metadata"]
                else:
                    data = raw_data
                
                # Extract run_id from topic
                # Topic format: {prefix}/{run_id}
                parts = topic.split("/")
                run_id = parts[-1] if len(parts) > 1 else topic
                
                # Dispatch to callbacks
                callbacks = self._callbacks.get(topic, [])
                for callback in callbacks:
                    try:
                        callback(run_id, data, received_at)
                    except Exception as e:
                        logger.error(f"Error in callback for topic {topic}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(0.1)

    @property
    def is_connected(self) -> bool:
        """Check if connected to the broker."""
        return self._connected


# Global MQTT subscriber instance
_mqtt_subscriber: Optional[MQTTSubscriber] = None
_message_processor_task: Optional[asyncio.Task] = None


async def get_mqtt_subscriber() -> MQTTSubscriber:
    """Get or create the global MQTT subscriber instance."""
    global _mqtt_subscriber, _message_processor_task
    
    if _mqtt_subscriber is None:
        _mqtt_subscriber = MQTTSubscriber()
        await _mqtt_subscriber.connect()
        
        # Start the message processor
        _message_processor_task = asyncio.create_task(_mqtt_subscriber.process_messages())
    
    return _mqtt_subscriber


async def shutdown_mqtt_subscriber():
    """Shutdown the global MQTT subscriber."""
    global _mqtt_subscriber, _message_processor_task
    
    if _message_processor_task:
        _message_processor_task.cancel()
        try:
            await _message_processor_task
        except asyncio.CancelledError:
            pass
        _message_processor_task = None
    
    if _mqtt_subscriber:
        await _mqtt_subscriber.disconnect()
        _mqtt_subscriber = None
