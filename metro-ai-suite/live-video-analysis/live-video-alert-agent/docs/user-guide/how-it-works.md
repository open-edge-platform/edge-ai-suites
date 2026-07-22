# How It Works

The Live Video Alert Agent is a multi-layered application that ingests RTSP
video streams, applies VLM-based scene understanding, and delegates configurable
action dispatch to the external alert-agent-service over HTTP.

## Architecture Overview

![System Architecture](./_assets/Architecture.png)

## Data Flow

```text
RTSP Sources (N cameras)
     │
     ▼
LiveStreamManager × N          grab()/retrieve() throttled decode
     │                         exponential-backoff reconnection
     │  frame (latest)
     ▼
AgentManager                   one asyncio.Task per stream (concurrent)
  ├─ VlmClient ──────────────► OVMS / OpenAI-compatible VLM
  │   └─ retry + backoff       Phi-3.5-Vision | InternVL2-2B ...
  │
  ├─ AlertStateManager         per-stream × per-alert runtime state
  │   ├─ cooldown gate         suppresses repeat firings
  │   ├─ consecutive counter   detects persistent conditions
  │   └─ escalation trigger    promotes alert tier after N consecutives
  │
  ├─ AlertServiceClient ─────► alert-agent-service (HTTP POST)
  │                             dispatches tools via ADK or rule-based mode
  │                             tools: log_alert, capture_snapshot,
  │                                    trigger_webhook, publish_mqtt, MCP tools
  │
  ├─ MCP Client (optional)     Model Context Protocol integration
  │   └─ External MCP servers  discover tools for status/monitoring
     │
     ▼
EventManager (SSE pub/sub)     alerts fan-out to all connected browsers
     │
     ▼
Dashboard UI                   real-time stream tiles, alert feed
```

## Key Components

### LiveStreamManager

Each registered camera has its own `LiveStreamManager` running in a daemon thread.

- Uses `cv2.VideoCapture.grab()` followed by `retrieve()` to skip deep-decode on
  unused frames, reducing CPU usage proportionally to the gap between capture FPS
  and analysis FPS.
- Frame interval is controlled by `CAPTURE_FPS` (default: auto-derived from
  `ANALYSIS_INTERVAL`).
- Reconnects on drop-out with exponential back-off (2 s → 30 s).
- Exposes a `get_health()` method returning connection status, actual FPS,
  resolution, and buffer fill level.

### AgentManager

The central orchestrator. Instead of a single serial loop across all cameras, each
stream gets an independent `asyncio.Task`:

```text
add_stream("cam1", ...) → _launch_stream_task("cam1")
add_stream("cam2", ...) → _launch_stream_task("cam2")

cam1-task: _stream_analysis_loop() running every ANALYSIS_INTERVAL seconds
cam2-task: _stream_analysis_loop() running every ANALYSIS_INTERVAL seconds
```

Failed or cancelled tasks are automatically restarted via an `add_done_callback`.

### VlmClient

Thin async wrapper around `openai.AsyncOpenAI`, targeting OVMS (OpenVINO Model
Server) via its OpenAI-compatible REST API.

- Sends a `system` role message (VLM system instruction) plus a `user` message
  containing the base64-encoded frame and the structured alert prompt.
- Retries failed calls up to `VLM_MAX_RETRIES` times with exponential back-off.
- Alert prompts are serialised with `json.dumps` — not f-strings — to prevent
  prompt-injection from user-supplied alert names or text.

### AlertStateManager

Maintains per-stream × per-alert runtime state without any database dependency:

| State field | Purpose |
|---|---|
| `last_action_time` | Timestamp of last tool execution |
| `consecutive_yes` | Counts unbroken YES detections; triggers escalation |
| `last_answer` | Detects state transitions (NO→YES, YES→NO) |

`process()` returns `(should_act, is_escalation, is_transition)` so the manager
can decide whether to invoke tools and which tier of tools to use.

