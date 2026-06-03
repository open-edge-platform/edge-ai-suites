<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# Handheld Multi-Modal

Full-stack AI inference and observability platform for handheld deployment scenarios, optimized for Intel edge hardware.

Combines an LLM inference server, a speech-to-text service, a chat UI, and a metrics/dashboarding stack into a single composable solution. Designed to run alongside the [Visual Pipeline and Platform Evaluation Tool (vippet)](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/tools/visual-pipeline-and-platform-evaluation-tool), sharing its Docker network.

## Project Structure

```
docker-compose.yml            Root compose — all services (standard GPU)
docker-compose-cdi.yml        CDI / SR-IOV variant
docker-compose-standalone.yml Dev/test — no VIPPET required
Makefile                      Operational and packaging targets
AGENTS.md                     AI agent context file
collector/                    Telegraf config for VIPPET metrics-manager
apps/
  LLM-OpenWebUI/              OVMS model server + Open WebUI chat interface
  speech-to-text/             Whisper STT service
  grafana/provisioning/       Pre-provisioned Grafana dashboards
  nginx/                      HTTPS reverse proxy (self-signed cert, enables browser mic)
```

## Stack

| Service | Image | Role |
|---------|-------|------|
| `grafana` | `grafana/grafana:latest` | Dashboards — consumes metrics via Grafana Live |
| `ovms` | `openvino/model_server:latest-gpu` | LLM inference via OpenAI-compatible REST API |
| `open-webui` | `ghcr.io/open-webui/open-webui:v0.9.6-slim` | Chat UI connected to OVMS |
| `whisper-stt` | `whisper-stt:latest` (local build) | Speech-to-text with Prometheus metrics |
| `nginx-https` | `nginx:alpine` | HTTPS reverse proxy (self-signed cert, enables browser mic) |

All services share the `fedaero` Docker network and are defined in [`docker-compose.yml`](docker-compose.yml).

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker Engine ≥ 24 | [Install guide](https://docs.docker.com/engine/install/) |
| Docker Compose v2 | Included with Docker Desktop; on Linux install the `docker-compose-plugin` package. Use `docker compose` (space), not `docker-compose` (hyphen). |
| `render` group | Required for GPU access by OVMS. Verify with `getent group render`. |
| Git | Required for `make vippet-get` to sparse-checkout VIPPET. |
| Intel GPU with OpenVINO driver | iGPU or discrete Xe GPU supported. |
| **CDI only:** CDI drivers configured | Set `CDI_XE_DEVICE_0` in `.env` (see `AGENTS.md` for all env vars). |

Run `make setup` after cloning to auto-detect the `render` group GID and write `.env`.

## Quick Start

> **Recommended — use `make deploy`.**
> This stack requires VIPPET to be running first because the `fedaero` Docker network is created by VIPPET. Running `docker compose up -d` directly **will fail** with:
> ```
> network visual-pipeline-and-platform-evaluation-tool_default declared as external, but could not be found
> ```
> `make deploy` handles everything — it fetches VIPPET, starts it, waits for the network, then brings up this stack.

```bash
cd apps/handheld-multi-modal
make deploy        # standard GPU
make deploy-cdi    # CDI / SR-IOV environments
```

**Development / testing without VIPPET** — a standalone variant creates its own isolated `fedaero` network. Metrics from VIPPET pipelines will not be available.

```bash
make up-standalone
```

## Endpoints

Open WebUI, Grafana, and Whisper STT are only accessible via the nginx TLS reverse proxy — their container ports are not exposed directly to the host.

| Service | URL | Notes |
|---------|-----|-------|
| Open WebUI | https://localhost:8443 | LLM chat UI — browser mic enabled (via nginx) |
| Grafana | https://localhost:7443 | Pre-provisioned dashboards (via nginx) |
| Whisper STT | https://localhost:5443 | Speech-to-text — browser mic enabled (via nginx) |
| VIPPET UI | https://localhost:443 | via nginx |

## Make Targets

```
make deploy            Full one-shot deploy (setup + vippet + this stack)
make deploy-cdi        Same for CDI / SR-IOV environments
make up                Start this stack (standard, requires VIPPET network)
make up-cdi            Start this stack (CDI, requires VIPPET network)
make up-standalone     Start this stack without VIPPET (dev/testing only)
make down              Stop all services
make build             Build local images
make restart           Restart all services
make urls              Print all service endpoints
make test              Check service connectivity
make health            Show service health/status
make clean CONFIRM=yes Stop containers and remove all data dirs
```

## Component READMEs

- [LLM — OVMS + Open WebUI](apps/LLM-OpenWebUI/README.md)
- [Speech-to-Text — Whisper STT](apps/speech-to-text/README.md)
