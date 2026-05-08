# API Reference

The Live Video Alert Agent exposes REST and SSE endpoints for management,
data consumption, and operational monitoring.


## Observability

### `GET /health`
Liveness probe. Always returns `200` if the application process is alive.
- **Response**:
  ```json
  {
    "status": "healthy",
    "streams_active": 2,
    "alerts_enabled": 3,
    "vlm_reachable": true,
    "uptime_seconds": 342.1,
    "timestamp": "2026-03-12T10:00:00Z"
  }
  ```

### `GET /ready`
Readiness probe. Returns `200` only when the manager is running and at least
one alert is enabled. Returns `503` otherwise.
- **Response** (ready):
  ```json
  {"status": "ready", "streams": 1, "alerts": 2}
  ```

### `GET /metrics`
System and per-stream inference counters.
- **Response**:
  ```json
  {
    "cpu_percent": 18.4,
    "memory_percent": 42.1,
    "streams": [
      {
        "stream_id": "cam1",
        "analysis_count": 120,
        "alert_count": 5,
        "last_inference_ms": 850.3
      }
    ]
  }
  ```

---

## Streaming

### `GET /events` (SSE)
Server-Sent Events stream for real-time updates.
- **Response Type**: `text/event-stream`
- **Events**:

| Event | When | Data fields |
|---|---|---|
| `init` | On connect | `results`, `streams` |
| `analysis` | Each VLM cycle | `stream_id`, `results` |
| `alert_action` | Alert fired + tools invoked | `stream_id`, `alert_name`, `severity`, `answer`, `reason`, `actions_taken`, `escalated`, `snapshot_path` |
| `keepalive` | Every 15 s | `ts` |

- **`alert_action` example**:
  ```json
  {
    "event": "alert_action",
    "data": {
      "stream_id": "cam1",
      "alert_name": "Fire Detection",
      "severity": "critical",
      "answer": "YES",
      "reason": "Flames visible in lower-left quadrant",
      "actions_taken": ["log_alert", "capture_snapshot"],
      "escalated": false,
      "snapshot_path": "/app/snapshots/cam1/Fire_Detection_critical_20260312T100512.jpg"
    }
  }
  ```

### `GET /video_feed`
MJPEG stream for live frame preview.
- **Query Parameters**: `stream_id` (string, default: `default`)
- **Response Type**: `multipart/x-mixed-replace; boundary=frame`

### `GET /data`
Polling endpoint returning latest VLM results enriched with runtime alert state. Prefer `/events` for new integrations.
- **Response**:
  ```json
  {
    "cam1": {
      "stream_name": "Lobby Camera",
      "alerts": {
        "Fire Detection": {
          "answer": "NO",
          "reason": "No fire or smoke visible",
          "consecutive_yes": 0,
          "consecutive_no": 3,
          "last_answer": "NO"
        }
      }
    }
  }
  ```

---

## Stream Management

### `GET /streams`
List all active streams with health status.
- **Response**:
  ```json
  {
    "streams": [
      {
        "stream_id": "cam1",
        "name": "Lobby Camera",
        "url": "rtsp://192.168.1.10:554/stream",
        "connected": true,
        "fps": 1.0,
        "resolution": "1920x1080",
        "buffer_fill": 1,
        "tools": [],
        "alerts": []
      }
    ]
  }
  ```

### `POST /streams`
Register a new video stream.
- **Request Body**:
  ```json
  {
    "stream_id": "cam1",
    "name": "Lobby Camera",
    "url": "rtsp://192.168.1.10:554/stream",
    "tools": [],
    "alerts": []
  }
  ```
- **Response**: `{"status": "added", "stream_id": "cam1"}`
- **Status Codes**: `200` added | `409` already exists | `422` validation error

### `PATCH /streams/{stream_id}`
Update per-stream settings.
- **Request Body**:
  ```json
  {"alerts": ["Fire Detection", "Person Detection"]}
  ```
  - `alerts` — list of alert names to evaluate for this stream
- **Response**:
  ```json
  {"id": "cam1", "alerts": ["Fire Detection", "Person Detection"]}
  ```
- **Status Codes**: `200` updated | `404` not found

### `DELETE /streams/{stream_id}`
Remove an active stream.
- **Response**: `{"status": "removed", "stream_id": "cam1"}`
- **Status Codes**: `200` removed | `404` not found

---

## Alert Configuration

### `GET /config/alerts`
Return the current alert configurations.
- **Response**: array of `AlertConfig` objects (see schema below).