### AlertServiceClient

`AlertServiceClient` is the live-video-alert-agent's async HTTP integration point for action dispatch.

- Reads `ALERT_AGENT_SERVICE_URL` (default:
  `http://alert-agent-service:8000/api/v1`) and
  `ALERT_AGENT_SERVICE_TIMEOUT` (default: 30 s).
- Sends alert context, selected tool names, per-tool arguments, metadata, and an
  optional JPEG-encoded frame to the alert-agent-service via HTTP POST.
- Keeps the video analysis service decoupled from Google ADK, local tool
  registries, webhook/MQTT implementations, and LLM endpoint management.
- Receives normalized execution results such as `actions_taken`,
  `duration_ms`, and `snapshot_path`, which are then published to the UI as
  alert events.

The alert-agent-service owns the ADK-powered and rule-based execution modes, so
the live-video-alert-agent no longer embeds an action agent locally.

### Action Tools

Action tools are no longer implemented inside the live-video-alert-agent
process. Instead, they are registered and executed by the external
alert-agent-service.

Typical tools provided by that service include:

- `log_alert`
- `capture_snapshot`
- `trigger_webhook`
- `publish_mqtt`
- MCP-backed tools exposed by the alert-agent-service

Tools are still referenced per alert through `AlertConfig.tools` and
`AlertConfig.escalation.additional_tools`, but the `/tools`,
`/tools/{name}/invoke`, and `/tools/reload` endpoints in the live-video-alert-agent
now proxy requests to the alert-agent-service.

### Alert Configuration Schema

Each alert is described by an `AlertConfig` Pydantic model:

```json
{
  "name": "Fire Detection",
  "prompt": "Is there fire or smoke visible?",
  "enabled": true,
  "tools": ["log_alert", "capture_snapshot"],
  "tool_arguments": {
    "trigger_webhook": {"stream_id": "{{stream_id}}", "severity": "{{severity}}"}
  },
  "escalation": {
    "threshold_consecutive": 3,
    "additional_tools": ["trigger_webhook", "publish_mqtt"]
  }
}
```

| Field | Values | Description |
|---|---|---|
| `tools` | list of tool names | Tools invoked when alert fires |
| `tool_arguments` | object | Per-tool keyword argument overrides; supports `{{variable}}` placeholders rendered from alert context (`stream_id`, `alert_name`, `answer`, `reason`, `consecutive_count`, `escalated`, `snapshot_path`) |
| `escalation.threshold_consecutive` | integer ≥ 2 | Consecutive YES count before escalation |
| `escalation.additional_tools` | list of tool names | Extra tools added on escalation |

## Event Types

The SSE stream (`GET /events`) emits four event types:

| Event | When |
|---|---|
| `init` | On SSE connect — current streams + latest results |
| `analysis` | Each VLM analysis cycle completes |
| `alert_action` | Alert fired and tools were invoked |
| `keepalive` | Every 15 s to prevent proxy timeouts |

## MCP Integration

The agent still supports connecting to external **Model Context Protocol (MCP)**
servers for status visibility and monitoring-oriented tool discovery.

### MCPClient

The `MCPClient` module manages lifecycle for one or more MCP servers configured in
`resources/mcp_servers.json`. Supported transports:

| Transport | When to use |
|---|---|
| `http` | Remote HTTP MCP server (MCP Streamable HTTP protocol) |
| `sse` | Remote SSE-based MCP server |
| `stdio` | Local subprocess MCP server |

At startup, if `MCP_ENABLED=true`, the agent:

1. Reads `resources/mcp_servers.json`
2. Connects to each enabled server and performs the MCP `initialize` handshake
3. Calls `tools/list` to discover available tools
4. Exposes the discovered tool inventory through local MCP status/inspection endpoints, while action-dispatch tool registration is handled by the alert-agent-service
5. Leaves ADK tool-calling and alert-time MCP dispatch to the alert-agent-service rather than reinitialising a local action agent
