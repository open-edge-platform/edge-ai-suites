# Get Started

## Overview

The **VMS Adapter Plugin (VAP)** bridges VMS systems (Nx Witness, Genetec, Milestone, etc.) with AI Analytics Apps (Live Video Captioning (LVC), DLStreamer vision analytics app like Loitering Detection) and provides a unified React based provider dashboard for managing cameras and analytics runs. This guide shows how to deploy the full stack with Docker Compose and run your first analytics session.

Note: Frigate is used as an open-source proxy for limited VMS capabilities as a means to demonstrate the VAP capabilities. 

This guide shows how to:

- **Set up prerequisites**: Start LVC or DLS vision analytics (Loitering Detection) before VAP, since VAP fetches their schemas at startup.
- **Configure the environment**: Point VAP at your VMS and Analytics App services.
- **Run the provider dashboard**: Discover cameras, enable streams, and start analytics runs.

## Quick Start

Check the [folder layout](#folder-layout) to familiarize with the code structure.

### Prerequisites

- Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose: [Installation Guide](https://docs.docker.com/compose/install/).
- One or more of the following running and reachable:
  - **Nx Witness** VMS with accessible REST API (`NX_HOST`, `NX_USERNAME`, `NX_PASSWORD`). This document does not intend to provide reference on setup of Nx Witness and Nx Cloud.
  - **Frigate** VMS with cameras configured (RTSP streams). Refer to [usage](#41-install-frigate) instructions for a quick guide on how to deploy, configure camera, and use Frigate.
- At least one Analytics App running before VAP starts:
  - **Live Video Captioning (LVC)** — for VLM based AI captioning
  - **Loitering Detection (DLS vision based)** — for real-time detection of loitering behavior in transportation hubs with Nx write-back

---

## Step 1 — Start Live Video Captioning (LVC)

> Skip this step if you are only using Loitering Detection.

Clone and start the LVC application from its own directory. LVC must be running before VAP starts, because VAP fetches the LVC OpenAPI schema at startup to build the analytics configuration form.

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/live-video-captioning
```

Follow the [LVC Get Started guide](../../../live-video-analysis/live-video-captioning/docs/user-guide/quick-start-guide.md) to prepare models and configure the environment, then start the stack:

```bash
docker compose up -d
```

Verify LVC is reachable:

```bash
curl http://localhost:4173/health
```

---

## Step 2 — Start Loitering Detection

> Skip this step if you are only using Live Video Captioning.

Loitering Detection is a user-provided application based on the Intel DLStreamer Pipeline Server. Bring up the application according to its own documentation. The following services must be reachable from the VAP backend container:

| **Service**              | **Default Port** | **Purpose**                            |
|--------------------------|------------------|----------------------------------------|
| DLStreamer Pipeline Server | `8080`         | Receive pipeline start/stop commands   |
| MQTT Broker              | `1883`           | Publish inference metadata to VAP      |

Verify the DLStreamer Pipeline Server is reachable:

```bash
curl http://<LOITERING_DETECTION_HOST>:8080/pipelines
```

---

## Step 3 — Clone VAP and Create the `.env` File

```bash
cd metro-ai-suite/vms-adapter-plugin
cp .env.example .env
```

Open `.env` and update the variables for your environment:

| **Variable**                         | **Description**                                                          |
|--------------------------------------|--------------------------------------------------------------------------|
| `LVC_BASE_URL`                       | URL of the running LVC backend, e.g. `http://<lvc-host>:4173`            |
| `MEDIAMTX_URL`                       | URL of the MediaMTX WebRTC server, e.g. `http://<lvc-host>:8889`         |
| `FRIGATE_HOST`                       | Hostname/IP of the Frigate instance reachable from the backend container |
| `NX_BASE_URL` / `NX_USERNAME` / `NX_PASSWORD` | Nx Witness credentials (only if using Nx)                       |
| `NX_TLS_VERIFY` / `NX_CA_BUNDLE` | Nx TLS verification toggle and optional CA bundle path (default: `false`) |
| `LOITERING_DET_HOST` / `LOITERING_DET_PORT`              | DLStreamer Pipeline Server host and port for Loitering Detection app (default: `8080`)       |
| `DLS_VISION_TLS_VERIFY` / `DLS_VISION_CA_BUNDLE` | DLStreamer TLS verification toggle and optional CA bundle path (default: `false`) |
| `MQTT_HOST` / `MQTT_PORT`            | MQTT broker host and port for dls_vision metadata (default: `1883`)             |
| `MQTT_TLS_ENABLED` / `MQTT_CA_BUNDLE` / `MQTT_CLIENT_CERT` / `MQTT_CLIENT_KEY` | MQTT TLS, CA bundle, and optional mutual TLS client certificate for the dls_vision subscriber |
| `MQTT_BROKER_TLS_ENABLED` / `MQTT_BROKER_CA_BUNDLE` / `MQTT_BROKER_CLIENT_CERT` / `MQTT_BROKER_CLIENT_KEY` | MQTT TLS, CA bundle, and optional mutual TLS client certificate for the LVC broker subscriber |
| `PG_PASSWORD`                        | PostgreSQL password (change from default)                                |
| `UI_HTTPS_PORT`                      | Host port for the dashboard HTTPS (`3443`)                              |

> If LVC or Loitering Detectopm is running on the same host as VAP, use `host.docker.internal` (Linux/Mac). Otherwise, use the actual IP address.

For certificate path examples and TLS behavior details, see [TLS and Certificate Configuration](./how-to-guides/tls-and-certificates.md).

---

## Step 4 — Start Frigate (only if using Frigate)

> Skip this step if you are not using Frigate as your VMS.

Frigate is **not** included in the VAP Docker Compose stack. You must install, configure, and start it separately before bringing up VAP.

### 4.1 Install Frigate

Follow the [official Frigate installation guide](https://docs.frigate.video/frigate/installation). The recommended approach is Docker:

```bash
docker run -d \
  --name frigate \
  --restart=unless-stopped \
  --shm-size=256m \
  -p 5000:5000 \
  -p 8554:8554 \
  -v /path/to/your/frigate/config:/config \
  -v /etc/localtime:/etc/localtime:ro \
  ghcr.io/blakeblackshear/frigate:0.15.1
```

Or use Frigate's own compose file from the [Frigate documentation](https://docs.frigate.video/frigate/installation/#docker-compose).

### 4.2 Configure Cameras

Edit your Frigate `config.yml` to add camera RTSP streams. Add each camera to **both** the `go2rtc.streams:` and `cameras:` sections — VAP discovers cameras via Frigate's `GET /api/go2rtc/streams` API:

```yaml
go2rtc:
  streams:
    front-door:
      - rtsp://user:pass@192.168.1.10:554/stream
    warehouse-cam:
      - rtsp://user:pass@192.168.1.11:554/stream

cameras:
  front-door:
    ffmpeg:
      inputs:
        - path: rtsp://user:pass@192.168.1.10:554/stream
          roles:
            - detect
  warehouse-cam:
    ffmpeg:
      inputs:
        - path: rtsp://user:pass@192.168.1.11:554/stream
          roles:
            - detect
```

- The key under `go2rtc.streams:` (e.g. `front-door`) becomes the camera name in the VAP dashboard.
- VAP builds RTSP URLs as `rtsp://<FRIGATE_HOST>:8554/<stream_name>`.
- Both `go2rtc.streams` and `cameras` entries must use the **same key name**.
- Refer to the [Frigate configuration docs](https://docs.frigate.video/configuration/) for the full YAML schema.

### 4.3 Verify Frigate is Running

```bash
curl http://localhost:5000/api/go2rtc/streams
```

You should see a JSON object listing your configured streams. Then set `FRIGATE_HOST` in your `.env` to point VAP at the running Frigate instance (use `host.docker.internal` if Frigate is on the same host as VAP).

---

## Step 5 — Build and Start VAP

```bash
docker compose up -d --build
```

Wait for all services to become healthy:

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
curl -k https://localhost:3443/v1/health
```

---

## Step 6 — Open the Provider Dashboard


| **Service**             | **URL**                            |
|-------------------------|------------------------------------|
| Provider Dashboard (HTTPS) | `https://localhost:3443`        |
| API Docs (Swagger UI)   | `https://localhost:3443/docs`      |
| OpenAPI JSON            | `https://localhost:3443/openapi.json` |

> **Note:** The dashboard uses HTTPS by default with a self-signed certificate. Your browser will show a security warning on first access — this is expected. To use your own certificate, copy `docker-compose.tls.yml` to `docker-compose.override.yml` and place `cert.pem` and `key.pem` in `./certs/ui/`.

> **Swagger Docs:** VAP serves API docs through the UI nginx proxy. Open `https://localhost:3443/docs` to browse endpoints and `https://localhost:3443/openapi.json` for the raw OpenAPI schema.

---

## Step 7 — Discover Cameras

In the dashboard, click **Discover Cameras** to sync cameras from all connected VMS systems. You can also trigger discovery via the API:

```bash
curl -k -X POST https://localhost:3443/v1/cameras/discover
```

The backend queries all configured VMS shims (Frigate, Nx Witness) and persists discovered cameras to PostgreSQL.

---

## Step 8 — Enable Cameras and Start Analytics

1. In the **Camera Discovery** panel, enable the cameras you want to use for analytics.
2. In the **Analytics Engine** panel, select a Analytics App (for example, **Live Video Captioning** or **Loitering Detection**).
3. Configure the analytics parameters (model, prompt, pipeline, and so on) and click **Start Run**.
4. View live captions or detection results in the **Live Stream** and **Analysis Results** panels.

### Live Video Captioning

Configure the following fields in the dashboard:

| **Field**         | **Description**                                     | **Default**                              |
|-------------------|-----------------------------------------------------|------------------------------------------|
| Camera            | Dropdown of enabled cameras                         | —                                        |
| Enter Prompt      | VLM prompt for captioning                           | "Describe what you see in one sentence." |
| Select Model      | VLM model from LVC                                  | OpenGVLab/InternVL2-2B                   |
| Max New Tokens    | Maximum caption length                              | 70                                       |
| Select Pipeline   | DLStreamer pipeline configuration                   | —                                        |
| Run Name          | Display name for this run                           | —                                        |
| Frame Rate        | Frames per second sent for inference                | 1                                        |
| Chunk Size        | Number of frames per inference chunk                | 1                                        |
| Frame Resolution  | Resolution preset sent to LVC                       | default                                  |

Live captions are streamed via SSE and displayed in the dashboard caption overlay on the WebRTC video player.

### Loitering Detection (DLStreamer vision based app)

Configure the following fields in the dashboard:

| **Field**         | **Description**                                     |
|-------------------|-----------------------------------------------------|
| Camera            | Dropdown of enabled cameras (Nx Witness cameras)    |
| Pipeline Name     | DLStreamer pipeline template to use                 |
| Pipeline Version  | Version of the pipeline template                    |

Detection results are pushed directly back to Nx Witness as analytics objects (bounding boxes with labels). Use the Nx Witness client to view detections overlaid on the camera feed.

---

## Stop the Stack

```bash
docker compose down          # stop without removing data
docker compose down -v       # stop and remove PostgreSQL volume
```

## Folder Layout

```
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
├── docker-compose.yml              # backend + ui + postgres + frigate
├── pyproject.toml                  # Python deps + package config
└── .env.example                    # Environment variable reference
```


## Next Steps

1. **Explore the Architecture**: Learn how VAP components interact in the [How It Works](./how-it-works.md) guide.
2. **Follow Integration Tutorials**: Use the [How-To Guides](./how-to-guides.md) for end-to-end walkthroughs of LVC and Loitering Detection integrations.
3. **Browse the API**: Explore all available endpoints in the [API Reference](./api-reference.md).
4. **Troubleshooting**: If you encounter issues, check the [Troubleshooting Guide](./troubleshooting.md).

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md
get-started/build-from-source.md
get-started/deploy-with-helm.md

:::
hide_directive-->
