# Get Started

**Agentic Smart Community** is an AI Agent-native video analysis platform built around the Model Context Protocol (MCP). This guide installs the MCP server and its dependent services, then connects an agent host. You can then register a custom use case to tailor the video-analysis workflow to your camera-monitoring requirements.

For the validated use cases, e.g., Fridge Monitor, Child Safety, and Elder Wakeup reference demo, including user-provided video setup, see [Ready-to-Run Demo](./get-started/ready-to-run-demo.md).

## Prerequisites

Before you begin, ensure the following:

- **System Requirements:** Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- **GPU Driver Installed:** This guide assumes that the target machine already has the Intel GPU driver. Otherwise, follow the official [Installing Packages from the Intel PPA](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html) guide.
- **Docker Installed:** Install Docker by following [Get Docker](https://docs.docker.com/get-docker/).
- **Required command-line tools:** Install Node.js `>=22.22.3 <23` (the commands below use the supported 22.x line) and npm to build the MCP server and run OpenClaw 2026.7.1. Node.js `>=24.15.0 <25` and `>=25.9.0` are also supported. Install Python 3 with virtual-environment support for the demo launcher, `curl`, `wget`, `git`, and `jq` for service setup, `ffmpeg` and `ffprobe` for video processing, and MediaMTX for local RTSP streaming:

  ```bash
  sudo apt-get update
  sudo apt-get install -y curl wget git jq ffmpeg python3 python3-venv python3-pip

  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs

  mkdir -p "$HOME/.npm-global" "$HOME/.local/bin"
  npm config set prefix "$HOME/.npm-global"
  export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
  grep -qxF 'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"' "$HOME/.bashrc" || \
    echo 'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

  curl -fL --retry 3 \
    https://github.com/bluenviron/mediamtx/releases/download/v1.12.2/mediamtx_v1.12.2_linux_amd64.tar.gz \
    | tar xz -C "$HOME/.local/bin" mediamtx
  ```

This guide assumes basic familiarity with Docker commands and terminal usage. For an introduction, see the [Docker Documentation](https://docs.docker.com/).

### Memory and swap requirements

`Qwen/Qwen3.6-35B-A3B` in FP8 with a 60k context window is memory-intensive on a shared-RAM host. The default configuration targets a **64 GB system**:

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
> - If the YOLO11s OpenVINO IR is missing, `setup_docker.sh` automatically downloads the model and converts it before starting `videostream-analytics`.

Confirm the model serving is ready before continuing:

```bash
curl -fsS http://localhost:41091/v1/models
curl -fsS http://localhost:8192/v1/health
curl -fsS http://localhost:8999/health
```

### Step 2 - Start the MCP server

For the first run, create the runtime data directory and copy the configuration template into it:

```bash
export SMARTBUILDING_DATA_DIR="${SMARTBUILDING_DATA_DIR:-$HOME/.mcp-smartbuilding}"
mkdir -p "$SMARTBUILDING_DATA_DIR"
cp config.yaml.example "$SMARTBUILDING_DATA_DIR/config.yaml"

# Optional: start with an existing monitor configuration.
# cp <your-monitors.yaml> "$SMARTBUILDING_DATA_DIR/monitors.yaml"
```

Customize `$SMARTBUILDING_DATA_DIR/config.yaml` as needed, then start the server:

```bash
bash scripts/mcp-server/start.sh
```

The server always uses `$SMARTBUILDING_DATA_DIR/config.yaml` and `$SMARTBUILDING_DATA_DIR/monitors.yaml`. If `monitors.yaml` does not exist on the first run, the launcher creates an empty one. For later configuration changes, update these two files and restart the server.

The server runs as a host process and exposes:

```text
UI:     http://localhost:3100/
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
ls ~/.mcp-smartbuilding/config.yaml ~/.mcp-smartbuilding/monitors.yaml
```

> Use `bash scripts/mcp-server/stop.sh` to stop the MCP server.

### Step 3 - Connect an agent host

The MCP server is framework-agnostic. Once configured, a compatible MCP client can access the full `smartbuilding_*` tool set through Streamable HTTP at `http://localhost:3100/mcp`.

**Agentic Smart Community WebUI**
Open `http://localhost:3100/` to use the Agentic Smart Community Web UI. It provides live camera views, activity timelines, alert records, and report generation for registered monitors. The chat panel can also connect to a supported agent framework.


![Agentic Smart Community WebUI](_assets/agentic-smart-community-webui.png)
**Figure: Agentic Smart Community WebUI**

#### OpenClaw

1. Install OpenClaw using the official [OpenClaw documentation](https://openclaw.ai/), or use [our validated platform guide](../../scripts/openclaw/README.md).

2. Ensure that OpenClaw has a valid model provider configured, such as MiniMax, Kimi, DeepSeek, etc. Alternatively, run the following script to add the model served by `vllm-ipex-serving` from [Step 1 - Start dependent services](#step-1---start-dependent-services), into `~/.openclaw/openclaw.json`:

    ```bash
    bash scripts/openclaw/configure_local_model.sh
    ```

3. Add the MCP server to `~/.openclaw/openclaw.json`. The transport must be `streamable-http`, and the URL must include `/mcp`:

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

4. Import the skills and restart the gateway:

   ```bash
   mkdir -p ~/.openclaw/skills
   cp -rf ~/edge-ai-suites/metro-ai-suite/agentic-smart-community/skills/* ~/.openclaw/skills/
   openclaw gateway restart
   ```

5. Open the OpenClaw controUI to talk to your agents.
    ```bash
    openclaw dashboard
    # Then open:
    # http://localhost:18789/
    ```
    >
    > - If no GUI on your host. Open from your computer: `ssh -N -L 18789:127.0.0.1:18789 username@your-host-ip`
    > - Find the gateway token from `~/.openclaw/openclaw.json`

Agents can now use the MCP tools when you ask them to create a use case, analyze a monitor, or generate a report. Try the following examples in the OpenClaw Control UI (http://localhost:18789).

To use OpenClaw from the Agentic Smart Community Web UI, open `http://localhost:3100/`, select **OpenClaw** in the chat panel (as the figure shows below), and enter the gateway URL and token. After connecting, select an OpenClaw session to chat alongside the live video and activity views. You can alternatively use the standalone OpenClaw Control UI at `http://localhost:18789/`.


![Configure the Agent Chat Session from WebUI](_assets/configure-openclaw-session-from-webui.png)
**Figure: Configure the Agent Chat Session from WebUI**

**A. Inspect the Smart Building tools**

Ask the agent what capabilities and bundled use cases are available:

```text
"List the available Smart Building tools."
```

```text
"List the current Smart Building use cases."
```

**B. Register a camera-source monitor**

1. Prepare a valid RTSP video stream as a camera monitor source

You can publish a local video as a looping RTSP stream. Keep this command running while the monitor is in use:

  ```bash
  bash scripts/helpers/local_video_to_rtsp.sh /path/to/your-video.mp4
  ```

  The stream is available at `rtsp://localhost:8555/live`.

2. Ask the agent to register the stream with a bundled use case:

  ```text
  "Register a camera source at rtsp://localhost:8555/live using the child_safety use case."
  ```

  When no monitor ID is specified, the MCP server assigns `cam_child_safety`. You can also provide a monitor ID explicitly.

**C. Generate a report**

Leave the monitor online long enough to process video and store events in `~/.mcp-smartbuilding/smartbuilding.db`. Then ask the agent:

```text
"Generate today's report for the cam_child_safety monitor."
```

**MCP resource subscriptions** deliver alert-update notifications directly to the connected client; see [MCP Subscription Reference](./get-started/api-reference-mcp-subscription.md). This OpenClaw adapter is built with the [Framework Adapter SDK](../../packages/framework-adapter-sdk/README.md). For details about building the plugin and configuring alert routes, see the [OpenClaw adapter guide](../../packages/framework-adapter-sdk/examples/openclaw/README.md).

#### Other MCP clients

Hermes, Claude Desktop, Cursor, and other compatible MCP clients can similarly use the same `http://localhost:3100/mcp` endpoint through their own MCP-server configuration. The client can use the server reactively without an adapter, or subscribe to monitor alert updates as described in [MCP Subscription Reference](./get-started/api-reference-mcp-subscription.md). 

If your agent framework requires an adapter to route those updates into agent sessions or external channels, use the [Framework Adapter SDK](../../packages/framework-adapter-sdk/README.md).

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
|- config.yaml
|- config.yaml.<YYYYMMDD-HHMMSS>.bak
|- monitors.yaml
|- monitors.yaml.<YYYYMMDD-HHMMSS>.bak
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

The timestamped backup entries are present only after the launcher replaces a different active configuration. `config.yaml` and `monitors.yaml` are not removed by automatic data cleanup.

Automatic cleanup runs on server start and then daily at approximately 00:05 local time. It removes `.log` files older than `logging.retention_days` (14 days in `config.yaml.example`) and date directories under `segments/<id>/{recordings,motion_events,queries}/` older than `storage.retention_days` (2 days in `config.yaml.example`). It leaves `latest.jpg`, `smartbuilding.db`, and non-date directory names untouched.

## Supporting resources

- [Overview](./index.md)
- [API Reference](./api-reference.md)
- [System Requirements](./get-started/system-requirements.md)
- [Ready-to-Run Demo](./get-started/ready-to-run-demo.md)