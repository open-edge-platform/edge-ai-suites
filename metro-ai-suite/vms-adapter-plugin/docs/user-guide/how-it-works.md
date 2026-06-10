# How It Works

The VMS Adapter Plugin (VAP) is a modular orchestration service that routes video streams from supported VMS systems to AI analytics Analytics Apps, and relays results back to the provider dashboard or VMS.

## Architecture

```
VMS / VMS Systems
  ┌──────────┐   RTSP / REST    ┌──────────────────────────────────────────┐
  │Nx Witness├─────────────────►│                                          │
  └──────────┘                  │           VMS Adapter Plugin             │
  ┌──────────┐   RTSP / REST    │                                          │
  │ Genetec  ├─────────────────►│  FastAPI Backend    ┌──────────────────┐ │
  └──────────┘                  │  ─────────────      │  PostgreSQL DB   │ │
  ┌──────────┐   RTSP / REST    │  Orchestrator   ◄──►│  (cameras,       │ │
  │ Milestone├─────────────────►│  Camera sync        │   sessions,      │ │
  └──────────┘                  │  Schema fetch       │   events)        │ │
  ┌──────────┐   RTSP / REST    │                     └──────────────────┘ │
  │ Frigate  ├─────────────────►└────────┬─────────────────────┬───────────┘
  └──────────┘                           │                     │
                          ┌──────────────▼──────┐   ┌─────────▼──────────────┐
                          │  Live Video         │   │  DLStreamer Vision     │
                          │  Captioning (LVC)   │   │  (e.g. Loitering Det)  │
                          │                     │   │                        │
                          │  DLStreamer +VLM    │   │  DLStreamer Pipeline   │
                          │  MediaMTX (WebRTC)  │   │  Server + MQTT Broker  │
                          └──────────┬──────────┘   └────────────┬───────────┘
                                     │                           │
                          ┌──────────▼──────────────────────────▼──────────┐
                          │              Provider Dashboard (React)        │
                          │   Camera list | Run controls | Live stream     │
                          │   Caption overlay | Analysis results           │
                          └────────────────────────────────────────────────┘
```

## Data Flow

### Camera Discovery

1. Operator triggers **Discover Cameras** from the dashboard or `POST /v1/cameras/discover`.
2. The **Orchestrator** calls each registered VMS shim:
   - **NxWitnessVmsShim** queries Nx Witness `GET /rest/v4/devices` for all camera devices.
   - **FrigateVmsShim** reads camera definitions directly from `vms_shim/frigate/config/config.yml`.
3. Discovered cameras are persisted to PostgreSQL with vendor-prefixed IDs (`nx:abc123-uuid`, `frigate:front-door`).
4. The dashboard displays the full camera list. Operators enable specific cameras for analytics.

### Live Video Captioning (LVC) Flow

```
Provider dashboard
    │  POST /v1/analytics-apps/live_captioning/runs  { camera_id, prompt, model, … }
    ▼
FastAPI route (analytics_apps.py)
    │  IAnalyticsAppShim.start(params)
    ▼
LiveCaptioningAnalyticsAppShim
    │  resolves camera_id → RTSP URL via NxWitnessVmsShim / FrigateVmsShim
    │  POST /api/runs  →  LVC backend (FastAPI)
    ▼
LVC DLStreamer Pipeline Server
    │  processes RTSP stream at configured frame rate
    ├─► VLM inference → captions → MQTT broker → LVC SSE stream
    └─► preview frames → MediaMTX (WebRTC)
    ▼
VAP  GET /v1/analytics-apps/live_captioning/results/stream  (SSE proxy)
    ▼
Provider dashboard
    │  caption overlay on WebRTC video player
```

### DLStreamer Vision (dls_vision e.g. Loitering Detection) Flow

```
Provider dashboard
    │  POST /v1/analytics-apps/dls_vision/runs  { camera_id, pipeline_name, pipeline_version }
    ▼
FastAPI route (analytics_apps.py)
    │  IAnalyticsAppShim.start(params)
    ▼
ObjectDetectionAnalyticsAppShim
    │  resolves camera_id → RTSP URL via NxWitnessVmsShim
    │  POST /pipelines/{name}/{version}  →  DLStreamer Pipeline Server
    ▼
DLStreamer Pipeline Server (dls_vision)
    │  processes RTSP stream
    └─► inference results → MQTT broker  topic: /{vms_name}/dls_vision/{camera_id}
    ▼
MqttSubscriber (VAP background task)
    │  translate_dls_metadata() — DLS JSON → Nx analytics object format
    ▼
NxWitnessVmsShim.push_analytics_objects()
    │  POST /rest/v4/analytics/engines/{engine_id}/deviceAgents/{device_id}/metadata/object
    ▼
Nx Witness VMS
    └─► bounding boxes + labels overlaid on camera feed in Nx client
```

