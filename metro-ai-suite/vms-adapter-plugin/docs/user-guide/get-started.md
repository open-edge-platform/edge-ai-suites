# Get Started

## Overview

The **VMS Adapter Plugin (VAP)** bridges Video Management Systems (VMS), such as Nx Witness,
Genetec, and Milestone VMS platforms, with AI Analytics Applications, such as Live Video Captioning (LVC),
DL Streamer vision analytics applications like Loitering Detection. This guide
shows how to deploy the full stack with the Docker Compose tool and run your first analytics
session.

This guide shows how to:

- **Set up prerequisites**: Start LVC or DL Streamer vision analytics (Loitering Detection) before VAP,
  since VAP fetches their schemas at startup.
- **Configure the environment**: Point VAP at your VMS and Analytics App services.
- **Start analytics**: Discover cameras and start pipelines from the Nx Witness client.

## Quick Start

Check the [folder layout](#folder-layout) to familiarize yourself with the code structure.

### Prerequisites

- Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- Install the Docker platform: [Installation Guide](https://docs.docker.com/get-docker/).
- Install the Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- **Nx Witness** VMS with an accessible REST API (`NX_HOST`,
  `NX_USERNAME`, `NX_PASSWORD`). This document does not cover Nx Witness or Nx Cloud setup.
- At least one Analytics Application running before VAP starts:
  - **Live Video Captioning (LVC)** — for Vision-Language Model (VLM) based AI captioning.
  - **Loitering Detection (DL Streamer Vision based)** — for real-time detection of loitering behavior in
    transportation hubs with Nx write-back.

## Step 1 — Start Live Video Captioning (LVC)

> **Note:** Skip this step if you are only using Loitering Detection.

Clone and start the LVC application from its own directory. LVC must be running before VAP
starts, because VAP fetches the LVC OpenAPI schema at startup to build the analytics
configuration form:

```bash
git clone --filter=blob:none --sparse --branch release-2026.2.0 https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/live-video-captioning
```

Follow the [LVC Get Started guide](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/live-video-captioning/quick-start-guide.html)
to prepare models and configure the environment, then start the stack:

```bash
docker compose up -d
```

Verify LVC is reachable:

```bash
curl http://localhost:4173/health
```

## Step 2 — Start Loitering Detection

> **Note:** Skip this step if you are only using Live Video Captioning.

Loitering Detection is a user-provided application based on the DL Streamer Pipeline Server. Follow the [Loitering Detection Get Started guide](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/loitering-detection/get-started.html) to bring up the application. Ensure all containers are running, but do not start the pipelines yet. The following services must be reachable from the VAP backend container:

| **Service**                 | **Default Port** | **Purpose**                          |
| --------------------------- | ---------------- | ------------------------------------ |
| DL Streamer Pipeline Server | `8080`           | Receive pipeline start/stop commands |
| MQTT Broker                 | `1883`           | Publish inference metadata to VAP    |

Verify the DL Streamer Pipeline Server is reachable:

```bash
curl http://<LOITERING_DETECTION_HOST>:8080/pipelines
```

## Step 3 — Clone VAP and Create the `.env` File

```bash
cd metro-ai-suite/vms-adapter-plugin
cp .env.example .env
```

Open `.env` and update the variables for your environment. Variables are grouped by scope. Within each analytics app group, **Mandatory** applies only if you are using that app.

**Common (VAP with Nx Witness):**

| **Variable**                              | **Description**                                                           | **Required?** |
| ----------------------------------------- | ------------------------------------------------------------------------- | ------------- |
| `NX_HOST` / `NX_USERNAME` / `NX_PASSWORD` | Nx Witness host and credentials                                           | Mandatory     |
| `NX_TLS_VERIFY` / `NX_CA_BUNDLE`          | Nx TLS verification toggle and optional CA bundle path (default: `false`) | Optional      |
| `PG_PASSWORD`                             | PostgreSQL password (change from default)                                 | Optional      |
| `UI_HTTPS_PORT`                           | Host port for the dashboard HTTPS (default: `3443`)                       | Optional      |

**Live Video Captioning (LVC):**

| **Variable**                         | **Description**                                                          | **Required?** |
|--------------------------------------|--------------------------------------------------------------------------|---------------|
| `LVC_BASE_URL`                       | URL of the running LVC backend, e.g., `http://<lvc-host>:4173`           | Mandatory     |
| `MEDIAMTX_URL`                       | URL of the MediaMTX WebRTC server, e.g., `http://<lvc-host>:8889`        | Mandatory     |
| `MQTT_BROKER_TLS_ENABLED` / `MQTT_BROKER_CA_BUNDLE` / `MQTT_BROKER_CLIENT_CERT` / `MQTT_BROKER_CLIENT_KEY` | MQTT TLS, CA bundle, and optional mutual TLS client certificate for the LVC broker subscriber | Optional |

**DL Streamer Vision (`dls_vision` — Loitering Detection):**

| **Variable**                         | **Description**                                                          | **Required?** |
|--------------------------------------|--------------------------------------------------------------------------|---------------|
| `DLS_VISION_HOST` / `DLS_VISION_PORT` | DL Streamer Pipeline Server host and port for Loitering Detection app (default port: `443`) | Mandatory |
| `MQTT_HOST` / `MQTT_PORT`            | MQTT broker host and port for `dls_vision` metadata (default: `1883`)             | Mandatory     |
| `DLS_VISION_TLS_VERIFY` / `DLS_VISION_CA_BUNDLE` | DL Streamer TLS verification toggle and optional CA bundle path (default: `false`) | Optional |
| `MQTT_TLS_ENABLED` / `MQTT_CA_BUNDLE` / `MQTT_CLIENT_CERT` / `MQTT_CLIENT_KEY` | MQTT TLS, CA bundle, and optional mutual TLS client certificate for the dls_vision subscriber | Optional |

> **Note:** If Live Video Captioning or Loitering Detection is running on the same host as VAP, use `host.docker.internal`
> (Linux/Mac). Otherwise, use the actual IP address.

For certificate path examples and TLS behavior details, see
[TLS and Certificate Configuration](./how-to-guides/tls-and-certificates.md).

## Step 4 — Build and Start VAP

```bash
docker compose up -d --build
```

Wait for all services to become healthy:

```bash
docker compose ps
```

Expected output — all services should show **healthy** or **running**:

```text
NAME                          STATUS
vms-adapter-backend           Up (healthy)
vms-adapter-ui                Up
vms-adapter-postgres          Up (healthy)
```

Verify the dockers are up and running:

```bash
docker ps
```

## Step 5 — Discover Cameras

Trigger camera discovery once after VAP starts. VAP queries Nx Witness and persists the
results to PostgreSQL:

```bash
curl -k -X POST https://localhost:3443/v1/cameras/discover
```

## Step 6 — Start Analytics from the Nx Witness Client

The recommended way to start and stop pipelines is directly from the **Nx Witness desktop
client**. VAP polls Nx Witness every 5 seconds and reacts to per-camera settings changes
automatically.

1. In the Nx Witness desktop client, right-click a camera → **Camera Settings**.
2. Go to the **Integrations** tab and expand **VAP Analytics Integration**.
3. Configure the fields and enable the pipeline.

### Live Video Captioning

| **Field**                                 | **Type**   | **Description**                                  |
| ----------------------------------------- | ---------- | ------------------------------------------------ |
| **Enable Live Video Captioning Pipeline** | Checkbox   | Starts or stops the LVC pipeline for this camera |
| **Device**                                | Dropdown   | Inference device: `CPU`, `GPU`, or `NPU`         |
| **Prompt**                                | Text field | Custom prompt sent to the VLM                    |

Live captions are pushed to Nx Witness as **bookmarks** on the camera timeline. Open the
**Bookmarks** tab (Ctrl+B) in the Nx Witness client to view them.

### Loitering Detection

| **Field**                               | **Type** | **Description**                                  |
| --------------------------------------- | -------- | ------------------------------------------------ |
| **Enable Loitering Detection Pipeline** | Checkbox | Starts or stops the pipeline for this camera     |
| **Device**                              | Dropdown | Inference device: `CPU`, `GPU`, or `NPU`         |

Detection results are pushed to Nx Witness as analytics objects (bounding boxes with labels).
Use the **Object Search** panel (Alt+O) in the Nx Witness client to view detections overlaid
on the camera feed.

## Stop the Stack

```bash
docker compose down          # stop without removing data
docker compose down -v       # stop and remove PostgreSQL volume
```

## Folder Layout

```text
vms-adapter/
├── plugin/                         # Backend Python package
│   ├── base/
│   │   └── interfaces.py           #  IVmsShim + IAnalyticsAppShim abstract interfaces
│   ├── common/
│   │   └── schema_builder.py       #  Dynamic Pydantic model builder from JSON Schema
│   └── Analytics/
│       ├── api/
│       │   ├── routes/
│       │   │   ├── cameras.py      #   Camera discovery + enable/disable
│       │   │   ├── analytics_apps.py    #   Generic Analytics App API (discover, runs, stream, options)
│       │   │   ├── events.py       #   Event timeline
│       │   │   ├── analysis.py     #   Analysis result callback
│       │   │   ├── sessions.py     #   Session tracking
│       │   │   ├── vms.py          #   VMS register
│       │   │   ├── health.py       #   Health + readiness
│       │   │   └── config.py       #   Config status
│       │   └── deps.py             #   FastAPI dependency injection
│       ├── db/
│       │   └── repository.py       #   Async SQLAlchemy CRUD
│       ├── models/
│       │   ├── db.py               #   ORM models (Camera, Event, Session, …)
│       │   └── domain.py           #   Domain dataclasses
│       ├── pipeline/
│       │   └── orchestrator.py     #   Background camera sync + event processing
│       ├── config.py               #   Pydantic settings (YAML + env)
│       ├── factory.py              #   Shim factory
│       └── main.py                 #   FastAPI application entry point
│
├── vms_shim/                       # Concrete VMS shims
│   ├── frigate/
│   │   ├── shim.py                 #  FrigateVmsShim — discovers cameras via local config
│   │   └── config/                 #  Frigate config.yml (cameras, go2rtc, etc.)
│   └── nxwitness/
│       └── shim.py                 #  NxWitnessVmsShim — Nx Witness REST API v4
│
├── analytics_app_shim/                  # Concrete Analytics App shims
│   └── lvc/
│       ├── api_client.py           #  LvcApiClient — all HTTP calls to LVC backend
│       ├── schema.py               #  LvcSchemaManager — OpenAPI fetch, $ref resolution,
│       │                           #    UI annotations, Pydantic model building
│       └── shim.py                 #  LiveCaptioningAnalyticsAppShim — composes api_client + schema
│
├── ui/                             # React 19 / Vite frontend served by nginx
│   ├── src/
│   │   ├── App.jsx                 #  Root component + state
│   │   ├── components/MainPage/
│   │   │   ├── CameraDiscoveryPanel.jsx
│   │   │   ├── AnalyticsEnginePanel.jsx   # Dynamic schema form + run lifecycle
│   │   │   ├── SchemaForm.jsx             # Generic JSON Schema → form renderer
│   │   │   ├── LiveStreamTab.jsx          # WebRTC player + caption overlay
│   │   │   └── AnalysisResultsPanel.jsx
│   │   ├── hooks/
│   │   │   └── useLvcStream.js     #  SSE caption stream hook
│   │   └── services/
│   │       └── api.js              #  Generic API client functions
│   └── nginx.conf                  #  Reverse proxy: /v1 → backend, /whep → MediaMTX
│
├── config/
│   └── config.yaml                 # Runtime config (cameras, VMS endpoints, LVC URL)
├── tests/                          # pytest unit + integration tests
├── Dockerfile                      # Backend image
├── docker-compose.yml              # backend + ui + postgres
├── pyproject.toml                  # Python deps + package config
└── .env.example                    # Environment variable reference
```

## Next Steps

1. **Explore the Architecture**: Learn how VAP components interact in the
   [How It Works](./how-it-works.md) guide.
2. **Follow Integration Tutorials**: Use the [How-To Guides](./how-to-guides.md) for end-to-end
   walkthroughs of LVC and Loitering Detection integrations.
3. **Browse the API**: Explore all available endpoints in the
   [API Reference](./api-reference.md).
4. **Troubleshooting**: If you encounter issues, check the
   [Troubleshooting Guide](./troubleshooting.md).

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md
get-started/build-from-source.md
get-started/deploy-with-helm.md

:::
hide_directive-->
