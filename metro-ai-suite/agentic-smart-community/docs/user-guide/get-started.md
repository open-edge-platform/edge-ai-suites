# Get Started

**Agentic Smart Community** is an AI Agent-native video analysis platform built around the Model Context Protocol (MCP). This guide installs the MCP server and its dependent services, then connects an agent host. You can then register a custom use case to tailor the video-analysis workflow to your camera-monitoring requirements.

For the validated use cases, e.g., Fridge Monitor, Child Safety, and Elder Wakeup reference demo, including user-provided video setup, see [Ready-to-Run Demo](./get-started/ready-to-run-demo.md).

## Prerequisites

Before you begin, ensure the following:

- **System Requirements:** Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- **GPU Driver Installed:** This guide assumes that the target machine already has the Intel GPU driver. Otherwise, follow the official [Installing Packages from the Intel PPA](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html) guide.
- **Docker Installed:** Install Docker by following [Get Docker](https://docs.docker.com/get-docker/).
- **Node.js and npm:** Required to install and build the MCP server workspace.
- **curl and jq:** Required by the MCP server launcher to check services and register bundled use cases. On Ubuntu or Debian, run `sudo apt install curl jq`.
- **ffmpeg / ffprobe:** Required for video-frame processing and stream diagnostics. On Ubuntu or Debian, run `sudo apt install ffmpeg`.

This guide assumes basic familiarity with Docker commands and terminal usage. For an introduction, see the [Docker Documentation](https://docs.docker.com/).

### Memory and swap requirements

`Qwen3.6-35B-A3B` in FP8 with a 60k context window is memory-intensive on a shared-RAM host. The default configuration targets a **64 GB system**:

- Provide at least **32 GB of swap** so weight loading and the KV cache can spill under peak pressure without triggering the OOM killer. See [Adding Swap Space](./get-started/add-swap.md).
- The **first startup takes 3-20 minutes** while weights download and compile. The serving is ready when `http://<host>:41091/v1/models` responds.

## Step-by-step installation

Clone the repository and change to `agentic-smart-community`:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites ~/edge-ai-suites -b main
cd ~/edge-ai-suites/metro-ai-suite/agentic-smart-community
```

### Step 1 - Start dependent services

The on-device stack is defined in [docker/compose.yaml](../../docker/compose.yaml) and managed by [setup_docker.sh](../../setup_docker.sh):

| Service | Port | Role |
|---|---|---|
| `vllm-ipex-serving` | `:41091` | On-device model serving for VLM and LLM requests |
| `multilevel-video-understanding` | `:8192` | Video-summary microservice |
| `videostream-analytics` | host network | Video capture and optional detector-as-prefilter; posts events to the MCP webhook |

```bash
source docker/set_env.sh

# First time only: build the two local images.
bash setup_docker.sh --build

# Start the on-device services.
bash setup_docker.sh
```

> - Use `bash setup_docker.sh --light` to reuse an already warm serving and start only `multilevel-video-understanding` and `videostream-analytics`.
> - Use `bash setup_docker.sh --down` to stop all three services.

Confirm the model serving is ready before continuing:

```bash
curl -fsS http://localhost:41091/v1/models
curl -fsS http://localhost:8192/v1/health
curl -fsS http://localhost:8999/health
```

### Step 2 - Start the MCP server

Start the MCP server:

```bash
cp config.yaml.example config.yaml
```

Customize `config.yaml` as needed for your deployment, then start the server:

```bash
bash scripts/mcp-server/start.sh config.yaml
```
The server runs as a host process and exposes:

```text
MCP:    http://localhost:3100/mcp
Events: http://localhost:3101/events
Logs:   /tmp/smartbuilding-<uid>/mcp-server.log
```

Verify that the MCP endpoint, events webhook, and data root are available:

```bash
curl -fsS -X POST http://localhost:3100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"startup-check","version":"1.0"}}}'
curl -fsS http://localhost:3101/health
ls ~/.mcp-smartbuilding/smartbuilding.db
```

> Use `bash scripts/mcp-server/stop.sh` to stop the MCP server.

### Step 3 - Connect an agent host

The MCP server is framework-agnostic. Once configured, a compatible MCP client can access the full `smartbuilding_*` tool set through Streamable HTTP at `http://localhost:3100/mcp`.

#### OpenClaw

1. Install OpenClaw using the official [OpenClaw documentation](https://openclaw.ai/), or use [the validated platform guide](../../scripts/openclaw/README.md).

2. Add the MCP server to `openclaw.json`. The transport must be `streamable-http`, and the URL must include `/mcp`:

   ```json
   {
     "mcp": {
       "servers": {
         "smart-building": {
           "transport": "streamable-http",
           "url": "http://localhost:3100/mcp"
         }
       }
     }
   }
   ```

3. Import the skills and restart the gateway:

   ```bash
   mkdir -p ~/.openclaw/skills
   cp -rf ~/edge-ai-suites/metro-ai-suite/agentic-smart-community/skills/* ~/.openclaw/skills/
   openclaw gateway restart
   ```

OpenClaw can now use the MCP tools when you ask it to create a use case, analyze a monitor, or generate a report.

**MCP resource subscriptions** deliver alert-update notifications directly to the connected client; see [MCP Subscription Reference](./get-started/mcp-subscription-reference.md). To proactively route those updates into an OpenClaw agent session or its external user channel, configure the optional [Smart Community MCP x OpenClaw adapter](../../packages/framework-adapter-sdk/examples/openclaw/README.md).

#### Other MCP clients

Hermes, Claude Desktop, Cursor, and other compatible clients use the same `http://localhost:3100/mcp` endpoint through their own MCP-server configuration. The client can use the server reactively without an adapter, or subscribe to monitor alert updates as described in [MCP Subscription Reference](./get-started/mcp-subscription-reference.md).

### Step 4 - Register a new use case

The MCP server includes these bundled use cases:

| Use case | Capability |
|---|---|
| Fridge Monitor | Tracks fridge activity and supports inventory-oriented daily reports. |
| Child Safety | Detects potentially dangerous child behavior and creates safety alerts and reports. |
| Elder Wakeup | Tracks wakeup activity and supports weekly wakeup reports. |

To use a bundled use case, ask the connected agent to register a monitor with its monitor ID, RTSP URL, and use-case key: `fridge`, `child_safety`, or `elder_wakeup`.

Now, you can simply describe your requirements to an agent to create a customized use case without restarting the core services. See [Register a New Use Case](./get-started/register-new-use-case.md) for the complete registration workflow.

## Data directory

All runtime data lives under one root controlled by an environment variable:

```bash
export SMARTBUILDING_DATA_DIR=/path/to/data   # default: ~/.mcp-smartbuilding
```

```text
$SMARTBUILDING_DATA_DIR/
|- smartbuilding.db
|- segments/
|  `- <monitor_id>/
|     |- latest.jpg
|     |- recordings/<YYYY-MM-DD>/
|     |- motion_events/<YYYY-MM-DD>/
|     `- queries/<YYYY-MM-DD>/
`- logs/
   |- reports/
   `- monitors/<monitor_id>/<YYYY-MM-DD>.log
```

Automatic cleanup runs on server start and every 24 hours. It removes `.log` files older than `logging.retention_days` (default 14) and date directories under `segments/<id>/{recordings,motion_events,queries}/` older than `storage.retention_days` (default 7). It leaves `latest.jpg`, `smartbuilding.db`, and non-date directory names untouched.

## Supporting resources

- [Overview](./index.md)
- [API Reference](./api-reference.md)
- [System Requirements](./get-started/system-requirements.md)
- [Ready-to-Run Demo](./get-started/ready-to-run-demo.md)