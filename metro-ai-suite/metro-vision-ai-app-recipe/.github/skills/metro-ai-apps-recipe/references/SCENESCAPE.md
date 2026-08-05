# SceneScape spatial-analysis path (optional, opt-in)

Load this file **only when `{{SCENESCAPE}}=yes`**. It replaces the
MediaMTX/WebRTC + Node-RED-alert + Grafana-MQTT *video/analytics tail* of
the default recipe with an Intel® **SceneScape** multi-camera
**scene-fusion** stack, modeled on the open-edge-platform
[smart-intersection](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection)
reference application.

**Do not reproduce the SceneScape orchestration by hand.** SceneScape ships a
self-contained deployer skill that gathers streams/camera-ids/scene-name and
runs bootstrap → calibrate → scene → tracking verification. Delegate to it:

> External skill:
> `https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup`
> (`SKILL.md` — orchestrator `scripts/deploy_scenescape.sh`).

If that skill is available in the session, **invoke it** and pass the
SceneScape parameters below. If it is not reachable, fall back to authoring the
compose from the smart-intersection service shapes documented here.

## When to choose this path

Choose SceneScape when the use-case needs **spatial** analytics that a single
per-camera pipeline cannot give:

- Multi-camera **multi-object tracking** — one object identity fused across
  overlapping camera views.
- **Scene-based regions of interest** defined once on a map/floorplan (not
  per-camera), e.g. crosswalks, lanes, zones.
- 3-D motion analytics — speed/heading, dwell time, object interactions.
- Mixed sensors (camera + lidar/radar) feeding one scene.

If the use-case is single-camera count/alert only, keep `{{SCENESCAPE}}=no`
(the default) and use the standard MediaMTX/WebRTC + Node-RED path.

## Architecture (SceneScape branch)

Detection metadata still flows out of DLSPS over MQTT, but a **Scene
Controller** fuses it into scene tracks, and aggregate ROI analytics land in
**InfluxDB** for **Grafana Flux** dashboards. Live fused tracks are viewed in
the **Scene Management UI**, not in Grafana WebRTC iframes.

```
Cameras (N, unique camera_ids) ─RTSP─▶ DLSPS ─MQTT─▶ broker (mosquitto, TLS)
                                                        │
              scene DB (postgres) ◀── Scene Mgmt API ──┤
                                                        ▼
   ntpserver (chrony) ──sync──▶  scene (Scene Controller)  ──fused tracks + ROI events──▶ broker
                                        ▲                                                   │
                                 tracker-config.json                                       ▼
                                                                              node-red ─▶ InfluxDB (Flux)
   Browser ─HTTPS 443─▶ nginx ─▶ /              → web (Scene Management UI)                  │
                              ├▶ /grafana/      → Grafana (InfluxDB datasource) ◀────────────┘
                              └▶ /nodered/      → Node-RED
```

The `web` (SceneScape manager) service serves the Scene Management UI + REST
scene API and owns scene calibration, camera poses, and regions of interest.

## Pinned images (from the smart-intersection reference)

- `intel/scenescape-controller:2026.1.0` — **scene** (multi-camera fusion, `tracker-config.json`)
- `intel/scenescape-manager:2026.1.0` — **web** (Scene Management UI + REST scene API, Django)
- `postgres:17.6` — **pgserver** (scene database)
- `influxdb:2.7.11` — **influxdb2** (time-series ROI analytics; Flux queries)
- `grafana/grafana:11.6.0` — Grafana with the **InfluxDB** datasource (not the MQTT datasource)
- `nodered/node-red:5.0.4` — MQTT → InfluxDB bridge
- `eclipse-mosquitto:2.1.2-alpine` — **broker** (secured with TLS certs)
- `dockurr/chrony:4.6.1` — **ntpserver** (synchronized timestamps for fusion)
- `nginx:1.31.3-alpine` — TLS reverse proxy (80/443)
- `${DLSTREAMER_PIPELINE_SERVER_IMAGE}` — DLSPS object detection → MQTT

