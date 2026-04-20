# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.mqtt_subscriber, MQTT subscriber service."""

import asyncio
import importlib
import json
from unittest.mock import AsyncMock, MagicMock
from urllib.error import HTTPError, URLError

import pytest

from backend.services.mqtt_subscriber import MQTTSubscriber
import backend.services.mqtt_subscriber as mqtt_subscriber_module


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

    def test_message_queued(self, monkeypatch):
        """_on_message submits queue put operation to the event loop."""
        sub = MQTTSubscriber(topic_prefix="t")
        loop = asyncio.new_event_loop()
        sub._loop = loop

        called = {"count": 0}

        def _fake_run_coroutine_threadsafe(coro, _loop):
            called["count"] += 1
            # Close the coroutine to avoid un-awaited coroutine warnings in tests.
            coro.close()
            return MagicMock()

        monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _fake_run_coroutine_threadsafe)

        msg = MagicMock()
        msg.topic = "t/run1"
        msg.payload = b'{"key": "value"}'

        sub._on_message(None, None, msg)
        assert called["count"] == 1
        loop.close()

    def test_on_message_queue_submit_failure_is_handled(self, monkeypatch):
        """If queue submit fails, the message is dropped without raising."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._loop = asyncio.new_event_loop()

        def _raise(coro, *_args, **_kwargs):
            coro.close()
            raise RuntimeError("queue full")

        warning_mock = MagicMock()
        monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _raise)
        monkeypatch.setattr(mqtt_subscriber_module.logger, "warning", warning_mock)

        msg = MagicMock()
        msg.topic = "t/run1"
        msg.payload = b'{"key": "value"}'

        sub._on_message(None, None, msg)
        warning_mock.assert_called()
        sub._loop.close()

    def test_on_message_payload_decode_error_is_handled(self, monkeypatch):
        """Payload decode failure is logged and swallowed."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._loop = asyncio.new_event_loop()

        error_mock = MagicMock()
        monkeypatch.setattr(mqtt_subscriber_module.logger, "error", error_mock)

        msg = MagicMock()
        msg.topic = "t/run1"
        msg.payload = b"\xff\xfe"

        sub._on_message(None, None, msg)
        error_mock.assert_called()
        sub._loop.close()


class TestMQTTSubscriberEmbeddingRequest:
    """Tests for embedding API request and async submit wrapper."""

    def test_post_embedding_request_success(self, monkeypatch):
        """Successful embedding API response does not raise."""
        sub = MQTTSubscriber(topic_prefix="t", embedding_api_url="http://embed/api")

        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        monkeypatch.setattr(mqtt_subscriber_module, "urlopen", lambda *_a, **_kw: response)
        sub._post_embedding_request("img", {"result": "hello"})

    def test_post_embedding_request_non_2xx_raises(self, monkeypatch):
        """Non-2xx embedding response is converted to RuntimeError."""
        sub = MQTTSubscriber(topic_prefix="t", embedding_api_url="http://embed/api")

        response = MagicMock()
        response.status = 500
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        monkeypatch.setattr(mqtt_subscriber_module, "urlopen", lambda *_a, **_kw: response)
        with pytest.raises(RuntimeError, match="unexpected status code"):
            sub._post_embedding_request("img", {"result": "hello"})

    def test_post_embedding_request_http_error_raises(self, monkeypatch):
        """HTTPError from embedding API is wrapped with status/details."""
        sub = MQTTSubscriber(topic_prefix="t", embedding_api_url="http://embed/api")

        err = HTTPError(
            url="http://embed/api",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b"bad payload")),
        )

        monkeypatch.setattr(mqtt_subscriber_module, "urlopen", MagicMock(side_effect=err))
        with pytest.raises(RuntimeError, match="status 400"):
            sub._post_embedding_request("img", "plain-metadata")

    def test_post_embedding_request_url_error_raises(self, monkeypatch):
        """URLError from embedding API is wrapped as RuntimeError."""
        sub = MQTTSubscriber(topic_prefix="t", embedding_api_url="http://embed/api")

        monkeypatch.setattr(
            mqtt_subscriber_module,
            "urlopen",
            MagicMock(side_effect=URLError("connection refused")),
        )
        with pytest.raises(RuntimeError, match="could not be completed"):
            sub._post_embedding_request("img", {"result": "hello"})

    @pytest.mark.asyncio
    async def test_submit_embedding_uses_to_thread(self, monkeypatch):
        """_submit_embedding delegates synchronous request via asyncio.to_thread."""
        sub = MQTTSubscriber(topic_prefix="t")

        called = {"fn": None, "args": None}

        async def _fake_to_thread(fn, *args):
            called["fn"] = fn
            called["args"] = args
            return None

        monkeypatch.setattr(asyncio, "to_thread", _fake_to_thread)
        await sub._submit_embedding("img", {"result": "hello"})

        assert called["fn"] == sub._post_embedding_request
        assert called["args"] == ("img", {"result": "hello"})


