# How It Works

The Live Video Alert Agent is a multi-layered agentic application that ingests RTSP
video streams, applies VLM-based scene understanding, and dispatches configurable
actions through an agentic tool-calling pipeline.

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
  ├─ AlertActionAgent          decides WHICH tools to call
  │   ├─ ADK mode              Google ADK LlmAgent + FunctionTool (default)
  │   ├─ LLM mode        OVMS-hosted text model endpoint
  │   └─ Rule-based mode       direct tool execution — no LLM needed
  │
  ├─ MCP Client (optional)     Model Context Protocol integration
  │   └─ External MCP servers  discover and invoke remote tools
  │
  └─ Action Tools (async)
      ├─ log_alert              structured logging
      ├─ capture_snapshot       JPEG frame to disk / named volume
      ├─ trigger_webhook        HMAC-signed HTTP POST
      └─ publish_mqtt           paho-mqtt 2.x MQTTv5 publish
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

### AlertActionAgent

Decides which tools to invoke for a fired alert. Operates in one of three modes,
selected automatically at startup:

#### Mode 1 — Google ADK (`USE_ADK=true`, default)

Uses Google's Agent Development Kit with a `LlmAgent` that receives
structured alert context and calls `FunctionTool`-wrapped async tool functions.
Best for dynamic, LLM-reasoned escalation logic that can be adjusted without code
changes. The LLM is served locally via OVMS (`ovms-llm` service) using an
OpenAI-compatible API endpoint.

#### Mode 2 — Local LLM (`USE_LOCAL_LLM=true`)

Connects to an OVMS-hosted OpenAI-compatible text endpoint. Two-tier execution:

1. **Tool-calling API** — sends `tools=` schemas; models that support
   function-calling (llama3.1+, Mistral, Phi-3, etc.) return `tool_calls` directly.
2. **JSON text fallback** — re-prompts asking for a JSON array of tool names;
   a regex+JSON parser extracts valid names from free-form text.

Requires: `LLM_URL` and `LLM_MODEL`.

#### Mode 3 — Rule-based (default)

Directly executes the tool list from `AlertConfig.tools` in order. No external LLM
required — works fully offline and air-gapped. Escalation tools from
`AlertConfig.escalation.additional_tools` are appended when the consecutive
threshold is reached.

### Action Tools

All four tools are async functions registered in `_TOOL_MAP`:

| Tool | Trigger condition | Configuration |
|---|---|---|
| `log_alert` | Always | Built-in, always active |
| `capture_snapshot` | Alert fires | `SNAPSHOT_DIR` writable |
| `trigger_webhook` | Alert fires | `WEBHOOK_URL` set |
| `publish_mqtt` | Alert fires | `MQTT_BROKER` set |

Tools are configured per-alert in `AlertConfig.tools` and are silently skipped
if their required env var is not set.

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

The agent supports connecting to external **Model Context Protocol (MCP)** servers, allowing
alerts to invoke tools hosted on remote services (e.g., Prometheus for metrics queries,
custom REST APIs, etc.).

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
4. Registers discovered tools with the `AlertActionAgent` under prefixed names (`mcp_{server_name}_{tool_name}`)
5. If ADK mode is active, reinitialises the agent so the new tools appear in the LLM's tool list

MCP tools can be referenced in `AlertConfig.tools` and `AlertConfig.escalation.additional_tools`
by their prefixed names, and are invocable via the `/mcp/tools/{tool_name}/invoke` API endpoint.
