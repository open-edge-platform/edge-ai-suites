# Build from Source

This guide provides instructions for building the VMS Adapter Plugin (VAP) from source code.
Whether you are customizing the application or deploying a modified version, this guide walks
you through the complete build process.

## Overview

The VAP application consists of the following components built from source:

- **Backend**: FastAPI Python service (`plugin/`) that manages VMS shims, analytics app shims,
  camera sync, event processing, and result routing.
- **UI**: React 19 / Vite frontend (`ui/`) served by nginx, providing the provider dashboard.

The `Dockerfile` in the repository root builds the backend image. The UI is built inside a
multi-stage Docker build. Both are orchestrated by Docker Compose.

## Step 1: Clone the Repository

Clone the repository and navigate to the VAP directory:

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/vms-adapter-plugin
```

## Step 2: Configure the Environment

Copy the example environment file and edit it for your setup:

```bash
cp .env.example .env
```

Set at minimum the following variables before building:

| **Variable**                                  | **Description**                                                         |
|-----------------------------------------------|-------------------------------------------------------------------------|
| `LVC_BASE_URL`                                | URL of the running LVC backend, e.g. `http://<lvc-host>:4173`           |
| `MEDIAMTX_URL`                                | URL of the MediaMTX WebRTC server, e.g. `http://<lvc-host>:8889`        |
| `FRIGATE_HOST`                                | Hostname/IP of the Frigate instance reachable from the backend container|
| `NX_BASE_URL` / `NX_USERNAME` / `NX_PASSWORD` | Nx Witness credentials (only if using Nx Witness)                       |
| `NX_TLS_VERIFY` / `NX_CA_BUNDLE`              | Nx TLS verification toggle and optional CA bundle path (default: `false`) |
| `DLS_VISION_TLS_VERIFY` / `DLS_VISION_CA_BUNDLE` | DLStreamer TLS verification toggle and optional CA bundle path (default: `false`) |
| `PG_PASSWORD`                                 | PostgreSQL password (change from default)                               |

Refer to `.env.example` for all available variables.

## Step 3: Build and Start with Docker Compose

Build all images and start the full stack:

```bash
docker compose up -d --build
```

### Customizing the Build

You can control the image registry and tag by setting environment variables before running
the build command:

```bash
export REGISTRY_URL=<your-container-registry-url>    # e.g. "docker.io/username/"
export TAG=<your-tag>                                # e.g. "1.0.0" or "latest"
```

> **Note:** If `REGISTRY_URL` or `TAG` are not set, the defaults in the Docker Compose file
> are used.

## Step 4: Verify the Build

Check that all services are running:

```bash
docker compose ps
```

Expected output — all services should show **healthy** or **running**:

```
NAME              STATUS
vms-backend       Up (healthy)
vms-ui            Up
postgres          Up (healthy)
```

Verify the backend is up:

```bash
curl http://localhost:8085/v1/health
```

## Local Development

### Backend

To run the backend outside Docker for local development:

```bash
pip install -e ".[dev]"
export VMS_PLUGIN_CONFIG_PATH=$PWD/config/config.yaml
uvicorn plugin.analytics.main:app --reload --port 8082
```

Run tests:

```bash
pytest tests/ -v
```

### Frontend

To run the React UI locally with hot reload:

```bash
cd ui
npm install
npm run dev       # http://localhost:5173 — proxies /v1 to backend
npm run build
```

## What to Do Next

- [Get Started](../get-started.md): Complete the initial setup and start an analytics session.
- [System Requirements](./system-requirements.md): Review hardware and software requirements.
- [API Reference](../api-reference.md): Explore the available REST API endpoints.
- [Troubleshooting](../troubleshooting.md): Find solutions to common build and deployment issues.
