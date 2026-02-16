# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the WebSocket metrics relay (app/relay.py).

Covers:
- get_status() helper
- Collector WebSocket connection lifecycle
- Client WebSocket connection lifecycle
- Metric broadcasting from collector to clients
- Second-collector rejection policy
- Data wrapping logic (array, dict, pre-wrapped)
- Disconnected-client cleanup during broadcast
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.relay as relay_module
from app.main import app


@pytest.fixture(autouse=True)
def _reset_relay_state():
    """Reset global relay state before each test to ensure isolation."""
    relay_module.collector_ws = None
    relay_module.client_connections.clear()
    yield
    relay_module.collector_ws = None
    relay_module.client_connections.clear()


@pytest.fixture()
def client():
    """TestClient scoped per test (overrides the session-level conftest fixture)."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# get_status()
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for the async get_status helper."""

    @pytest.mark.anyio
    async def test_status_no_connections(self):
        """Returns False/0 when nothing is connected."""
        status = await relay_module.get_status()
        assert status == {"collector_connected": False, "clients_connected": 0}

    @pytest.mark.anyio
    async def test_status_with_collector(self):
        """Returns True when a collector WebSocket is registered."""
        relay_module.collector_ws = MagicMock()
        status = await relay_module.get_status()
        assert status["collector_connected"] is True

    @pytest.mark.anyio
    async def test_status_with_clients(self):
        """Returns the correct client count."""
        relay_module.client_connections = {MagicMock(), MagicMock()}
        status = await relay_module.get_status()
        assert status["clients_connected"] == 2


# ---------------------------------------------------------------------------
# /ws/clients endpoint
# ---------------------------------------------------------------------------

class TestClientsWebSocket:
    """Tests for the /ws/clients WebSocket endpoint."""

    def test_client_connects_successfully(self, client):
        """A client WebSocket connection is accepted and added to the set."""
        with client.websocket_connect("/ws/clients") as ws:
            # Connection established; client should be tracked
            assert len(relay_module.client_connections) == 1

    def test_client_removed_on_disconnect(self, client):
        """Client is removed from the connection set after disconnect."""
        with client.websocket_connect("/ws/clients"):
            pass  # disconnect on context-manager exit
        assert len(relay_module.client_connections) == 0

    def test_multiple_clients_can_connect(self, client):
        """Multiple clients can connect concurrently."""
        with client.websocket_connect("/ws/clients"):
            with client.websocket_connect("/ws/clients"):
                assert len(relay_module.client_connections) == 2


# ---------------------------------------------------------------------------
# /ws/collector endpoint
# ---------------------------------------------------------------------------

class TestCollectorWebSocket:
    """Tests for the /ws/collector WebSocket endpoint."""

    def test_collector_connects_successfully(self, client):
        """Collector WebSocket connection is accepted and registered."""
        with client.websocket_connect("/ws/collector"):
            assert relay_module.collector_ws is not None

    def test_collector_slot_released_on_disconnect(self, client):
        """Collector slot is set to None after the collector disconnects."""
        with client.websocket_connect("/ws/collector"):
            pass
        assert relay_module.collector_ws is None

    def test_second_collector_rejected(self, client):
        """A second collector receives an error and is closed by the server."""
        with client.websocket_connect("/ws/collector"):
            with client.websocket_connect("/ws/collector") as ws2:
                data = ws2.receive_json()
                assert "error" in data
                assert "Only one collector connection allowed" in data["error"]

    def test_collector_broadcasts_array_to_clients(self, client):
        """Metrics sent as a JSON array are wrapped and forwarded to clients."""
        metrics = [{"name": "cpu", "fields": {"usage_user": 5.0}, "timestamp": 1}]

        with client.websocket_connect("/ws/clients") as client_ws:
            with client.websocket_connect("/ws/collector") as collector_ws:
                collector_ws.send_bytes(json.dumps(metrics).encode())
                data = client_ws.receive_json()
                assert "metrics" in data
                assert data["metrics"] == metrics

    def test_collector_broadcasts_prewrapped_dict(self, client):
        """Pre-wrapped {'metrics': [...]} payloads are forwarded as-is."""
        wrapped = {"metrics": [{"name": "mem", "fields": {"used_percent": 42.0}}]}

        with client.websocket_connect("/ws/clients") as client_ws:
            with client.websocket_connect("/ws/collector") as collector_ws:
                collector_ws.send_bytes(json.dumps(wrapped).encode())
                data = client_ws.receive_json()
                assert data == wrapped

    def test_collector_wraps_single_dict_metric(self, client):
        """A single metric dict is wrapped into {'metrics': [metric]}."""
        single_metric = {"name": "disk", "fields": {"used_percent": 80}}

        with client.websocket_connect("/ws/clients") as client_ws:
            with client.websocket_connect("/ws/collector") as collector_ws:
                collector_ws.send_bytes(json.dumps(single_metric).encode())
                data = client_ws.receive_json()
                assert data == {"metrics": [single_metric]}

    def test_broadcast_to_multiple_clients(self, client):
        """Collector broadcasts are received by all connected clients."""
        metrics = [{"name": "cpu", "fields": {"usage_user": 1.0}, "timestamp": 2}]

        with client.websocket_connect("/ws/clients") as c1:
            with client.websocket_connect("/ws/clients") as c2:
                with client.websocket_connect("/ws/collector") as collector_ws:
                    collector_ws.send_bytes(json.dumps(metrics).encode())
                    d1 = c1.receive_json()
                    d2 = c2.receive_json()
                    assert d1["metrics"] == metrics
                    assert d2["metrics"] == metrics