class TestMQTTSubscriberConnect:
    """connect() branch coverage."""

    @pytest.mark.asyncio
    async def test_connect_noop_when_client_exists(self):
        """connect() returns early when client is already initialized."""
        sub = MQTTSubscriber(topic_prefix="t")
        sub._client = MagicMock()
        await sub.connect()

    @pytest.mark.asyncio
    async def test_connect_timeout_path(self, monkeypatch):
        """connect() logs timeout when broker never reaches connected state."""
        sub = MQTTSubscriber(topic_prefix="t")

        mock_client = MagicMock()
        monkeypatch.setattr(mqtt_subscriber_module.mqtt, "Client", lambda **_kwargs: mock_client)
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        warning_mock = MagicMock()
        monkeypatch.setattr(mqtt_subscriber_module.logger, "warning", warning_mock)

        await sub.connect()

        mock_client.connect_async.assert_called_once()
        mock_client.loop_start.assert_called_once()
        warning_mock.assert_called()

    @pytest.mark.asyncio
    async def test_connect_re_raises_client_exception(self, monkeypatch):
        """Exceptions while connecting are logged then re-raised."""
        sub = MQTTSubscriber(topic_prefix="t")

        mock_client = MagicMock()
        mock_client.connect_async.side_effect = RuntimeError("boom")
        monkeypatch.setattr(mqtt_subscriber_module.mqtt, "Client", lambda **_kwargs: mock_client)
        error_mock = MagicMock()
        monkeypatch.setattr(mqtt_subscriber_module.logger, "error", error_mock)

        with pytest.raises(RuntimeError, match="boom"):
            await sub.connect()
        error_mock.assert_called()


