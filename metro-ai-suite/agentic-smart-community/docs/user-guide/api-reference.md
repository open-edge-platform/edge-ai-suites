# API Reference

The platform exposes MCP capabilities through Streamable HTTP and two RESTful HTTP APIs.

| API | Service | Base | What it covers |
|-----|---------|------|----------------|
| [MCP Tools and Resources API Reference](get-started/api-reference-mcp.md) | MCP Server | `http://<mcp-host>:3100/mcp` | Complete JSON-RPC reference for session setup, all MCP tool calls, resource reads, subscriptions, and SSE notifications. |
| [MCP Subscription Reference](get-started/api-reference-mcp-subscription.md) | MCP Server | `http://<mcp-host>:3100/mcp` | MCP session initialization, alert-resource subscriptions, SSE update notifications, cursor-based reads, and proactive-delivery integration. |
| [MCP Webhook Event API](get-started/api-reference-mcp-webhook-event.md) | MCP Server | `http://<mcp-host>:3101` | The `POST /events` ingest contract — envelope, per-`type` payloads (`motion` / `static` / `recording`), response codes, and the resulting DB writes. |
| [Dashboard API Reference](get-started/api-reference-dashboard.md) | MCP Server | `http://<mcp-host>:3100/api` | Monitor discovery, activity, reports, stats, snapshot/clip media, RTSP live preview, Router status, and optional OpenClaw chat proxy. |
| [Videostream Analytics HTTP API](get-started/api-reference-videostream-analytics.md) | videostream-analytics (VSA) | `http://<vsa-host>:8999` | The VSA control plane — register / start / stop / pause / restart sources, hot-update pipeline config, the source lifecycle state machine, and the events VSA emits. |

## Data flow

The MCP and REST APIs form a control and event flow: an MCP client calls tools or reads resources,
the MCP server drives **VSA's control plane**, and VSA pushes pipeline events back to the MCP
server's **webhook**.

```
   MCP server                       videostream-analytics (:8999)
            │  register / start / stop / pause / restart  ── VSA HTTP API
            └──────────────────────────────────────────────────▶ │
                                                                 │  RTSP → motion
                                                                 │  → prefilter → clips
   MCP Server (:3101)                                            │
            ◀──── POST /events  (motion / static / recording) ───┘  ── Webhook API
```

## Conventions

Common to the two RESTful APIs:

- **Transport** — JSON request/response bodies, `Content-Type: application/json`, UTF-8.
- **Auth** — none; deploy on loopback / private LAN / behind a reverse proxy.
- **Status codes** — `200` success · `404` unknown source · `422` schema / semantic validation failure · `4xx` permanent (do not retry) · `5xx` transient (retry after backoff).
- **Health probe** — both services answer `GET /health`.

See each linked document for the full endpoint list, request / response schemas, and worked examples.

## See also

- [Get Started Guide](get-started.md)
- [MCP Tools and Resources API Reference](get-started/api-reference-mcp.md)
- [MCP Subscription Reference](get-started/api-reference-mcp-subscription.md)
- [System Requirements](get-started/system-requirements.md)
- [Release Notes](release-notes.md)
