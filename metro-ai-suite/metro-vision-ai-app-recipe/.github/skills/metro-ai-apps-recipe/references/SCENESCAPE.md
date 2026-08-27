# Scenescape Spatial Analysis Path (optional, opt-in)

Load **only when `{{SCENESCAPE}}=yes`**. Replaces default MediaMTX/WebRTC + Node-RED-alert + Grafana-MQTT *video/analytics tail* with Intel® **Scenescape** multi-camera **scene-fusion**, based on [smart-intersection](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection).

**Do not reproduce Scenescape orchestration by hand.** Delegate to its deployer skill; it gathers streams/camera-ids/scene-name and runs bootstrap → calibrate → scene → tracking verification:

> External skill:
> `https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup`
> (`SKILL.md` — orchestrator `scripts/deploy_scenescape.sh`).

If available, **invoke it** with parameters below; otherwise use smart-intersection service shapes here.

## When to choose this path

Choose Scenescape for **spatial** analytics unavailable per camera:

- Multi-camera **multi-object tracking** — one identity fused across overlapping views.
- **Scene-based regions of interest** defined once on a map/floorplan (not per-camera), e.g. crosswalks, lanes, zones.
- 3-D motion analytics — speed/heading, dwell time, interactions.
- Mixed sensors (camera + lidar/radar) feeding one scene.

For single-camera count/alert, keep `{{SCENESCAPE}}=no` (default) and standard MediaMTX/WebRTC + Node-RED.

## Architecture (Scenescape branch)

DLSPS still publishes detections over MQTT. **Scene Controller** fuses tracks; ROI analytics go to **InfluxDB** for **Grafana Flux**; live fused tracks appear in **Scene Management UI**, not Grafana WebRTC iframes.

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

`web` (Scenescape manager) serves UI + REST scene API and owns calibration, camera poses, and ROIs.

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

No MediaMTX, Coturn, WebRTC, Prometheus, or OpenTelemetry.

## Parameters (Scenescape branch)

When `{{SCENESCAPE}}=yes`:

| Param | Purpose |
|---|---|
| `{{SCENESCAPE}}` | `yes` \| `no` (default `no`). `no` → standard recipe, ignore this file |
| `{{SCENE_NAME}}` | Human-readable scene name, e.g. `intersection-1` |
| `{{CAMERA_IDS}}` | Unique IDs (no `/`), one per input stream, same order as inputs |
| `{{NUM_SOURCES}}` | number of cameras/streams feeding the scene (≥1; ≥2 for cross-camera fusion) |

`{{OBJECT}}`, `{{DEFAULT_MODEL}}`, `{{PIPELINE_NAME}}`, `{{DEVICE}}`, and input streams carry over; only downstream fusion/analytics/UI differ.

## Parameter validation (enforce when `{{SCENESCAPE}}=yes`)

| Param | Rule | Failure mode |
|---|---|---|
| `SCENE_NAME` | non-empty | Scene create via REST fails |
| `CAMERA_IDS` | count == number of input streams, unique, no `/` | fusion maps wrong camera → bad tracks |
| `NUM_SOURCES` | int ≥ 1 (≥ 2 recommended for cross-camera tracking) | no fusion benefit with a single view |
| Inputs | one RTSP/RTSPS URL (or local video file) per `camera_id`, same order | camera↔stream mismatch |

`scenescape-setup` re-validates; still assert before handoff and state `camera_ids` uniqueness was checked.

## How to run (delegate first)

1. Confirm `{{SCENESCAPE}}=yes`, and that `{{SCENE_NAME}}`, `{{CAMERA_IDS}}`, and per-camera input streams are known.
2. **Preferred:** invoke external `scenescape-setup` with `deploy_dir=./{{STACK_DIR}}`, `scene_name={{SCENE_NAME}}`, `camera_ids={{CAMERA_IDS}}`, and `streams=<inputs>`. It runs bootstrap → calibrate → scene, launches services async, captures one calibration frame per `camera_id`, reconstructs scene, and verifies tracking. Do not re-implement.
3. **Fallback (skill unavailable):** author `docker-compose.yml` from smart-intersection service shapes above (services `ntpserver`, `broker`, `node-red`, `influxdb2`, `grafana`, `dlstreamer-pipeline-server`, `pgserver`, `web`, `scene`, `nginx` on one `scenescape` network, with TLS secrets and `tracker-config.json`), pulling files from [smart-intersection/src](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/src) (`controller/`, `webserver/`, `grafana/`, `node-red/`, `mosquitto/`, `nginx/`, `dlstreamer-pipeline-server/`, `secrets/`).

## Completion criteria (Scenescape branch — all must pass)

1. All services `running`/`healthy`, including `scene`, `web`, `pgserver`, `influxdb2`, `ntpserver`.
2. Scene Management UI reachable at `https://localhost/`; scene `{{SCENE_NAME}}` exists with calibrated cameras `{{CAMERA_IDS}}`.
3. DLSPS publishes detections to secured broker; Scene Controller publishes **fused tracks** and ROI events back to MQTT.
4. Tracking verification: at least one tracked object is associated with **more than one `camera_id`** (for `{{NUM_SOURCES}} ≥ 2`).
5. ROI/aggregate analytics land in InfluxDB and render in Grafana at `https://localhost/grafana/` (InfluxDB datasource, Flux).
6. When delegated, external skill reports `DEPLOY COMPLETE` with `scene_uid`.
