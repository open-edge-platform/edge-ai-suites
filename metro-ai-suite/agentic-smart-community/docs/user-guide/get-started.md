# Get Started

**Agentic Smart Community** is an AI Agent-native video analysis platform built around the Model Context Protocol (MCP). This guide brings up the **framework-agnostic core** — the piece that any MCP host (OpenClaw, Claude Desktop, Hermes, …) talks to. It provides step-by-step instructions to:

- Set up an on-device GenAI model serving (VLM + LLM) that exposes an OpenAI-compatible API.
- Start the three core services and the MCP server using pre-built Docker images / host scripts.
- Push the bundled demo videos as RTSP streams so the three demo monitors (fridge / child / elder) start running.
- Learn where to modify basic configuration to suit specific requirements.

Once you finish this guide the MCP server is up, and the demo monitors are processing video.

To integrate with OpenClaw, continue with an **agent-host adapter** — see [Next steps](#next-steps--connect-an-agent-host).

## Prerequisites

Before you begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- **GPU Driver Installed**: This guide assumes the GPU driver on the target machine is already installed. If it is not, install the Intel GPU driver packages by following the official [Installing Packages from the Intel PPA](https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html) guide first.
- **Docker Installed**: Install Docker. For installation instructions, see [Get Docker](https://docs.docker.com/get-docker/).
- **ffmpeg / ffprobe**: needed to push and verify the demo RTSP streams (`sudo apt install ffmpeg`).

This guide assumes basic familiarity with Docker commands and terminal usage. If you are new to Docker, see [Docker Documentation](https://docs.docker.com/) for an introduction.

### Memory & swap requirements

`Qwen3.5-35B-A3B` in FP8 with a 60k context window is memory-hungry on a shared-RAM host. The default configuration targets a **64 GB system**:

- Provide at least **32 GB of swap** so the weight load and KV cache can spill under peak pressure without the OOM killer stepping in. If your host lacks enough swap, see guidelines in: [Adding Swap Space](./get-started/add-swap.md).
- To lower the footprint, reduce `MAX_MODEL_LEN` (e.g. `32768`) or switch `LOAD_QUANTIZATION` to `awq` / `sym_int4` in [set_env.sh](../../docker/set_env.sh).
- The **first startup takes 3–20 minutes** while the weights are downloaded and compiled. The serving becomes healthy once it answers on `http://<host>:41091/v1/models`.

## Step 1 — Start the three core services

The full on-device stack is defined in [docker/compose.yaml](../../docker/compose.yaml) and orchestrated by [setup_docker.sh](../../setup_docker.sh):

| Service | Port | Role |
|---|---|---|
| `vllm-ipex-serving` | `:41091` | on-device model serving (one Qwen3.5-35B-A3B fills both the VLM and LLM roles) |
| `multilevel-video-understanding` | `:8192` | video-segment summary microservice |
| `videostream-analytics` | host net | RTSP capture + NPU YOLO prefilter; POSTs events to the MCP webhook `:3101` |

```bash
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

## Step 2 — Prepare the demo video RTSP streams

The pipeline reads its cameras over RTSP. For the demo, the bundled clips are pushed to a local mediamtx RTSP server (one path per camera: `live/fridge`, `live/child`, `live/elder`):

```bash
cd demo-videos
bash start-streams.sh            # start every enabled stream
# bash start-streams.sh --status   # show running pushers
# bash start-streams.sh --stop     # stop them
```

Each enabled stream loops forever, so the demo keeps running. Edit [demo-videos/streams.yaml](../../demo-videos/streams.yaml) to change the input source: toggle `enabled` per camera, swap the `file`, or adjust the `rtsp_url` / mediamtx port. Verify a stream is live with:

```bash
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/child
```

This runs on the host in the background — continue in the same terminal.

## Step 3 — (Optional) Configure the MCP server

The MCP server reads two files: `config.yaml` (services, retention, use cases) and `monitors.yaml` (per-camera declarations). If you don't create them, the start script falls back to the tracked [config.yaml.example](../../config.yaml.example) / [monitors.yaml.example](../../monitors.yaml.example), which already declare the three demo monitors — so the demo runs out of the box.

To customize, copy the examples and edit your own copy (the `.example` files stay as a pristine reference):

```bash
cp config.yaml.example   config.yaml
cp monitors.yaml.example monitors.yaml
```

All runtime data (SQLite DB, video segments, logs) is stored under a single root directory, `~/.mcp-smartbuilding` by default. Override it with `export SMARTBUILDING_DATA_DIR=/path/to/data`.

## Step 4 — Start the MCP server

The MCP server runs as a **host** process (like OpenClaw) — Streamable-HTTP on `:3100` plus the events webhook on `:3101`. The first run builds the workspace automatically:

```bash
bash scripts/mcp-server/start.sh
# → MCP:    http://localhost:3100/mcp
# → events: http://localhost:3101/events
# → logs:   /tmp/smartbuilding-<uid>/mcp-server.log
```

> To stop the server, run `bash scripts/mcp-server/stop.sh`.

## Step 5 — Verify the monitors are running

At startup the MCP server auto-registers every `enabled: true` monitor and starts pulling its RTSP stream through `videostream-analytics`. Confirm it end to end:

- **Database** is created at `~/.mcp-smartbuilding/smartbuilding.db`; video segments and per-monitor logs appear under `~/.mcp-smartbuilding/segments/<monitor_id>/`.

At this point the core is fully live: three services + MCP server + three demo monitors processing video.

## Next steps — connect an agent host

The MCP server is host-agnostic, it is easily to integrate with a specific agent framework:

- **OpenClaw** — see [Adapter Example: Smart Community MCP × OpenClaw](../../packages/framework-adapter-sdk/examples/openclaw/README.md). It installs plain OpenClaw, wires model providers, registers this MCP server in `openclaw.json`, and installs the adapter plugin that routes each monitor's alerts into the matching agent session.

## Supporting Resources

- [Overview](./index.md)
- [API Reference](./api-reference.md)
- [System Requirements](./get-started/system-requirements.md)
