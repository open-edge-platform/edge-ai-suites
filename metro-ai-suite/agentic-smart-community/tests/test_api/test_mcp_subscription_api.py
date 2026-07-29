# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for api-reference-mcp-subscription.md."""

from __future__ import annotations

import http.client
from urllib.parse import urlsplit

from conftest import McpApiClient, http_json


def _client(mcp_api: McpApiClient) -> McpApiClient:
    client = McpApiClient(mcp_api.url)
    client.initialize()
    return client


def test_subscribe_read_and_unsubscribe(mcp_api: McpApiClient):
    client = _client(mcp_api)
    uri = "smartbuilding://monitor/cam_child/alerts"

    subscribed = client.request("resources/subscribe", {"uri": uri})
    initial = client.read_resource(uri)
    incremental = client.read_resource(f"{uri}?since={initial['latestId']}")
    unsubscribed = client.request("resources/unsubscribe", {"uri": uri})

    assert subscribed["result"] == {}
    assert initial == {"monitorId": "cam_child", "latestId": 0, "alerts": []}
    assert incremental == {"monitorId": "cam_child", "latestId": 0, "alerts": []}
    assert unsubscribed["result"] == {}


def test_sse_stream_accepts_subscribed_session(mcp_api: McpApiClient):
    client = _client(mcp_api)
    uri = "smartbuilding://monitor/cam_child/alerts"
    client.request("resources/subscribe", {"uri": uri})
    parsed = urlsplit(client.url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)

    connection.request(
        "GET",
        parsed.path,
        headers={
            "Accept": "text/event-stream",
            "mcp-session-id": client.session_id or "",
        },
    )
    response = connection.getresponse()

    assert response.status == 200
    assert response.getheader("Content-Type", "").startswith("text/event-stream")
    connection.close()


def test_unknown_session_is_rejected(mcp_api: McpApiClient):
    client = McpApiClient(mcp_api.url)
    client.session_id = "unknown-session"

    status, _, response = http_json(
        client.url,
        method="POST",
        headers=client.headers,
        body={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/subscribe",
            "params": {"uri": "smartbuilding://monitor/cam_child/alerts"},
        },
    )

    assert status == 400
    assert "error" in response