## Key Components

### VMS Shims (`vms_shim/`)

Each VMS vendor is represented by a class implementing the `IVmsShim` interface:

| **Shim**            | **Source**           | **Camera Discovery**                        |
|---------------------|----------------------|---------------------------------------------|
| `NxWitnessVmsShim`  | Nx Witness REST v4   | Queries `/rest/v4/devices`                  |
| `FrigateVmsShim`    | Frigate 0.15         | Reads local `config/config.yml` directly    |

Camera IDs are vendor-prefixed strings (`frigate:front-door`, `nx:abc123`). The orchestrator uses the prefix to dispatch RTSP URL lookups and write-backs to the correct shim.

### Analytics App Shims (`analytics_app_shim/`)

Each AI analytics application is represented by a class implementing the `IAnalyticsAppShim` interface:

| **Shim**                          | **App ID**          | **Result Delivery**                    |
|-----------------------------------|---------------------|----------------------------------------|
| `LiveCaptioningAnalyticsAppShim`       | `live_captioning`   | SSE proxy to dashboard caption overlay |
| `ObjectDetectionAnalyticsAppShim`      | `dls_vision`               | MQTT → Nx Witness analytics objects    |

Adding a new Analytics App requires only a new shim class registered in `plugin/core/factory.py`. No route changes are needed.

### FastAPI Backend (`plugin/`)

The backend exposes a generic Analytics App API at `/v1/analytics-apps/{app_id}/…` for all integrations, plus camera management, event timeline, and health endpoints. Dependency injection via `plugin/core/api/deps.py` provides shim instances to all routes.

### Orchestrator (`plugin/core/pipeline/orchestrator.py`)

The orchestrator runs at startup to:
- Construct and connect all VMS shims.
- Register analytics manifests with Nx Witness.
- Fetch Analytics App schemas (LVC OpenAPI, dls_vision pipeline list).
- Start background tasks: camera sync loop, MQTT subscriber (for dls_vision).

### Dynamic Schema (LVC)

The `LvcSchemaManager` fetches the `StartRunRequest` JSON Schema from LVC's `/openapi.json` at startup, resolves all `$ref` references, adds UI annotations, and builds a live Pydantic model. The dashboard renders analytics forms directly from this schema — no frontend changes are needed when LVC parameters change.

### MQTT Subscriber (dls_vision)

`MqttSubscriber` runs as an asyncio background task. It subscribes to `+/dls_vision/+` on the MQTT broker and receives DLStreamer GVA JSON metadata per frame. The `translate_dls_metadata()` function converts normalized bounding boxes and labels to Nx analytics object format, then `NxWitnessVmsShim.push_analytics_objects()` posts them to Nx.

### React Analytics Provider Dashboard (`ui/`)

The dashboard (React 19 + Vite + Tailwind CSS) is served by nginx, which reverse-proxies:
- `/v1/*` → FastAPI backend
- `/whep/*` → MediaMTX (WebRTC video relay)

Key panels:
- **Camera Discovery**: discover, enable, and disable cameras.
- **Analytics Engine**: select a Analytics App, fill the dynamically rendered schema form, start/stop runs.
- **Live Stream**: WebRTC video player with caption overlay (LVC).
- **Analysis Results**: timeline of metadata events.

## Extensibility

VAP is designed for extension:

- **Add a new VMS**: implement `IVmsShim` in `vms_shim/<vendor>/shim.py`, register in `factory.py`.
- **Add a new Analytics App**: implement `IAnalyticsAppShim` in `analytics_app_shim/<name>/shim.py`, register in `factory.py`. No route changes needed.

## Learn More

- [Get Started](./get-started.md)
- [System Requirements](./get-started/system-requirements.md)
- [Troubleshooting](./troubleshooting.md)
- [Release Notes](./release-notes.md)
