# Get Started

**Agentic Smart Community** is an AI Agent-native video analysis platform built around the Model Context Protocol (MCP). Follow this guide step by step and you will bring up the three **validated example** monitors — Fridge, Child Safety, and Elder Wakeup — end to end: on-device model serving, the core services, demo RTSP streams, and the MCP server.

The platform itself is **use-case-agnostic** — the examples are just a starting point. Once the demo is running you will learn how to connect your own agent framework with zero code, how to drive the platform by chatting with an agent, and how to run a clean server with no use cases at all and add your own by conversation (see [Run a clean, use-case-free server](#run-a-clean-use-case-free-server)).

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- **GPU Driver Installed**: This guide assumes the GPU driver on the target machine is already installed. If it is not, install the Intel GPU driver packages by following the official [Installing Packages from the Intel PPA](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html) guide first.
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).
- **ffmpeg / ffprobe**: needed to push and verify the demo RTSP streams (`sudo apt install ffmpeg`).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

### Memory & swap requirements

`Qwen3.6-35B-A3B` in FP8 with a 60k context window is memory-hungry on a shared-RAM host. The default configuration targets a **64 GB system**:

- Provide at least **32 GB of swap** so the weight load and KV cache can spill under peak pressure without the OOM killer stepping in. If your host lacks enough swap, see guidelines in: [Adding Swap Space](./get-started/add-swap.md).
- To lower the footprint, reduce `MAX_MODEL_LEN` (e.g. `32768`) or switch `LOAD_QUANTIZATION` to `awq` / `sym_int4` in [set_env.sh](../../docker/set_env.sh).
- The **first startup takes 3–20 minutes** while the weights are downloaded and compiled. The serving becomes healthy once it answers on `http://<host>:41091/v1/models`.

## Step-by-step Installation

Clone the repository and change directory to `agentic-smart-community`:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites ~/edge-ai-suites -b main
cd ~/edge-ai-suites/metro-ai-suite/agentic-smart-community
```

### Step 1 — Start the dependent external services

The full on-device stack is defined in [docker/compose.yaml](../../docker/compose.yaml) and orchestrated by [setup_docker.sh](../../setup_docker.sh):

| Service | Port | Role |
|---|---|---|
| `vllm-ipex-serving` | `:41091` | on-device model serving (one Qwen3.6-35B-A3B fills both the VLM and LLM roles) |
| `multilevel-video-understanding` | `:8192` | video summary microservice |
| `videostream-analytics` | host net | RTSP capture + NPU YOLO prefilter; POSTs events to the MCP webhook `:3101` |

```bash
cd ~/edge-ai-suites/metro-ai-suite/agentic-smart-community
source docker/set_env.sh   # deployment env (model, ports, group ids, data dir); the script also sources it itself

# First time only — build the two local images (multilevel + videostream-analytics):
bash setup_docker.sh --build

# Start all three services:
bash setup_docker.sh
```

> - Use `bash setup_docker.sh --light` to reuse an already-warm serving and start only `multilevel-video-understanding` + `videostream-analytics`.
> - Use `bash setup_docker.sh --down` to tear down.

The first run pulls and compiles the model in `vllm-ipex-serving` (3–20+ min). Confirm the serving is healthy before continuing:

```bash
curl -s http://localhost:41091/v1/models   # returns the model "id" once ready
```

### Step 2 — Start the demo (streams + MCP server)

A single command pushes the bundled demo clips as RTSP streams and then starts the MCP server against the demo bundle — [demo/config.demo.yaml](../../demo/config.demo.yaml) (the three use cases) and [demo/monitors.demo.yaml](../../demo/monitors.demo.yaml) (the demo cameras):

```bash
cd ~/edge-ai-suites/metro-ai-suite/agentic-smart-community
bash demo/scripts/start-demo.sh
# → MCP:    http://localhost:3100/mcp     (Streamable-HTTP, for OpenClaw / Hermes / Claude Desktop …)
# → events: http://localhost:3101/events  (videostream-analytics posts pipeline events here)
# → logs:   /tmp/smartbuilding-<uid>/mcp-server.log
```

This pushes each demo clip to a local mediamtx RTSP server (one path per camera: `live/fridge`, `live/child`, `live/elder`), then starts the MCP server as a **host** process (like OpenClaw) which auto-registers every `enabled: true` monitor. To stop everything (server + streams) in one shot:

```bash
cd ~/edge-ai-suites/metro-ai-suite/agentic-smart-community
bash demo/scripts/stop-demo.sh
```

> - Each demo stream loops forever, so the demo keeps running. Edit [demo/videos/streams.yaml](../../demo/videos/streams.yaml) to change the input source: toggle `enabled` per camera, swap the `file`, or adjust the `rtsp_url` / mediamtx port.
> - Verify a stream is live with `ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/child`.
> - All runtime data (SQLite DB, video segments, logs) is stored under a single root directory, `~/.mcp-smartbuilding` by default. Override it with `export SMARTBUILDING_DATA_DIR=/path/to/data`.

### Step 3 — Verify the monitors are running

At startup the MCP server auto-registers every `enabled: true` monitor and starts pulling its RTSP stream through `videostream-analytics`. Confirm it end to end:

- The **database** is created at `~/.mcp-smartbuilding/smartbuilding.db`; video segments and per-monitor logs appear under `~/.mcp-smartbuilding/segments/<monitor_id>/`.
- Three demo monitors — `cam_fridge`, `cam_child`, `cam_elder_bedroom` — are online and processing video.

At this point the core is fully live: three services + MCP server + three demo monitors.

## Connect an agent host (zero-code)

The MCP server is host-agnostic. Any MCP client speaks **Streamable-HTTP** at `http://localhost:3100/mcp` — no adapter, no glue code. Point your framework at that endpoint and its agent immediately gains the `smartbuilding_*` tools.

### OpenClaw

**Step 1 — Install OpenClaw.**
Install a stock OpenClaw by following the official guide ([OpenClaw — Personal AI Assistant](https://openclaw.ai/)), or follow [our guide](../../scripts/openclaw/README.md) to install it on our validated platform (Ubuntu 24.04).

**Step 2 — Register the MCP server.**
Add this server to `openclaw.json`. The transport **must** be `streamable-http`, and the URL **must** include the `/mcp` path:

```json
{
  "mcp": {
    "servers": {
      "smart-community": {
        "transport": "streamable-http",
        "url": "http://localhost:3100/mcp"
      }
    }
  }
}
```

**Step 3 — Import skills.**

```bash
mkdir -p ~/.openclaw/skills
cp -rf ~/edge-ai-suites/metro-ai-suite/agentic-smart-community/skills/* ~/.openclaw/skills/

# Then restart the openclaw gateway to make skills effective
openclaw gateway restart
```

**Step 4 — Try the demo.**
Chat with the agents about your smart-community use cases. This covers **reactive** use — the agent calls a tool only when you ask. Some typical questions for the current demo can be found in [Talk to the agent](#talk-to-the-agent).

To experience the **full** OpenClaw-based demo, you'll add a lightweight framework-adapter that enables:

- **Proactive alerts** — each monitor's alerts are routed to its corresponding agent session (no need to ask first).
- **Multi-agent setup** — every monitor gets its own house-keeper-style agent.

Install the ready-to-use adapter plugin by following [Adapter Example: Smart Community MCP × OpenClaw](../../packages/framework-adapter-sdk/examples/openclaw/README.md).

### Hermes (TODO)

Add the server to `~/.hermes/config.yaml` using its Streamable-HTTP transport pointing at the same endpoint:

```yaml
mcp_servers:
  smart-community:
    transport: streamable-http
    url: http://localhost:3100/mcp
```

> Field names follow your Hermes version's MCP-server config schema; use the Streamable-HTTP transport (older builds may expose it as stdio / SSE). The server URL is always `http://localhost:3100/mcp`.

### Other MCP clients

Any other MCP client (Claude Desktop, Cursor, VS Code, …) connects to the same `http://localhost:3100/mcp` endpoint through its own MCP-server config file. The server is identical across hosts — only the config file location and field names differ. This gives you **reactive** use out of the box: the agent calls a `smartbuilding_*` tool whenever you ask.

For **proactive** push, each monitor's alerts are a subscribable resource (`smartbuilding://monitor/<monitor_id>/alerts`). Implement the standard [MCP resource-subscription](https://modelcontextprotocol.io/specification/2025-06-18/server/resources) flow, then deliver each alert into an agent session:

1. `resources/subscribe` to the monitor's alert URI.
2. On each `notifications/resources/updated`, `resources/read` with `?since=<lastId>` to pull the delta and advance the cursor.
3. Inject the new alert into the target agent session.

## Talk to the agent

Once connected, you drive the whole platform in natural language — the agent picks the right `smartbuilding_*` tool for you:

- *[smart-community] I'm working out lately — based on what's currently in my fridge, what should I buy?*
- *[smart-community] Any child-safety alerts today? Generate a daily report and send it to me.*
- *[smart-community] What about the elder's bedroom today?*
- *[smart-community] Generate daily reports for all online monitors and send them to me.*

> **Tip:** Prefix your message with `[smart-community]` so the agent knows to reach for the `smartbuilding_*` tools. Alternatively, tell it once at the start of the conversation, or save the guideline to its memory.


## Run a clean, use-case-free server

The demo above is one packaging of a platform that ships **zero** use cases by default. To start the pristine core instead:

```bash
bash scripts/mcp-server/start.sh
```

This boots from the tracked [config.yaml.example](../../config.yaml.example) (an empty `use_case_dict`) with **no** monitors — a clean, use-case-agnostic server. From there, add everything by chatting with a connected agent:
(TODO: update)

1. **Create a use case** — describe it in chat; the `video-summary-prompt-studio` skill infers the events/schema, drafts the prompt, and calls `smartbuilding_use_case_register`.
2. **Add a camera** — `smartbuilding_monitor_ctl register_source` (single monitor) or `smartbuilding_monitors_compose up` (a batch from a `monitors.yaml`).

No core-component changes, no restart — the server picks up the new use case and monitor at runtime. This is the intended production shape; the demo bundle simply pre-fills it with three validated examples.

## Data directory

All runtime data lives under one root, controlled by an env var:

```
export SMARTBUILDING_DATA_DIR=/path/to/data   # default: ~/.mcp-smartbuilding
```

```
$SMARTBUILDING_DATA_DIR/
├── smartbuilding.db                       — SQLite database
├── segments/
│   └── <monitor_id>/
│       ├── latest.jpg                     — latest frame (read by scene_query, overwritten each frame)
│       ├── recordings/<YYYY-MM-DD>/       — recorded clips (daily rotate; purged after storage.retention_days)
│       ├── motion_events/<YYYY-MM-DD>/    — motion-event frames (daily rotate; purged)
│       └── queries/<YYYY-MM-DD>/          — scene_query frame archive (daily rotate; purged)
└── logs/
    ├── reports/                           — generate_report SRT debug files
    └── monitors/<monitor_id>/<YYYY-MM-DD>.log
```

**Automatic cleanup** runs on server start and every 24h: `.log` files older than `logging.retention_days` (default 14) and `segments/<id>/{recordings,motion_events,queries}/` date dirs older than `storage.retention_days` (default 7) are removed. `latest.jpg`, `smartbuilding.db`, and non-date directory names are skipped.

## Supporting Resources

- [Overview](./index.md)
- [API Reference](./api-reference.md)
- [System Requirements](./get-started/system-requirements.md)