No MediaMTX, Coturn, or WebRTC in this branch; no Prometheus/OpenTelemetry.

## Parameters (SceneScape branch)

Supplied by the invoking prompt when `{{SCENESCAPE}}=yes`:

| Param | Purpose |
|---|---|
| `{{SCENESCAPE}}` | `yes` \| `no` (default `no`). `no` → standard recipe, ignore this file |
| `{{SCENE_NAME}}` | Human-readable scene name, e.g. `intersection-1` |
| `{{CAMERA_IDS}}` | Unique IDs (no `/`), one per input stream, same order as inputs |
| `{{NUM_SOURCES}}` | number of cameras/streams feeding the scene (≥1; ≥2 for cross-camera fusion) |

`{{OBJECT}}`, `{{DEFAULT_MODEL}}`, `{{PIPELINE_NAME}}`, `{{DEVICE}}`, and the
input streams carry over from the standard parameter set — the DLSPS detection
pipeline is the same; only the downstream fusion/analytics/UI differ.

## Parameter validation (enforce when `{{SCENESCAPE}}=yes`)

| Param | Rule | Failure mode |
|---|---|---|
| `SCENE_NAME` | non-empty | Scene create via REST fails |
| `CAMERA_IDS` | count == number of input streams, unique, no `/` | fusion maps wrong camera → bad tracks |
| `NUM_SOURCES` | int ≥ 1 (≥ 2 recommended for cross-camera tracking) | no fusion benefit with a single view |
| Inputs | one RTSP/RTSPS URL (or local video file) per `camera_id`, same order | camera↔stream mismatch |

The external `scenescape-setup` skill re-validates these; still assert them
before handing off, and state that `camera_ids` uniqueness was checked.

## How to run (delegate first)

1. Confirm `{{SCENESCAPE}}=yes`, and that `{{SCENE_NAME}}`, `{{CAMERA_IDS}}`,
   and the per-camera input streams are known.
2. **Preferred:** invoke the external `scenescape-setup` skill with
   `deploy_dir=./{{STACK_DIR}}`, `scene_name={{SCENE_NAME}}`,
   `camera_ids={{CAMERA_IDS}}`, and `streams=<inputs>`. It orchestrates
   bootstrap → calibrate → scene, launches services async, captures one
   calibration frame per `camera_id`, reconstructs the scene, and verifies
   multi-camera tracking. Do not re-implement its steps.
3. **Fallback (skill unavailable):** author `docker-compose.yml` from the
   smart-intersection service shapes above (services `ntpserver`, `broker`,
   `node-red`, `influxdb2`, `grafana`, `dlstreamer-pipeline-server`,
   `pgserver`, `web`, `scene`, `nginx` on one `scenescape` network, with TLS
   secrets and the `tracker-config.json` config), pulling the concrete files
   from
   [smart-intersection/src](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/src)
   (`controller/`, `webserver/`, `grafana/`, `node-red/`, `mosquitto/`,
   `nginx/`, `dlstreamer-pipeline-server/`, `secrets/`).

## Completion criteria (SceneScape branch — all must pass)

1. All services `running`/`healthy`, including `scene`, `web`, `pgserver`,
   `influxdb2`, `ntpserver`.
2. Scene Management UI reachable at `https://localhost/` and the scene
   `{{SCENE_NAME}}` exists with the calibrated cameras `{{CAMERA_IDS}}`.
3. DLSPS publishes detections to the secured broker; the Scene Controller
   publishes **fused tracks** and ROI events back to MQTT.
4. Tracking verification: at least one tracked object is associated with **more
   than one `camera_id`** (for `{{NUM_SOURCES}} ≥ 2`).
5. ROI/aggregate analytics land in InfluxDB and render in the Grafana dashboard
   at `https://localhost/grafana/` (InfluxDB datasource, Flux queries).
6. When delegated to the external skill, it reports `DEPLOY COMPLETE` with a
   `scene_uid`.
