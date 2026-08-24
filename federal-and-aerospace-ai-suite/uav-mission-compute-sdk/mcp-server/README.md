<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# MCP Server — Edge AI Skills

MCP server exposing Intel Edge AI tools (Anomalib, DLStreamer, Edge AI Suites) and MAVLink telemetry to AI agents for UAV data analysis and applications.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager (auto-installed by setup.sh)

**Note**: uv may create a lightweight `.venv` directory for internal dependency management. This is automatic and transparent - you don't need to activate it.

## Quick Start

```bash
# Option 1: Full setup (installs uv, clones repos, configures MCP)
./setup.sh

# Option 2: Using Makefile (recommended for development)
make dev          # Install uv + dependencies
make verify       # Check tool discovery
make run          # Start server

# Option 3: Direct commands
uv pip install -e .
uv run server.py

# Use with Claude Code
cd /path/to/workspace
claude
```

**Custom workspace directory:**
```bash
./setup.sh /path/to/custom/workspace
```

## Available Tools

**Anomalib** (Anomaly Detection)
- `anomalib_train` - Train anomaly detection models
- `anomalib_predict` - Run inference on images
- `anomalib_export` - Export to OpenVINO/ONNX
- `anomalib_benchmark` - Benchmark model performance
- `anomalib_openvino_inference` - Run OpenVINO inference

**DLStreamer** (Video Analytics)
- `dlstreamer_build_pipeline` - Create video analytics pipelines
- `dlstreamer_run_sample` - Run sample applications
- `dlstreamer_list_samples` - List available samples
- `dlstreamer_download_models` - Download pre-trained models

**Edge AI Suites** (Manufacturing Apps)
- `edge_ai_suites_deploy_app` - Deploy production applications
- `edge_ai_suites_list_apps` - List available applications
- `edge_ai_suites_sdk_install` - Install SDK components

**MAVLink Telemetry** (UAV Data)
- `mavlink_get_telemetry` - Get all telemetry data
- `mavlink_get_position` - Get GPS position
- `mavlink_get_attitude` - Get orientation (roll/pitch/yaw)
- `mavlink_get_battery` - Get battery status
- `mavlink_get_velocity` - Get velocity vector
- `mavlink_get_status` - Get flight status
- `mavlink_check_health` - Health check
- `mavlink_monitor_flight` - Monitor flight in real-time
- `mavlink_collect_flight_data` - Collect flight data logs

## Usage Examples

```
# Anomaly detection on UAV imagery
"Train defect detector on aerial inspection images in ./data"

# Video analytics pipeline
"Build object tracking pipeline for UAV camera RTSP stream"

# Deploy application
"Deploy worker safety monitoring app"
```

## Architecture

```
mcp-server/
├── server.py           # MCP server entry point
├── setup.sh           # Setup script (uv-based, no venv)
├── pyproject.toml     # Dependencies and project config
├── providers/         # Tool implementations
│   ├── anomalib.py
│   ├── dlstreamer.py
│   ├── edge_ai_suites.py
│   └── telemetry/     # MAVLink telemetry tools
└── tool_configs/      # YAML tool definitions
```

Setup creates in workspace directory:
```
$WORKSPACE_DIR/
├── .mcp.json          # Claude Code MCP config (uses uv run)
├── anomalib/          # Cloned repo
├── dlstreamer/        # Cloned repo
└── edge-ai-suites/    # Cloned repo
```

## Deployment

**Development Setup:**
```bash
cd mcp-server
./setup.sh $(pwd)/..
```

**Production Setup:**
```bash
# Install in custom location
export WORKSPACE_DIR=/opt/UAV-workspace
cd mcp-server
./setup.sh $WORKSPACE_DIR

# Server runs via: uv --directory /path/to/mcp-server run server.py
# Dependencies managed by uv (no venv needed)
```

**Docker Deployment:**
```dockerfile
FROM python:3.11-slim
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app
COPY mcp-server/ ./mcp-server/
RUN cd mcp-server && uv pip install -e .
CMD ["uv", "--directory", "mcp-server", "run", "server.py"]
```

**Migration Note:** This project uses `uv` instead of `venv` for dependency management. The setup script automatically installs `uv` if not present. Dependencies are declared in `pyproject.toml` (not `requirements.txt`).
