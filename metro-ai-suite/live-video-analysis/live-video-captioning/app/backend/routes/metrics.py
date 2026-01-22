# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
WebSocket-based metrics relay for live system monitoring.

This module provides WebSocket endpoints to receive metrics from a collector service
and broadcast them to connected dashboard clients for real-time visualization.

Architecture:
    - /ws/collector: Single collector connection (exclusive lock)
    - /ws/clients: Multiple client connections for live metric streaming

Telegraf sends metrics as a JSON array directly:
    [
        {
            "name": "cpu",
            "tags": {"cpu": "cpu-total", "host": "container_id"},
            "fields": {"usage_user": 0.14},
            "timestamp": 1767758563
        },
        ...
    ]

We wrap this as {"metrics": [...]} before forwarding to clients.
"""

import logging
from asyncio import Lock
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

router = APIRouter(tags=["metrics"])
logger = logging.getLogger("app.metrics")

# Single collector websocket (None if not connected)
collector_ws: Optional[WebSocket] = None
collector_lock = Lock()

# Set of client websockets
client_connections: Set[WebSocket] = set()
clients_lock = Lock()


@router.websocket("/ws/collector")
async def collector_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for a single metrics collector (Telegraf).

    This endpoint accepts exactly one collector connection at a time. Telegraf
    sends metric batches as JSON arrays, which are wrapped and broadcast to clients.

    Protocol:
        * Accepts one collector at a time (enforced via lock)
        * Receives JSON metric arrays from Telegraf (text or binary mode)
        * Wraps as {"metrics": [...]} and broadcasts to /ws/clients
        * Handles disconnection and errors gracefully
        * Releases collector slot on exit

    Telegraf Message Format (array of metrics):
        [
            {
                "name": "cpu",
                "tags": {"cpu": "cpu-total", "host": "52bb47bc4271"},
                "fields": {"usage_user": 0.14},
                "timestamp": 1767758563
            },
            ...
        ]

    Error Handling:
        * Connection already exists → reject with WS_1008_POLICY_VIOLATION
        * Client disconnect → logged; collector slot released
        * Unexpected exception → logged; collector slot released
    """
    global collector_ws

    await websocket.accept()
    logger.info("Collector attempting to connect from %s", websocket.client)

    async with collector_lock:
        if collector_ws is not None:
            logger.warning(
                "Rejecting new collector connection: one is already connected."
            )
            await websocket.send_json(
                {"error": "Only one collector connection allowed."}
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        collector_ws = websocket
        logger.info("Collector connected from %s", websocket.client)

    try:
        while True:
            # Receive JSON - Telegraf sends as binary
            data = await websocket.receive_json(mode="binary")
            logger.debug("Received metrics from collector: %s", data)

            # Telegraf sends an array of metrics directly, wrap it
            if isinstance(data, list):
                wrapped_data = {"metrics": data}
            elif isinstance(data, dict) and "metrics" in data:
                # Already wrapped
                wrapped_data = data
            else:
                # Single metric or unknown format, wrap as array
                wrapped_data = {"metrics": [data] if isinstance(data, dict) else data}

            # Broadcast to all connected clients
            disconnects = []
            async with clients_lock:
                clients = list(client_connections)

            for client in clients:
                try:
                    await client.send_json(wrapped_data, mode="text")
                    logger.debug("Forwarded metrics to client %s", client.client)
                except Exception as e:
                    logger.error(
                        "Error sending to client %s: %s", client.client, e
                    )
                    disconnects.append(client)

            # Cleanup disconnected clients
            if disconnects:
                async with clients_lock:
                    for client in disconnects:
                        client_connections.discard(client)
                logger.debug(
                    "Cleaned up %d disconnected clients", len(disconnects)
                )

    except WebSocketDisconnect:
        logger.info("Collector disconnected: %s", websocket.client)
    except Exception as e:
        logger.error("Exception in collector handler: %s", e)
    finally:
        async with collector_lock:
            if collector_ws == websocket:
                collector_ws = None
        logger.debug("Collector slot released")


@router.websocket("/ws/clients")
async def clients_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for dashboard clients receiving live metrics.

    This endpoint accepts multiple concurrent client connections. Each client
    receives real-time metric updates broadcast from the collector.

    Protocol:
        * Accepts unlimited concurrent connections
        * Pushes every metric payload from /ws/collector as JSON
        * Ignores messages sent by clients (only logs them)
        * Handles disconnection and cleanup gracefully

    Client Integration:
        JavaScript example:
            const ws = new WebSocket('ws://localhost:4173/ws/clients');
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                // data.metrics = array of metric objects
                updateCharts(data.metrics);
            };

    Message Format (sent to clients):
        Same as collector format - see collector_websocket() docstring.

    Error Handling:
        * Client disconnect → connection removed from set
        * Unexpected exception → logged; connection cleaned up
    """
    await websocket.accept()
    logger.info("Client connected: %s", websocket.client)

    async with clients_lock:
        client_connections.add(websocket)
        logger.debug(
            "Total clients connected: %d", len(client_connections)
        )

    try:
        while True:
            # Keep connection alive; ignore client messages
            msg = await websocket.receive_text()
            logger.debug(
                "Received message from client %s (ignored): %s",
                websocket.client,
                msg[:100],
            )
    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", websocket.client)
    except Exception as e:
        logger.error(
            "Exception in client handler for %s: %s",
            websocket.client,
            e,
            exc_info=True,
        )
    finally:
        async with clients_lock:
            client_connections.discard(websocket)
            logger.debug(
                "Client removed. Total clients: %d", len(client_connections)
            )


@router.get("/api/metrics/status")
async def metrics_status():
    """
    Get the current status of metrics collection.

    Returns:
        {
            "collector_connected": bool,
            "clients_connected": int
        }
    """
    async with collector_lock:
        collector_connected = collector_ws is not None

    async with clients_lock:
        num_clients = len(client_connections)

    return {
        "collector_connected": collector_connected,
        "clients_connected": num_clients,
    }
