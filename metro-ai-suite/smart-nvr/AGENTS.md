# Agent Instructions

## Project Overview

Smart NVR is a Python application for edge video analytics. It has a FastAPI backend,
a Gradio-based UI, and Docker/Helm deployment assets for running with Frigate, MQTT,
Redis, VSS Search, VSS Summary, and optional VLM/Scenescape integrations.

The project is not packaged as an installable library. `pyproject.toml` sets
`[tool.uv] package = false`, and the Docker image copies `src/` and `ui/` directly
into the runtime image.

## Repository Map

- `src/`: backend service code.
  - `src/main.py`: FastAPI app entry point.
  - `src/api/`: API router and endpoint service wrappers.
    - `src/api/endpoints/brokers_api.py`: CRUD endpoints for runtime multi-broker management.
    - `src/api/endpoints/vss_api.py`: `GET /vss-features` — detects active VSS deployment mode.
  - `src/service/`: Redis, MQTT, Frigate, watcher, dispatcher, and rule logic.
    - `src/service/broker_manager.py`: async multi-broker MQTT connection lifecycle (connect/reconnect/stop).
  - `src/model/`: Pydantic/domain models.
    - `src/model/broker.py`: Broker configuration model.
  - `src/tests/`: backend tests.
- `ui/`: Python UI code.
  - `ui/main.py`: Gradio UI entry point.
  - `ui/interface/`: UI construction and interaction handlers.
  - `ui/services/`: backend API client and UI service helpers.
  - `ui/test/`: UI tests.
- `docker/`: Dockerfile, Compose file, and entrypoint.
- `charts/`: Helm chart and packaged chart artifacts.
- `resources/`: Frigate, MQTT, Scenescape, RTSP, and sample-video resources.
- `scripts/`: supporting shell utilities.
- `docs/user-guide/`: user, developer, API, deployment, and troubleshooting docs.

## Development Commands

Use `uv` for local development.

```bash
uv sync
uv run pytest
uv run pytest src/tests
uv run pytest ui/test
uv run pytest --cov=src --cov=ui --cov-report=term-missing:skip-covered
```

There is no configured formatter or linter in this repo at the moment. Keep edits
consistent with the surrounding files and run focused tests for changed behavior.

## Running Services

Local test runs should not require Docker services because tests mostly patch network
and service dependencies. Do not start the Docker stack unless the task specifically
requires integration/runtime validation.

Common stack commands:

```bash
./build.sh
source setup.sh start           # single-node: all services
source setup.sh stop
source setup.sh start-si        # distributed System 1: SI + RTSP streamer
source setup.sh stop-si
source setup.sh start-nvr       # distributed System 2: NVR only
source setup.sh stop-nvr
source setup.sh start-streamer  # RTSP streamer only
source setup.sh stop-streamer
```

`setup.sh start` validates required environment variables and starts Docker Compose.
It may also generate MQTT secrets, alter `resources/frigate-config/config.yml`, and
start RTSP/Scenescape components depending on environment flags. Treat changes under
`resources/` as potentially user-visible deployment configuration.

Important environment variables used by the stack include:

- `NVR_GENAI`
- `NVR_SCENESCAPE`
- `VSS_IP`
- `VSS_PORT`
- `VLM_SERVING_IP`
- `VLM_SERVING_PORT`
- `SI_RTSP_HOST`
- `SCENESCAPE_MQTT_BROKER`
- `MAX_CONCURRENT_EVENTS`
- `BROKER_RECONNECT_DELAY`
- `BROKERS_CONFIG_PATH`
- `MQTT_USER`
- `MQTT_PASSWORD`
- `REGISTRY_URL`
- `PROJECT_NAME`
- `TAG`

## Code Guidelines

- Preserve the existing Python module layout. Backend modules import from `src/`
  as top-level packages such as `api`, `service`, `model`, and `utils`; tests adjust
  `sys.path` accordingly.
- Keep FastAPI route behavior aligned with `docs/user-guide/api-reference.md` when
  changing API contracts.
- Keep UI service functions in `ui/services/` as the boundary between Gradio handlers
  and backend HTTP calls.
- Prefer dependency injection, fixtures, and mocks in tests instead of requiring live
  Redis, MQTT, Frigate, VSS, or VLM services.
- Be careful with runtime side effects in imports. Many tests import routers and
  services directly.
- Keep Docker runtime paths in mind: the image copies `src/` to `/app/backend` and
  `ui/` to `/app/ui`, then runs either `uvicorn main:app` or `python -m ui.main`
  depending on `MODE`.
- Maintain the existing Apache-2.0 copyright/SPDX header style in Python and shell
  files that already use it.

## Testing Guidance

Add or update tests near the changed behavior:

- Backend route/service changes: `src/tests/`
- UI API-client or UI helper changes: `ui/test/`
- Async backend behavior: use the existing `pytest-asyncio` setup and fixtures.
- Network/service behavior: mock `requests`, Redis clients, MQTT clients, and VSS
  calls unless the task is explicitly an integration test.

Before handing off code changes, run the narrowest meaningful test command. For shared
or cross-cutting changes, run `uv run pytest`.

## Documentation And Deployment Updates

Update docs when changing user-visible behavior:

- API shape or status codes: `docs/user-guide/api-reference.md`
- Setup, required environment, or service startup: `docs/user-guide/get-started.md`
  and possibly `docs/user-guide/troubleshooting.md`
- Build or image behavior: `docs/user-guide/get-started/build-from-source.md`
  and `docker/Dockerfile`
- Helm deployment defaults: files under `charts/`

Avoid editing generated or packaged artifacts such as `uv.lock` or chart archives
unless dependency or packaging changes require it.
