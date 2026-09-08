<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# SDK Agent Commands and MCP Tools

The [UAV Mission Compute SDK](../../../../uav-mission-compute-sdk/README.md) ships two complementary interfaces
for AI agents:

1. **Slash commands** for Claude Code that wrap the most common stack lifecycle
   and validation workflows.
2. **An MCP server** that exposes Intel Edge AI tools (Anomalib, DLStreamer,
   Edge AI Suites) and live MAVLink telemetry to any MCP-capable agent.

Together they let you bring up the PX4 + Gazebo + OpenVINO stack, verify it,
capture data, and drive higher-level AI workflows — all through natural
language.

## Claude Code Slash Commands

The SDK repository provides ready-to-use slash commands under
[`.claude/commands/`](../../../../uav-mission-compute-sdk/.claude/commands).
Once the repository is opened with Claude Code from
`federal-and-aerospace-ai-suite/uav-mission-compute-sdk/`, the commands below
are auto-discovered and invocable as `/<command-name>`.

| Command | What it does | Typical usage |
|---|---|---|
| [`/start-stack`](../../../../uav-mission-compute-sdk/.claude/commands/start-stack.md) | Brings up the full UAV infrastructure (mosquitto, mediamtx, PX4, companion bridge, camera bridge, observability). Supports `sim` (default 3-camera Gazebo) and `usb` (single USB camera) modes, plus `-lean` variants that skip Grafana/InfluxDB. | `/start-stack sim` or `/start-stack usb` |
| [`/validate-infra`](../../../../uav-mission-compute-sdk/.claude/commands/validate-infra.md) | Runs a health sweep across the stack: container status, MQTT broker connectivity, PX4 SITL process, companion bridge, MediaMTX API, RTSP camera streams, and telemetry flow. Camera-profile aware (checks only the active bridge). | `/validate-infra` |
| [`/capture-camera`](../../../../uav-mission-compute-sdk/.claude/commands/capture-camera.md) | Captures a single frame (or short clip) from any UAV camera for debugging. Prefers RTSP (`rtsp://localhost:8554/uav-1/<camera>`) and falls back to MQTT legacy mode. Arms the UAV first if needed. | `/capture-camera nadir` |
| [`/switch-camera-mode`](../../../../uav-mission-compute-sdk/.claude/commands/switch-camera-mode.md) | Switches the running stack between simulated 3-camera mode (`nadir,forward,rear`) and real USB camera mode (`nadir`). Updates `.env`, tears down current profile, and brings up the target profile. | `/switch-camera-mode sim` or `/switch-camera-mode usb` |
| [`/cleanup-stack`](../../../../uav-mission-compute-sdk/.claude/commands/cleanup-stack.md) | Stops sample apps + helpers first, then core infra across both camera profiles, and runs `make clean`. Points at `make clean-all` for deeper cleanup (compose volumes + unused images). | `/cleanup-stack` |

### Typical Session

```text
/start-stack sim
/validate-infra
/capture-camera nadir
/switch-camera-mode usb
/cleanup-stack
```

Each command file is a self-contained runbook — the agent reads the file,
prompts for any missing arguments (for example the target camera), executes
the documented shell steps, and reports the outcome.

## MCP Server — Edge AI Skills

The SDK also includes a Model Context Protocol server at
[`uav-mission-compute-sdk/mcp-server/`](../../../../uav-mission-compute-sdk/mcp-server/README.md)
that exposes Intel Edge AI tooling and live MAVLink telemetry to any
MCP-capable agent (Claude Code, GitHub Copilot with MCP, etc.).

### Quick Start

From `uav-mission-compute-sdk/mcp-server/`:

```bash
# Full setup (installs uv, clones supporting repos, configures MCP)
./setup.sh

# Or, for iterative development
make dev          # Install uv + dependencies
make verify       # Check tool discovery
make run          # Start the server
```

Then launch Claude Code from the workspace directory and the tools below
become available. See the
[full MCP server README](../../../../uav-mission-compute-sdk/mcp-server/README.md)
for custom workspace paths, production deployment, and the Docker recipe.

### Exposed Tools

The server groups tools by domain. Each tool is invoked by the agent when its
description matches the user request.

#### Anomalib — Anomaly Detection

| Tool | Purpose |
|---|---|
| `anomalib_train` | Train anomaly detection models on a dataset |
| `anomalib_predict` | Run inference on images |
| `anomalib_export` | Export a trained model to OpenVINO / ONNX |
| `anomalib_benchmark` | Benchmark model performance |
| `anomalib_openvino_inference` | Run OpenVINO inference on exported models |

#### DLStreamer — Video Analytics

| Tool | Purpose |
|---|---|
| `dlstreamer_build_pipeline` | Compose a video analytics pipeline (detection, tracking, classification) |
| `dlstreamer_run_sample` | Run a bundled sample application |
| `dlstreamer_list_samples` | List available sample pipelines |
| `dlstreamer_download_models` | Download pre-trained models |

#### Edge AI Suites — Application Deployment

| Tool | Purpose |
|---|---|
| `edge_ai_suites_deploy_app` | Deploy a production Edge AI Suites application |
| `edge_ai_suites_list_apps` | List available applications across suites |
| `edge_ai_suites_sdk_install` | Install SDK components |

#### MAVLink — Live UAV Telemetry

| Tool | Purpose |
|---|---|
| `mavlink_get_telemetry` | Get the full telemetry snapshot |
| `mavlink_get_position` | Get GPS position |
| `mavlink_get_attitude` | Get orientation (roll / pitch / yaw) |
| `mavlink_get_battery` | Get battery status |
| `mavlink_get_velocity` | Get velocity vector |
| `mavlink_get_status` | Get flight status |
| `mavlink_check_health` | Health check against the vehicle |
| `mavlink_monitor_flight` | Monitor a flight in real time |
| `mavlink_collect_flight_data` | Collect flight data logs |

### Example Prompts

```text
Train a defect detector on aerial inspection images in ./data.
```

```text
Build an object tracking pipeline for the UAV nadir RTSP stream.
```

```text
Deploy the worker safety monitoring app.
```

```text
Monitor the current flight and alert me if battery drops below 20%.
```

## When to Use Which

- Use the **slash commands** for stack lifecycle work — starting, validating,
  capturing from, switching, and tearing down the local UAV simulation.
- Use the **MCP server tools** for higher-level AI workflows — training and
  exporting models, building analytics pipelines, deploying suite
  applications, and querying live vehicle telemetry.

Both can be used together in the same Claude Code session: bring the stack up
with `/start-stack sim`, then ask the agent to build a DLStreamer pipeline
against the running RTSP source.