### `POST /config/alerts`
Replace the full alert configuration.
- **Request Body**: array of alert config objects:
  ```json
  [
    {
      "name": "Fire Detection",
      "prompt": "Is there fire or smoke visible?",
      "enabled": true,
      "tools": ["log_alert", "capture_snapshot"],
      "escalation": {
        "threshold_consecutive": 3,
        "additional_tools": ["trigger_webhook", "publish_mqtt"]
      }
    },
    {
      "name": "Person Detection",
      "prompt": "Is there a person in the frame?",
      "enabled": true,
      "tools": ["log_alert"]
    }
  ]
  ```
- **Alert Config Fields**:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Alert identifier (letters, digits, spaces, hyphens, dots, underscores) |
| `prompt` | string | yes | Natural-language yes/no question sent to the VLM |
| `enabled` | bool | no (default `true`) | Whether this alert is active |
| `tools` | list of tool names | no (default `["log_alert", "capture_snapshot"]`) | Tools to invoke when alert fires |
| `tool_arguments` | object | no | Per-tool argument overrides; supports `{{variable}}` template placeholders |
| `escalation.threshold_consecutive` | int (≥ 2) | no | Consecutive YES count before escalation |
| `escalation.additional_tools` | list of tool names | no | Extra tools added on escalation |

- **Valid built-in tool names**: `log_alert`, `capture_snapshot`, `trigger_webhook`, `publish_mqtt`
- **MCP tool names** (when `MCP_ENABLED=true`): prefixed with `mcp_{server_name}_` (see [MCP section](#mcp))
- **Response**: `{"status": "saved", "count": 2}`
- **Status Codes**: `200` saved | `422` schema validation failed

---

## Action Tools

### `GET /tools`
List all registered action tools and whether they are currently enabled (based
on environment variable configuration).
- **Response**:
  ```json
  {
    "tools": [
      {
        "name": "log_alert",
        "description": "...",
        "enabled": true,
        "parameters": {}
      }
    ]
  }
  ```

### `POST /tools/{tool_name}/invoke`
Manually invoke a registered tool for testing.
- **Path Parameters**: `tool_name` — one of `log_alert`,
  `trigger_webhook`, `capture_snapshot`, `publish_mqtt`
- **Request Body**:
  ```json
  {"parameters": {"stream_id": "cam1", "alert_name": "Test"}}
  ```
- **Response**:
  ```json
  {
    "tool": "log_alert",
    "status": "success",
    "result": {"status": "logged"},
    "duration_ms": 1.2
  }
  ```
- **Status Codes**: `200` (success or error both return 200 with `status` field) | `404` tool not found

### `POST /tools/reload`
Reload tool definitions from `resources/tools.json` without restarting the application.
- **Response**: `{"status": "ok", "tools_loaded": 4}`
- **Status Codes**: `200` ok

---

## MCP

Model Context Protocol (MCP) endpoints allow the agent to discover and invoke tools from
external MCP servers. Enabled when `MCP_ENABLED=true` (default). Server connections can be
configured an added in `resources/mcp_servers.json`.

### `GET /mcp/status`
Get connection status and available tools per configured MCP server.
- **Response**:
  ```json
  {
    "enabled": true,
    "servers": [
      {
        "name": "prometheus",
        "connected": true,
        "transport": "http",
        "url": "http://10.0.0.1:8080/mcp",
        "tool_count": 6
      }
    ],
    "total_tools": 6
  }
  ```
- When `MCP_ENABLED=false`: `{"enabled": false, "servers": [], "total_tools": 0}`

### `GET /mcp/tools`
List all tools available from connected MCP servers.
- **Response**:
  ```json
  {
    "tools": [
      {
        "name": "mcp_prometheus_execute_query",
        "description": "[MCP:prometheus] Execute a PromQL query",
        "server": "prometheus",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
      }
    ],
    "count": 6
  }
  ```
- Tool names are prefixed with `mcp_{server_name}_` to avoid conflicts with built-in tools.

### `POST /mcp/reload`
Reload MCP server configuration from `resources/mcp_servers.json` and reconnect to all servers.
- **Response**: `{"status": "ok", "tools_loaded": 6}`
- When `MCP_ENABLED=false`: `{"status": "skipped", "reason": "MCP is disabled", "tools_loaded": 0}`
- **Status Codes**: `200` ok | `500` reload failed

### `POST /mcp/tools/{tool_name}/invoke`
Manually invoke an MCP tool for testing.
- **Path Parameters**: `tool_name` — full prefixed name (e.g. `mcp_prometheus_execute_query`)
- **Request Body**:
  ```json
  {"parameters": {"query": "up"}}
  ```
- **Response**:
  ```console
  {
    "tool": "mcp_prometheus_execute_query",
    "status": "success",
    "result": {...},
    "duration_ms": 45.3
  }
  ```
- **Status Codes**: `200` | `404` tool not found | `503` MCP disabled or server not connected

---

## Dashboard UI

### `GET /`
Serves the monitoring dashboard HTML.
- **Response**: `text/html`
