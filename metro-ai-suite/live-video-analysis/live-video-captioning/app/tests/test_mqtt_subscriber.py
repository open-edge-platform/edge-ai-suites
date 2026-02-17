# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.mqtt_subscriber, MQTT subscriber service."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from backend.services.mqtt_subscriber import MQTTSubscriber


# ===================================================================
# MQTTSubscriber unit tests (no real broker)
# ===================================================================
class TestMQTTSubscriberInit:
    """Construction and default attribute tests."""

    def test_default_attributes(self):
        """MQTTSubscriber uses config defaults for host, port, and prefix."""
        sub = MQTTSubscriber(
            broker_host="localhost", broker_port=1883, topic_prefix="test"
        )
        assert sub.broker_host == "localhost"
        assert sub.broker_port == 1883
        assert sub.topic_prefix == "test"
        assert sub.is_connected is False

    def test_topic_generation(self):
        """_get_topic_for_run builds '<prefix>/<run_id>'."""
        sub = MQTTSubscriber(topic_prefix="pfx")
        assert sub._get_topic_for_run("run123") == "pfx/run123"


class TestMQTTSubscriberCallbacks:
    """subscribe_to_run / unsubscribe_from_run without a live broker."""

    def test_subscribe_registers_callback(self):
        """subscribe_to_run stores the callback under the topic key."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb = MagicMock()
        sub.subscribe_to_run("r1", cb)
        assert "t/r1" in sub._callbacks
        assert cb in sub._callbacks["t/r1"]

    def test_unsubscribe_removes_callbacks(self):
        """unsubscribe_from_run removes all callbacks for the topic."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub.subscribe_to_run("r1", MagicMock())
        sub.unsubscribe_from_run("r1")
        assert "t/r1" not in sub._callbacks

    def test_unsubscribe_nonexistent_is_noop(self):
        """Unsubscribing from a topic with no callbacks does not raise."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub.unsubscribe_from_run("nonexistent")  # should not raise

    def test_multiple_callbacks_per_topic(self):
        """Multiple callbacks can be registered for the same run."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb1, cb2 = MagicMock(), MagicMock()
        sub.subscribe_to_run("r1", cb1)
        sub.subscribe_to_run("r1", cb2)
        assert len(sub._callbacks["t/r1"]) == 2


class TestMQTTSubscriberOnConnect:
    """_on_connect callback behaviour."""

    def test_successful_connection(self):
        """_on_connect sets _connected=True when rc==0."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._on_connect(MagicMock(), None, None, 0)
        assert sub._connected is True

    def test_failed_connection(self):
        """_on_connect sets _connected=False when rc!=0."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._on_connect(MagicMock(), None, None, 1)
        assert sub._connected is False

    def test_resubscribes_on_reconnect(self):
        """_on_connect re-subscribes to all registered topics."""
        sub = MQTTSubscriber(topic_prefix="t")
        mock_client = MagicMock()
        sub._callbacks["t/r1"] = [MagicMock()]
        sub._callbacks["t/r2"] = [MagicMock()]
        sub._on_connect(mock_client, None, None, 0)
        assert mock_client.subscribe.call_count == 2


class TestMQTTSubscriberOnDisconnect:
    """_on_disconnect callback behaviour."""

    def test_disconnect_sets_flag(self):
        """_on_disconnect sets _connected to False."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._connected = True
        sub._on_disconnect(MagicMock(), None, 0)
        assert sub._connected is False


class TestMQTTSubscriberDisconnect:
    """disconnect() method."""

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self):
        """disconnect() stops the loop and sets client to None."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._client = MagicMock()
        sub._connected = True
        await sub.disconnect()
        assert sub._client is None
        assert sub._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """disconnect() is a no-op when no client exists."""
        sub = MQTTSubscriber(topic_prefix="t")
        await sub.disconnect()  # should not raise
        assert sub._client is None


class TestMQTTSubscriberOnMessage:
    """_on_message callback behaviour."""

    def test_message_queued(self):
        """_on_message puts the message into the async queue."""
        sub = MQTTSubscriber(topic_prefix="t")
        loop = asyncio.new_event_loop()
        sub._loop = loop

        msg = MagicMock()
        msg.topic = "t/run1"
        msg.payload = b'{"key": "value"}'

        sub._on_message(None, None, msg)
        loop.close()


class TestMQTTSubscriberProcessMessages:
    """process_messages(), async message dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatches_to_callback(self):
        """Messages in the queue are dispatched to registered callbacks."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb = MagicMock()
        sub._callbacks["t/run1"] = [cb]

        # Pre-load a message and a CancelledError to stop the loop
        await sub._message_queue.put(("t/run1", '{"caption": "hello"}', 1.0))

        # Run process_messages with a short cancel
        task = asyncio.create_task(sub.process_messages())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        cb.assert_called_once()
        args = cb.call_args[0]
        assert args[0] == "run1"  # run_id extracted from topic
        assert args[1] == {"caption": "hello"}

    @pytest.mark.asyncio
    async def test_extracts_metadata_field(self):
        """If payload contains a 'metadata' wrapper, the inner data is forwarded."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb = MagicMock()
        sub._callbacks["t/run2"] = [cb]

        payload = json.dumps({"metadata": {"text": "detected"}, "blob": ""})
        await sub._message_queue.put(("t/run2", payload, 2.0))

        task = asyncio.create_task(sub.process_messages())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        cb.assert_called_once()
        assert cb.call_args[0][1] == {"text": "detected"}

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        """Invalid JSON payloads are wrapped in a {'raw': ...} dict."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb = MagicMock()
        sub._callbacks["t/run3"] = [cb]

        await sub._message_queue.put(("t/run3", "not-json", 3.0))

        task = asyncio.create_task(sub.process_messages())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        cb.assert_called_once()
        assert cb.call_args[0][1] == {"raw": "not-json"}