class TestMQTTSubscriberProcessMessages:
    """process_messages(), async message dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatches_to_callback(self):
        """Messages in the queue are dispatched to registered callbacks."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb = MagicMock()
        sub._callbacks["t/run1"] = [cb]

        # Pre-load a message and a CancelledError to stop the loop
        await sub._message_queue.put(("t/run1", '{"result": "hello"}', 1.0))

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
        assert args[1] == {"result": "hello"}

    @pytest.mark.asyncio
    async def test_extracts_metadata_field(self):
        """If payload contains a 'metadata' wrapper, the inner data is forwarded."""
        sub = MQTTSubscriber(topic_prefix="t")
        cb = MagicMock()
        sub._callbacks["t/run2"] = [cb]

        payload = json.dumps({"metadata": {"text": "detected", "result": "detected"}, "blob": ""})
        await sub._message_queue.put(("t/run2", payload, 2.0))

        task = asyncio.create_task(sub.process_messages())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        cb.assert_called_once()
        assert cb.call_args[0][1] == {"text": "detected", "result": "detected"}

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        """Invalid JSON payloads are ignored because they do not contain result."""
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

        cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_embedding_submission_failure_is_logged(self, monkeypatch):
        """Embedding submission errors are logged and do not stop processing."""
        sub = MQTTSubscriber(topic_prefix="t")
        monkeypatch.setattr(mqtt_subscriber_module, "ENABLE_EMBEDDING", True)

        cb = MagicMock()
        sub._callbacks["t/run4"] = [cb]
        sub._submit_embedding = AsyncMock(side_effect=RuntimeError("embed failed"))
        error_mock = MagicMock()
        monkeypatch.setattr(mqtt_subscriber_module.logger, "error", error_mock)

        payload = json.dumps({"metadata": {"result": "ok"}, "blob": "base64"})
        await sub._message_queue.put(("t/run4", payload, 4.0))

        task = asyncio.create_task(sub.process_messages())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        sub._submit_embedding.assert_awaited_once()
        cb.assert_called_once()
        error_mock.assert_called()

    @pytest.mark.asyncio
    async def test_callback_exceptions_are_logged(self, monkeypatch):
        """A failing callback is isolated and logged."""
        sub = MQTTSubscriber(topic_prefix="t")

        def _bad_callback(*_args):
            raise RuntimeError("callback failed")

        sub._callbacks["t/run5"] = [_bad_callback]
        error_mock = MagicMock()
        monkeypatch.setattr(mqtt_subscriber_module.logger, "error", error_mock)

        await sub._message_queue.put(("t/run5", '{"result": "hello"}', 5.0))

        task = asyncio.create_task(sub.process_messages())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        error_mock.assert_called()

    @pytest.mark.asyncio
    async def test_outer_process_messages_exception_is_logged(self, monkeypatch):
        """Unexpected processing errors are logged and loop continues."""
        sub = MQTTSubscriber(topic_prefix="t")

        error_mock = MagicMock()
        sleep_mock = AsyncMock()
        monkeypatch.setattr(mqtt_subscriber_module.logger, "error", error_mock)
        monkeypatch.setattr(asyncio, "sleep", sleep_mock)

        calls = {"n": 0}

        async def _fake_get():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            raise asyncio.CancelledError

        monkeypatch.setattr(sub._message_queue, "get", _fake_get)

        await sub.process_messages()

        error_mock.assert_called()
        sleep_mock.assert_awaited()


class TestMQTTSubscriberSubscribeUnsubscribeConnected:
    """Subscription calls against an active MQTT client."""

    def test_subscribe_calls_client_when_connected(self):
        sub = MQTTSubscriber(topic_prefix="t")
        sub._client = MagicMock()
        sub._connected = True

        cb = MagicMock()
        sub.subscribe_to_run("r2", cb)

        sub._client.subscribe.assert_called_once_with("t/r2")

    def test_unsubscribe_calls_client_when_connected(self):
        sub = MQTTSubscriber(topic_prefix="t")
        sub._client = MagicMock()
        sub._connected = True

        sub._callbacks["t/r3"] = [MagicMock()]
        sub.unsubscribe_from_run("r3")

        sub._client.unsubscribe.assert_called_once_with("t/r3")


class TestMQTTSubscriberGlobalLifecycle:
    """Global singleton helper coverage."""

    @pytest.mark.asyncio
    async def test_get_mqtt_subscriber_creates_and_reuses_singleton(self, monkeypatch):
        module = importlib.reload(mqtt_subscriber_module)
        module._mqtt_subscriber = None
        module._message_processor_task = None

        created = {"count": 0}

        class _FakeSubscriber:
            def __init__(self):
                created["count"] += 1
                self.connect = AsyncMock()

            async def process_messages(self):
                await asyncio.sleep(3600)

        monkeypatch.setattr(module, "MQTTSubscriber", _FakeSubscriber)

        def _fake_create_task(coro):
            coro.close()
            return MagicMock()

        monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

        sub1 = await module.get_mqtt_subscriber()
        sub2 = await module.get_mqtt_subscriber()

        assert created["count"] == 1
        assert sub1 is sub2

    @pytest.mark.asyncio
    async def test_shutdown_mqtt_subscriber_cancels_task_and_disconnects(self):
        module = importlib.reload(mqtt_subscriber_module)

        class _FakeSubscriber:
            def __init__(self):
                self.disconnect = AsyncMock()

        fake_subscriber = _FakeSubscriber()
        module._mqtt_subscriber = fake_subscriber
        module._message_processor_task = asyncio.create_task(asyncio.sleep(3600))

        await module.shutdown_mqtt_subscriber()

        fake_subscriber.disconnect.assert_awaited_once()
        assert module._mqtt_subscriber is None
        assert module._message_processor_task is None
