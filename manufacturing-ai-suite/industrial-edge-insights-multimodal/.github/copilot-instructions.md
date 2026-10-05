<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Multimodal Weld Defect Detection — AI agents

## Canonical Instructions

Use this file as the canonical router for coding agents. Keep tool-specific
files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/multimodal.mdc` as
short pointers to this file.

## What This App Is

The Multimodal Weld Defect Detection sample application fuses **vision**
(DL Streamer Pipeline Server) and **time-series** (Time-Series Analytics
Microservice) analytics to detect welding anomalies in real time. Fusion
analytics combines both signals with configurable `AND`/`OR` logic. It ships
as a Docker Compose stack with an optional Helm/Kubernetes deployment path,
and supports three variants: default (vision + time-series), vLLM-based VLM
inference, and an agentic VLM pipeline. Deeper user docs live under
[`docs/user-guide/`](../docs/user-guide/); this file is the agent-facing map.

## Deployment Modes

| Mode     | Make target     | Compose overlay                         | Notes |
|----------|------------------|------------------------------------------|-------|
| Default  | `make up`        | `docker-compose.yml`                      | Vision + time-series fusion, no extra hardware gate |
| vLLM     | `make up_vllm`   | `+ docker-compose-vllm.yml`               | Requires `make check_hardware` + `make check_models` (models pre-staged in `configs/vllm/models`, `configs/vllm/huggingface`) |
| Agentic  | `make up_agentic`| `+ docker-compose-agentic.yml` + vllm     | Requires hardware check; runs `make download_model` first (downloads/converts the LLM, can take minutes) |

All `up*` targets run `check_env_variables`, `validate_host_ip`, and `down`
first. `check_hardware` requires an Intel Panther Lake / Core Ultra 3xx CPU
unless `PLATFORM_CHECK=false` is set in `.env` (CI/validation use only).

**Use the `multimodal-deploy` skill** ([`.github/skills/multimodal-deploy/SKILL.md`](skills/multimodal-deploy/SKILL.md))
to drive build/deploy/smoke-test/functional-test cycles instead of running
raw commands ad hoc.

## Component Map

| Path | Purpose |
|------|---------|
| `Makefile` | All lifecycle targets (build, up/up_vllm/up_agentic, down, status, helm) |
| `docker-compose.yml` | Default stack: DL Streamer Pipeline Server, Time-Series Analytics Microservice, InfluxDB, Grafana, MQTT broker, Telegraf, MediaMTX, coturn, SeaweedFS, nginx |
| `docker-compose-vllm.yml` | vLLM/OVMS VLM inference overlay |
| `docker-compose-agentic.yml` | Agentic pipeline overlay (adds model-download service) |
| `.env` | Runtime configuration (credentials, `HOST_IP`, `GRAFANA_PORT`, LLM settings) — never commit real secrets |
| `configs/` | Per-service config: `agentic/`, `dlstreamer-pipeline-server/`, `grafana/`, `influxdb/`, `mqtt-broker/`, `nginx/`, `seaweedfs-s3/`, `telegraf/`, `time-series-analytics-microservice/` |
| `fusion-analytics/` | Fusion service combining vision + time-series anomaly signals (`fusion.py`, `api.py`) |
| `weld-data-simulator/` | Synthetic weld sensor data publisher for demo/testing |
| `ui-service/` | Web UI backend/frontend (`src/`, own `pytest.ini`) |
| `insights-workbench/` | Workbench app (`app.py`, prompt templates) |
| `training/` | `classification-training/`, `vlm-fine-tuning/` — offline model training, not part of the runtime stack |
| `helm/` | Helm chart (generated/populated by `make gen_helm_charts`); `values.yaml`, `templates/` |
| `tests/functional/` | pytest suites for Docker and Helm deployment (CPU/GPU/NPU variants) |
| `docs/user-guide/` | Get-started, build-from-source, Helm deploy, alerts/config how-tos, troubleshooting |

## Key Environment Variables (`.env`)

- `HOST_IP` (default `localhost`), `GRAFANA_PORT` (default `3000`)
- `INFLUXDB_USERNAME/PASSWORD`, `VISUALIZER_GRAFANA_USER/PASSWORD`,
  `MTX_WEBRTCICESERVERS2_0_USERNAME/PASSWORD`, `S3_STORAGE_USERNAME/PASSWORD`
  — all validated by `make check_env_variables` (length/charset rules)
- `PLATFORM_CHECK` — set `false` to skip the Panther Lake hardware gate (CI only)
- `LLM_DEVICE`, `LLM_WEIGHT_FORMAT`, `LLM_MODEL_NAME` — vLLM/agentic model selection
- `DOCKER_REGISTRY`, `IMAGE_SUFFIX`, `WEEKLY_BUILD_DATE` — push/versioning

## Useful Commands

```bash
make build                # Build Docker images (add build_copyleft_sources for copyleft sources)
make up                   # Default variant
make up_vllm              # vLLM/VLM variant (hardware + model checks first)
make up_agentic           # Agentic variant (hardware check + model download first)
make status               # Container status + recent error-log scan
make down                 # Stop and remove containers + volumes
make push_images          # Build then push to DOCKER_REGISTRY
make gen_helm_charts      # Generate/refresh helm/ from current configs
make push_helm_charts     # Package and push Helm chart to registry
make help                 # Full command list from the Makefile
```

See [`.github/skills/multimodal-deploy/references/command-reference.md`](skills/multimodal-deploy/references/command-reference.md)
for the full, normative target/flag catalogue.

## Keeping Agent Guidance in Sync

**This file and the `multimodal-deploy` skill must be updated whenever the
Makefile, compose files, Helm chart, `.env` schema, or `docs/user-guide/`
content change.** Specifically:

- New/renamed Make targets or compose overlays → update the Deployment Modes
  table here and `references/command-reference.md` in the skill.
- New/changed functional test files → update `references/functional-tests.md`.
- New env vars or validation rules → update Key Environment Variables here and
  the skill's prerequisite checks.
- Port/URL changes → update Useful Commands/Endpoints here and
  `scripts/smoke-check.sh` in the skill.

Stale agent guidance is worse than none — treat these docs as part of the
change whenever you touch deployment-affecting files.
