# Smart Building Digital Twin Blueprint Guidelines

## Architecture
This repo layers analytics and setup automation on top of a Scenescape deployment. Preserve the distinction between host-side access and container-internal networking.

- Keep internal Docker service discovery aligned with upstream Scenescape expectations:
  - `broker.scenescape.intel.com`
  - `web.scenescape.intel.com`
  - `autocalibration.scenescape.intel.com`
- Do not make `PUBLIC_HOSTNAME` drive internal container-to-container URLs.
- Host-side setup and helper scripts should use loopback API access by default: `https://localhost/api/v1`.
- For loopback API access, bypass host proxy settings so local `curl` traffic does not tunnel through `HTTP_PROXY` or `HTTPS_PROXY`.

## Images And Runtime
All Scenescape images (`intel/scenescape-*:2026.2.0-rc2`) are pulled from Docker Hub — do not add build steps for them. The DLStreamer GST plugin scripts are sparse-cloned by `setup.sh` into `generated/scenescape-plugins/` (no full repo clone, no build). `scene-narrator` uses `python:3.12-slim` directly with pip dependencies installed at container start; there is no Dockerfile for it.

## Setup And Runtime
When working on setup, preserve these behaviors unless the task explicitly requires a change.

- `setup.sh` should bring up the full stack needed for the blueprint, including `scene`, `autocalibration`, `analytics`, and `scene-narrator`.
- API readiness is not just container startup; prefer web health plus auth/API validation over fixed sleeps.
- Scene import must tolerate short readiness races and report HTTP/body diagnostics instead of raw parser failures.
- `cleanup.sh` should remain consistent with generated certs, UUID files, and Docker volumes used by setup.
- `generated/scenescape-plugins/` is created by `setup.sh` and referenced by `SCENESCAPE_DIR` in `.env`; do not delete it without also clearing `SCENESCAPE_DIR` from `.env`.

## Cross-System Tuning
Differences across machines are expected. When tuning on another system:

- Compare GPU vs CPU inference mode first; `setup.sh` selects this from detected Intel GPU hardware.
- Treat CPU and platform-generation differences as meaningful inputs, not background noise. A newer platform such as Panther Lake can change inference cadence, replay timing, event ordering, and alert thresholds relative to an Arrow Lake reference system.
- When results differ, compare effective throughput and timing before changing business logic. Performance differences can alter when objects are associated, when doors/bags/persons are observed, and whether short-lived conditions cross analytics thresholds.
- Treat scene UUIDs as deployment-specific. `setup.sh` should resolve them from the API and write `config/resolved-uuids.json`; avoid hardcoding UUIDs in source.
- Keep browser-facing values (`PUBLIC_HOSTNAME`, `SCENESCAPE_UI_URL`, `DASHBOARD_URL`) separate from host-local setup values (`API_BASE_URL`).
- If behavior differs, inspect `.env`, `docker compose ps`, `docker compose logs`, `config/resolved-uuids.json`, and exported scene/object-class configuration before changing analytics logic.

## Configuration Changes
- Prefer updating exported configuration snapshots over adding environment-specific logic when the issue is scene calibration, regions, or object classes.
- After live tuning in the UI, run `scripts/export-config.sh` and review `config/object-classes.json` plus `config/scenes/*.json` for the durable change.
- Keep code changes minimal and targeted; do not revert upstream-compatible internal hostname assumptions without strong evidence.
