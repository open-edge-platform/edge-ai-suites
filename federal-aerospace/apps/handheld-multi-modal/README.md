<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# Handheld Multi-Modal Application

The Handheld Multi-Modal application is a full-stack AI inference and observability platform for handheld scenarios, optimized for Intel® edge hardware.

The application combines LLM inference capability served through the OpenVINO™ Model Server platform, speech-to-text transcription through the Whisper service, a chat UI through the Open WebUI software, and metrics information through the Grafana dashboard; it runs with the [Visual Pipeline and Platform Evaluation Tool](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/tools/visual-pipeline-and-platform-evaluation-tool) for pipeline visualization, sharing its Docker network.

## Project Structure

```
docker-compose.yml            Defines and runs all services in the application using the standard GPU configuration.
docker-compose-cdi.yml        Container Device Interface (CDI) and Single Root I/O Virtualization (SR-IOV) variant.
docker-compose-standalone.yml Development or test. No Visual Pipeline and Platform Evaluation Tool required.
Makefile                      Operational and packaging targets.
AGENTS.md                     AI agent context file.
collector/                    Telegraf configuration for Visual Pipeline and Platform Evaluation Tool metrics-manager.
apps/
  LLM-OpenWebUI/              OpenVINO model server and Open WebUI chat interface.
  speech-to-text/             Whisper speech-to-text service.
  grafana/provisioning/       Pre-provisioned Grafana dashboards.
  nginx/                      HTTPS reverse proxy (self-signed cert, enables browser microphone).
```

## Stack

| Service | Image | Role |
|---------|-------|------|
| `grafana` | `grafana/grafana:latest` | Dashboards — consumes metrics via Grafana Live |
| `ovms` | `openvino/model_server:latest-gpu` | LLM inference via OpenAI-compatible REST API |
| `open-webui` | `ghcr.io/open-webui/open-webui:v0.9.6-slim` | Chat UI connected to OpenVINO model server |
| `whisper-stt` | `whisper-stt:latest` (local build) | Speech-to-text with Prometheus metrics |
| `nginx-https` | `nginx:alpine` | HTTPS reverse proxy (self-signed cert, enables browser microphone) |

All services share the `fedaero` Docker network and are defined in [`docker-compose.yml`](docker-compose.yml).

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker Engine release 24 or later| [Install guide](https://docs.docker.com/engine/install/) |
| Docker Compose v2 | Included with Docker Desktop; on Linux OS, install the `docker-compose-plugin` package. Use `docker compose` (space), not `docker-compose` (hyphen). |
| `render` group | Required for GPU access by OpenVINO model server. Verify with `getent group render`. |
| Git | Required for `make vippet-get` to do sparse-checkout of Visual Pipeline and Platform Evaluation Tool. |
| Intel® GPU with OpenVINO driver | iGPU or discrete GPU based on the Xe architecture. |
| **CDI only:** CDI drivers configured | Set `CDI_XE_DEVICE_0` in `.env` (see `AGENTS.md` for all env vars). |

Run `make setup` after cloning to auto-detect the `render` group GID and write the `.env`.

## Quick Start

> **Recommended — use `make deploy`.**
> This stack requires the Visual Pipeline and Platform Evaluation Tool to be running first because the tool will create the `fedaero` Docker network. Running `docker compose up -d` first **will fail** with:
> ```
> network visual-pipeline-and-platform-evaluation-tool_default declared as external, but could not be found
> ```
> `make deploy` handles everything — it fetches Visual Pipeline and Platform Evaluation Tool, starts it, waits for the network, then brings up this stack.

```bash
cd apps/handheld-multi-modal
make deploy        # standard GPU
make deploy-cdi    # CDI / SR-IOV environments
```

**Development or testing without Visual Pipeline and Platform Evaluation Tool** — a standalone variant creates its own isolated `fedaero` network. Metrics from Visual Pipeline and Platform Evaluation Tool pipelines will not be available.

```bash
make up-standalone
```

## Endpoints

Open WebUI, Grafana dashboard, and Whisper speech-to-text service are only accessible via the NGINX Transport Layer Security (TLS) reverse proxy — their container ports are not exposed directly to the host.

| Service                                         | URL                             | Notes                                                                 |
|-------------------------------------------------|---------------------------------|-----------------------------------------------------------------------|
| Single pane page                                | https://localhost:443           | via NGINX reverse proxy                                               |
| Visual Pipeline and Platform Evaluation Tool UI | https://localhost:1443          | via NGINX reverse proxy                                               |
| Whisper speech-to-text service                  | https://localhost:5443          | Speech-to-text — browser microphone enabled (via NGINX reverse proxy) |
| OVMS metrics                                    | https://localhost:6443/metrics  | Prometheus metrics (via NGINX reverse proxy)                          |
| Grafana dashboard                               | https://localhost:7443          | Pre-provisioned dashboards (via NGINX reverse proxy)                  |
| Open WebUI                                      | https://localhost:8443          | LLM chat UI — browser microphone enabled (via NGINX reverse proxy)    |

## Make Targets

```
make deploy           # full one-shot deployment: sets runtime environment variables for the stack, tailors Visual Pipeline and Platform Evaluation Tool installation (metrics-manager and supported models) and brings up the stack components in the correct order
make deploy-cdi        The same for CDI and SR-IOV environments
make up                Start this stack (standard, requires Visual Pipeline and Platform Evaluation Tool network)
make up-cdi            Start this stack (CDI, requires Visual Pipeline and Platform Evaluation Tool network)
make up-standalone     Start this stack without Visual Pipeline and Platform Evaluation Tool (development or testing only)
make down              Stop all services
make build             Build local images
make restart           Restart all services
make urls              Print all service endpoints
make test              Check service connectivity
make health            Show service health or status
make clean CONFIRM=yes Stop containers and remove all data directories
```

## Component README Files

- [LLM: OpenVINO model server and Open WebUI chat interface](apps/LLM-OpenWebUI/README.md)
- [Speech-to-Text feature: Whisper speech-to-text service](apps/speech-to-text/README.md)
