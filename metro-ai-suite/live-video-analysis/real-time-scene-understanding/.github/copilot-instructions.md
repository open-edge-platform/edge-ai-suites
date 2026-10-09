<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Real Time Scene Understanding - AI agent instructions

## What this project is

Real Time Scene Understanding is a Python FastAPI application that ingests RTSP camera streams, relays low-latency video through MediaMTX and WebRTC, performs VLM-based alert detection, and runs temporal deep analysis over consecutive frames. SeaweedFS stores alert artifacts and the browser dashboard uses the backend REST API.

## Repository map

- `compose.yaml` - Docker Compose deployment and supporting services.
- `app/` - Python application source, UI, Dockerfile, and `pyproject.toml`.
- `app/backend/routes/` - FastAPI route construction and HTTP endpoints.
- `app/backend/services/` - stream, frame, alert, VLM, analysis, and storage services.
- `app/tests/` - unit and route tests.
- `ov_models/` - OpenVINO model files organized by device.
- `model_download_scripts/` - model download and conversion helpers.
- `configs/` - runtime service configuration such as SeaweedFS S3 settings.
- `docs/user-guide/` - setup, architecture, API, troubleshooting, and release documentation.
- `scripts/setup_env.sh` - creates the local `.env` file with host-specific values.

## Architecture

The main runtime path is:

```text
RTSP camera -> Python/PyAV stream handling -> MediaMTX -> browser WebRTC playback
                                  |
                                  +-> alert VLM gate -> deep multi-frame analyzer
                                                           |
                                                           +-> SeaweedFS -> alert API/dashboard
```

Supporting services are defined in `compose.yaml`: `mediamtx`, `coturn`, `metrics-manager`, `seaweedfs`, and `real-time-scene-understanding`.

## Skills

Task-specific procedures live under `.github/skills/`. Load the relevant skill before acting:

| User intent | Skill |
|---|---|
| Configure, build, start, stop, or inspect the stack | `rtsu-deployment` |
| Diagnose dashboard, API, stream, WebRTC, model, device, or storage failures | `rtsu-troubleshooting` |
| Run focused tests, the full suite, coverage, or runtime validation | `rtsu-testing` |

Read the selected skill's `SKILL.md` and use only the procedures relevant to the current task.

## Development workflow

- Run commands from the repository root.
- Create or refresh environment configuration with `bash scripts/setup_env.sh`.
- Start the stack with `docker compose up -d`.
- Check service state with `docker compose ps`.
- View application logs with `docker compose logs -f real-time-scene-understanding`.
- Stop the stack with `docker compose down`.
- Open the dashboard at `http://<host>:9100` unless `PORT` is overridden.
- Check backend health at `http://<host>:9100/api/health`.
- Run Python tests from `app/` with `uv run pytest` when `uv` is available, or with the project environment's `pytest`.

The setup script must be run with `bash` as documented. Do not assume that changing `DASHBOARD_PORT` changes the published host port; Compose publishes host `PORT` to the container's fixed port `9100`.

## Models and devices

- Alert detection uses `ALERT_VLM_MODEL` and `ALERT_VLM_DEVICE`.
- Deep analysis uses `DEEP_ANALYZER_MODEL` and `DEEP_ANALYZER_DEVICE`.
- Models are mounted read-only at `/models` and should be stored under `ov_models/<device>/<model-name>/`.
- GPU and NPU execution depends on host Intel runtimes and `/dev/dri` or the configured NPU device.
- Verify that a deep-analyzer model supports video input before changing it.
- Do not commit model weights, Hugging Face tokens, access keys, or passwords.

## Code and security conventions

- This project is a FastAPI application; preserve the existing `pyproject.toml` dependency setup and keep compatibility with Python 3.12+.
- Prefer existing route builders and service abstractions over new parallel patterns.
- Validate external input at API and stream boundaries.
- Do not expose exception internals, credentials, tokens, or sensitive paths in responses or logs.
- Keep storage credentials in environment configuration or approved secret mechanisms.
- Treat RTSP URLs, prompts, uploaded data, and configuration values as untrusted input.
- Keep Docker device and privilege changes narrowly justified.
- Add or update focused tests for behavior changes.
- Add the SPDX copyright and license header to every new source, configuration, or documentation file.
- Update the relevant user guide or API reference when commands, endpoints, configuration, or behavior changes.

## Change validation

For backend changes, run the focused tests first, then the complete suite from `app/`:

```bash
uv run pytest tests/test_<area>.py
uv run pytest
```

For Compose, model, or environment changes, validate the affected configuration and inspect `docker compose ps` and service logs. Do not claim a runtime change works without checking the relevant health endpoint or test.

## Instruction boundaries

This file is the canonical project guidance for AI coding assistants. Keep detailed, task-specific procedures in future skill files under `.github/skills/`; do not duplicate them here.