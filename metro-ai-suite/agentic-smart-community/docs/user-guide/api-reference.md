# RESTful API Reference

The platform's HTTP services expose two RESTful APIs. Both speak JSON over HTTP, run in a trusted network segment (no auth), and use standard status codes.

| API | Service | Base | What it covers |
|-----|---------|------|----------------|
| [MCP Webhook Event API](get-started/mcp_webhook_event_api.md) | MCP Server | `http://<mcp-host>:3101` | The `POST /events` ingest contract — envelope, per-`type` payloads (`motion` / `static` / `recording`), response codes, and the resulting DB writes. |
| [Videostream Analytics HTTP API](get-started/videostream_analytics_api.md) | videostream-analytics (VSA) | `http://<vsa-host>:8999` | The VSA control plane — register / start / stop / pause / restart sources, hot-update pipeline config, the source lifecycle state machine, and the events VSA emits. |

## Data flow

The two APIs form a producer → consumer pair: an operator drives **VSA's control plane** to register cameras, and VSA in turn pushes pipeline events to the MCP server's **webhook**.

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

Common to both APIs:

- **Transport** — JSON request/response bodies, `Content-Type: application/json`, UTF-8.
- **Auth** — none; deploy on loopback / private LAN / behind a reverse proxy.
- **Status codes** — `200` success · `404` unknown source · `422` schema / semantic validation failure · `4xx` permanent (do not retry) · `5xx` transient (retry after backoff).
- **Health probe** — both services answer `GET /health`.

See each linked document for the full endpoint list, request / response schemas, and worked examples.

## See also

- [Get Started Guide](get-started.md)
- [System Requirements](get-started/system-requirements.md)
- [Release Notes](release-notes.md)
