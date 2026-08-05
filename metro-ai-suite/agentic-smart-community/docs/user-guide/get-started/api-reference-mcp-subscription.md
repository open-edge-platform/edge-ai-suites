<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# MCP Subscription Reference

Use MCP resource subscriptions to receive alert-update notifications from a monitor. This is a standard MCP capability: the server notifies the subscribed client when alerts change. The notification contains the resource URI, not the alert payload; read the resource with a cursor to retrieve the new alerts.

## Alert resource URIs

| Purpose | URI |
|---|---|
| Subscribe or perform an initial read | `smartbuilding://monitor/<monitor_id>/alerts` |
| Read alerts after a cursor | `smartbuilding://monitor/<monitor_id>/alerts?since=<latestId>` |

Only delivered alerts are returned. Use `smartbuilding_alert_query` when you need the full audit trail, including cooled-down alerts.

## Subscription API Reference

The MCP endpoint is `http://<mcp-host>:3100/mcp`. Use `POST /mcp` for JSON-RPC requests and `GET /mcp` for the SSE notification stream. Send `Accept: application/json, text/event-stream` on POST requests. After `initialize`, send the returned `mcp-session-id` header on every request for that session.

| Operation | HTTP request | JSON-RPC request | Result |
|---|---|---|---|
| Initialize a session | `POST /mcp` | `initialize` | `200` response with an `mcp-session-id` header. |
| Complete initialization | `POST /mcp` | `notifications/initialized` | Notification; no result body is required. |
| Subscribe | `POST /mcp` | `resources/subscribe` | Empty JSON-RPC result; future changes generate notifications. |
| Read alerts | `POST /mcp` | `resources/read` | Resource content containing `monitorId`, `latestId`, and `alerts`. |
| Receive updates | `GET /mcp` | None; use SSE | `notifications/resources/updated` notification for each changed subscribed resource. |

### `resources/subscribe`

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "resources/subscribe",
  "params": {
    "uri": "smartbuilding://monitor/<monitor_id>/alerts"
  }
}
```

The subscription is associated with the current `mcp-session-id`. Resubscribe after establishing a new session.

### `resources/read`

Use the bare URI for an initial read:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resources/read",
  "params": {
    "uri": "smartbuilding://monitor/<monitor_id>/alerts"
  }
}
```

For incremental reads, use the previously returned `latestId`:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "resources/read",
  "params": {
    "uri": "smartbuilding://monitor/<monitor_id>/alerts?since=<latestId>"
  }
}
```

The JSON-RPC response contains a resource content item. Its `text` field is a JSON string with this shape:

```json
{
  "monitorId": "cam_child",
  "latestId": 42,
  "alerts": [
    {
      "id": 42
    }
  ]
}
```

`latestId` remains equal to the supplied cursor when no new alert exists. Persist it only after successfully processing every returned alert.

### `notifications/resources/updated`

The server sends this JSON-RPC notification through the SSE stream after an alert resource changes:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/updated",
  "params": {
    "uri": "smartbuilding://monitor/<monitor_id>/alerts"
  }
}
```

The notification does not contain alert data. Read the same resource with the stored cursor to obtain the payload.

## Subscription sequence

1. Send `initialize` to `POST /mcp` and retain the `mcp-session-id` response header.
2. Send the required `notifications/initialized` notification using that session ID.
3. Send `resources/subscribe` for the monitor alert URI.
4. Keep a `GET /mcp` SSE connection open with the same session ID.

## Terminal Example

Set the endpoint and the monitor you want to observe:

```bash
export MCP_URL=http://localhost:3100/mcp
export MONITOR_ID=cam_child
```

Initialize an MCP session and capture its session ID:

```bash
SID=$(curl -fsS -D - -o /tmp/mcp-initialize.json -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"subscription-reference","version":"1.0"}}}' \
  | grep -i '^mcp-session-id:' | tr -d '\r' | cut -d' ' -f2)

test -n "$SID" || echo "MCP server did not return mcp-session-id; verify the MCP endpoint before continuing." >&2
echo "MCP session ID: $SID"
```

Complete the MCP handshake and subscribe to the monitor's alerts:

```bash
curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"resources/subscribe\",\"params\":{\"uri\":\"smartbuilding://monitor/$MONITOR_ID/alerts\"}}"
```

Perform an initial read. Save `latestId` from the JSON in `result.contents[0].text`; it is the cursor for the next read.

```bash
curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"resources/read\",\"params\":{\"uri\":\"smartbuilding://monitor/$MONITOR_ID/alerts\"}}"
```

In another terminal, copy the session ID printed above, set it as `SID`, then open the SSE stream and keep it open:

```bash
export MCP_URL=http://localhost:3100/mcp
export SID="<MCP session ID from the first terminal>"
curl -fsS -N -X GET "$MCP_URL" \
  -H "Accept: text/event-stream" \
  -H "mcp-session-id: $SID"
```

> The idle stream prints periodic `keepalive` heartbeats to hold the connection open; this is expected. `curl` is not an SSE client, so it echoes every byte, including heartbeats. A real SSE/MCP client ignores them.

When an alert is created, the stream receives a notification like this:

```text
event: message
data: {"jsonrpc":"2.0","method":"notifications/resources/updated","params":{"uri":"smartbuilding://monitor/cam_child/alerts"}}
```

Read the incremental alerts with the saved cursor, replace `<latestId>`, and then save the new `latestId` from the response:

```bash
curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"resources/read\",\"params\":{\"uri\":\"smartbuilding://monitor/$MONITOR_ID/alerts?since=<latestId>\"}}"
```

For an automated client, persist the cursor only after the alerts have been processed successfully. Reconnect with a new MCP session after a transport interruption, resubscribe, and continue from the persisted cursor.

## Proactive User Delivery

The subscription mechanism delivers updates to the connected MCP client. To proactively deliver those updates to an agent session or external user channel, add routing and delivery logic in the client environment. The [Smart Community MCP x OpenClaw adapter](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/packages/framework-adapter-sdk/examples/openclaw/README.md) is a reference implementation that subscribes, keeps cursors, reconnects, and injects alerts into configured OpenClaw sessions.