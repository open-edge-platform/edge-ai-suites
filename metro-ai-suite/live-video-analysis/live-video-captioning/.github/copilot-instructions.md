<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Live Video Captioning — AI agents

## Canonical Instructions

Use this file as the canonical router for coding agents. Keep tool-specific
files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/lvc.mdc` as short
pointers to this file.

## What This Repo Is

Live Video Captioning (LVC) is an Intel sample application that generates
real-time captions for live RTSP video streams. It pairs **Deep Learning
Streamer (DL Streamer)** pipelines with **OpenVINO™ Vision Language Models**
(InternVL, MiniCPM) and is designed to run **locally** on Intel hardware. It
ships as a multi-service Docker Compose stack: a FastAPI backend that also
serves the web dashboard, an MQTT broker for caption/metadata transport, the
DL Streamer pipeline server for inference, and mediamtx/coturn for WebRTC video.
Deeper user docs live under [`docs/user-guide/`](../docs/user-guide/); this file
is the agent-facing map.

## Deployment

The stack is brought up with Docker Compose from the repository root. Models are
**not** committed and must be downloaded once before the first launch:

```bash
./model_download_scripts/download_models.sh --model OpenGVLab/InternVL2-1B --type vlm --weight-format int8
bash scripts/setup_env.sh   # renders .env (run once)
docker compose up -d        # launch the stack
docker compose down         # stop the stack
```

The optional embedding/RAG profile adds `multimodal-embedding-serving`,
`vdms-vector-db`, and `live-video-captioning-rag` (gated by `ENABLE_EMBEDDING`).
Use the `lvc-run-app` skill to drive deploy + smoke-test, and `lvc-test` for the
backend unit suite.

## Architecture at a Glance

All dashboard and API traffic enters through **video-caption-service** on host
port `DASHBOARD_PORT` (default **`4173`**); the REST API is under the `/api/...`
prefix. Core services (see `compose.yaml`):

- **video-caption-service** — FastAPI backend + static web dashboard; owns the
  `/api` REST API and the SSE metadata stream. The only port agents target.
- **dlstreamer-pipeline-server** — DL Streamer pipeline server (port `8040`)
  that samples frames and runs VLM inference.
- **mqtt-broker** — eclipse-mosquitto; carries captions/metadata between the
  pipeline server and the backend.
- **mediamtx** / **coturn** — WebRTC media + TURN for live video in the UI.
- **metrics-manager** — metrics manager.
- **multimodal-embedding-serving**, **vdms-vector-db**,
  **live-video-captioning-rag** — embedding, vector DB, and RAG (EMBEDDING
  profile only; harmless "variable is not set" warnings appear when disabled).

### Real API (do not trust stale route docs elsewhere)

- `GET /api/health`
- `GET /api/vlm-models`, `GET /api/detection-models`, `GET /api/pipelines`,
  `GET /api/cameras`
- `POST | GET | DELETE /api/generate_captions_alerts[/{run_id}]`
- `GET /api/generate_captions_alerts/{run_id}/stream-ready`
- SSE `GET /api/generate_captions_alerts/metadata-stream`
- `GET /runtime-config.js` (frontend runtime settings)

Video sources must be `rtsp://` or `/dev/videoN`; the API rejects `file://`.

## Repository Map

| Path | Contents |
|---|---|
| `compose.yaml` | Docker Compose orchestration for all services. |
| `config.json` | Application/pipeline configuration. |
| `app/` | FastAPI application package (backend + UI + tests). |
| `app/main.py` | App entry point: router registration, UI mount, lifespan. |
| `app/backend/config.py` | Environment configuration and defaults. |
| `app/backend/state.py` | Global run state (`RUNS`). |
| `app/backend/routes/` | FastAPI route handlers (all under `/api`). |
| `app/backend/services/` | MQTT, HTTP client, discovery, pipeline health. |
| `app/tests/` | pytest suite (`conftest.py` + `test_*.py`). |
| `app/ui/` | Frontend static files served at `/`. |
| `charts/` | Helm chart + subcharts for Kubernetes. |
| `scripts/` | `setup_env.sh`, `setup_proxy_rtsp.sh`, `setup.sh`, `setup_embeddings.sh`. |
| `model_download_scripts/` | `download_models.sh` model helper. |
| `pipeline_server_patches/` | Patches applied to the pipeline server image. |
| `docs/user-guide/` | User/developer documentation. |
| `ov_models/`, `ov_detection_models/` | Downloaded models (not committed). |

## Tech Stack

Python >=3.12 + FastAPI/Uvicorn (backend, deps in `app/uv.lock`, managed with
uv), paho-mqtt for MQTT, OpenVINO Vision Language Models (InternVL, MiniCPM) for
inference, DL Streamer for the media pipeline, vanilla JS + SSE + WebRTC for the
dashboard, Docker Compose for local deploy and Helm for Kubernetes.

## Conventions

- Run repo-local commands from the **repository root** unless a skill says
  otherwise; run the test suite from `app/`.
- Every new source/config/doc file carries the SPDX header used across the repo
  (`SPDX-FileCopyrightText: (C) 2026 Intel Corporation` / `Apache-2.0`).
- Target the dashboard port (`4173`) and the `/api/...` prefix; do not hit
  internal service ports directly.
- Always `curl --noproxy '*'` for localhost calls — corporate proxy env breaks
  them.
- Use absolute imports (`from backend.config import ...`); add type hints and
  keep backend coverage ≥ 80%.
- All configuration goes through `backend/config.py` and environment variables;
  never hardcode values or commit secrets/model files.

## Skills

Reusable LVC workflow skills live under [`.github/skills/`](skills/). Use
[`.github/skills/skill-catalog.json`](skills/skill-catalog.json) to pick the
relevant skill, then read that skill's `SKILL.md`.

| User intent | Skill |
|---|---|
| Run, start, smoke-test, or verify the LVC stack end to end | `lvc-run-app` |
| Run the backend unit test suite / check coverage | `lvc-test` |

## Skill Loading Rules

- Load only the skill needed for the current request.
- Use a skill's `references/`/`scripts/` files only when its `SKILL.md` points
  to them.
- Prefer the repo's real interfaces: `compose.yaml`, `setup_env.sh`,
  `download_models.sh`, the `/api/...` REST API, and the skill driver
  `.github/skills/lvc-run-app/smoke.sh`.
- Run commands yourself when the harness permits it and relay the result.
- Probe `GET /api/health` before API workflows. If the backend is not healthy,
  use the `lvc-run-app` skill to (re)launch the stack.

## Path Conventions

All paths in the skill catalog are relative to the repository root. The skills
live in `.github/skills` as the shared location for Codex, Copilot CLI, Claude
Code, Cursor, and local agent scripts.
