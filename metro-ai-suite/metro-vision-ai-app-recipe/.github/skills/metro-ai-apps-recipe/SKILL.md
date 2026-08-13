---
name: metro-ai-apps-recipe
description: >-
  Build an end-to-end, vertical-agnostic computer-vision analytics stack on
  Intel hardware from a single streamlined Docker Compose deployment: DL Streamer
  Pipeline Server plus MediaMTX/WebRTC, Coturn, Mosquitto, Node-RED, Grafana, and
  Nginx. It streams live annotated video over WebRTC and flows detection metadata
  DLSPS->MQTT->Node-RED->Grafana, with an optional SceneScape multi-camera
  spatial-analysis path. USE FOR standing up an object-detection, classification,
  counting, or zone-alerting pipeline for any vertical (smart city/ITS, retail,
  industrial, logistics, healthcare, or a custom OpenVINO/ONNX model) where only
  the model, class filter, alert rule, and dashboard change. Also USE FOR a
  lightweight **demo/PoC** single application (no full stack) — a simple DL
  Streamer pipeline (via the `dlstreamer-coding-agent` skill) or a simple
  OpenVINO inference app (guided by the OpenVINO 2026 docs) selected via the
  mode question. DO NOT USE FOR non-Intel or cloud-only deployments,
  Prometheus/OpenTelemetry metrics stacks, or training and exporting models.
license: Apache-2.0
compatibility: >-
  Requires Docker + Docker Compose v2, host with Intel CPU (and optionally
  Intel GPU/NPU with `video`/`render` groups), outbound network access to
  Docker Hub, ghcr.io, and github.com (for model + sample video downloads).
  Ports 80 and 443 (Nginx) plus 3478/udp (Coturn TURN) must be free on the
  host; WebRTC also uses MediaMTX local TCP 8189 (proxied via Nginx). Tested
  with the open-edge-platform Metro Vision AI App Recipe reference
  (v2026.1.0 image tags).
---

# Metro AI Apps Recipe — DLSPS + MediaMTX/WebRTC + Mosquitto + Node-RED + Grafana + Nginx

Build an end-to-end `{{OBJECT}}`-analytics stack on Intel hardware in
`./{{STACK_DIR}}/` with Docker Compose. The **architecture is
vertical-agnostic** — the same seven-container topology below serves any
DL Streamer / OpenVINO CV pipeline; only the invoking prompt's model,
class filter, alert rule, dashboard, and topic names differ. It follows the
open-edge-platform
[Metro Vision AI App Recipe](https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.2.0/metro-ai-suite/metro-vision-ai-app-recipe)
**MediaMTX + Coturn + WebRTC** video path but is streamlined:
**no Prometheus, no OTel**. SceneScape is **off by default**, available
as an **opt-in multi-camera spatial-analysis path** (see
[`references/SCENESCAPE.md`](references/SCENESCAPE.md)). Detection metadata
flows DLSPS→MQTT→Node-RED→Grafana; video is decoupled — DLSPS overlays
detections (`gvawatermark`) and pushes each source to MediaMTX via WHIP
(`ENABLE_WEBRTC=true`, per-source `peer-id`), Coturn provides ICE/TURN, and
Grafana embeds MediaMTX's built-in WHEP player as `<iframe>` panels at
`/mediamtx/<peer-id>/` (proxied by Nginx).

## Supported verticals & use-cases

The same stack can be instantiated for, among others:

| Vertical | Example use-cases (each = one invoking prompt) |
|---|---|
| Smart city / ITS | person/vehicle detection, ANPR, smart-parking occupancy, wrong-way |
| Retail | customer counting, queue-length, shelf out-of-stock, dwell-time |
| Industrial | surface-defect detection, PPE compliance, zone intrusion, forklift tracking |
| Logistics | pallet counting, forklift-pedestrian proximity, package damage |
| Healthcare | patient fall detection, hand-hygiene, bed occupancy, mask compliance |
| Agriculture | livestock counting, crop-disease, pest/weed identification |
| Energy & utilities | perimeter intrusion, transformer thermal, meter reading |
| Building & facilities | occupancy counting, tailgating, badge/mask compliance |
| Custom | any OpenVINO IR / ONNX detector + optional classifier |

The invoking prompt maps its vertical to concrete `{{OBJECT}}`,
`{{PIPELINE_NAME}}`, `{{DEFAULT_MODEL}}`, `{{CLASS_FILTER_IDS}}`,
`{{DEFAULT_RULE}}`, and `{{DASHBOARD_SLUG}}`. Nothing in this skill,
`docker-compose.yml`, `nginx.conf`, `mosquitto.conf`, or the test
skeleton changes across verticals.

## How to use this skill

1. Read this file end-to-end.
2. Ask **Question 0 (mode)** first. If the user selects **Demo/PoC**, branch
   immediately to the [Demo/PoC mode](#demopoc-mode) section and load
   [`references/DEMO_POC.md`](references/DEMO_POC.md) — skip questions 1–7 and
   the full-stack build entirely. Otherwise (**Full-stack production**, the
   default) continue with the steps below.
3. Ask the 7 questions in ONE batched message (defaults in brackets); accept
   `go` / `defaults` / empty to proceed. Question 7 selects the **SceneScape**
   opt-in spatial-analysis path.
4. Run parameter validation (see below). Refuse to proceed on any failure.
5. Load reference file(s) on demand per component — **do not load all up
   front**. Load [`references/SCENESCAPE.md`](references/SCENESCAPE.md) only
   when `{{SCENESCAPE}}=yes`.
6. Verify against the completion criteria before declaring success, and
   record measured throughput/latency against the baselines in `benchmark.md`.

## Reference files (load on demand)

| File | Load when authoring |
|---|---|
| [`references/PIPELINE.md`](references/PIPELINE.md) | DLSPS `config.json`, GPU/NPU variants, REST launcher, watchdog |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | `nginx.conf` (WHEP/WHIP + WebRTC-TCP proxy), Grafana WebRTC iframe panels, dashboard provisioning, Mosquitto |
| [`references/NODE_RED.md`](references/NODE_RED.md) | `flows.json`, MQTT wildcard, `gva_meta` probe, alert flow |
| [`references/INSTALL.md`](references/INSTALL.md) | `.env`, `validate_env.sh`, `install.sh`, `docker-compose.yml` (MediaMTX + Coturn) volumes |
| [`references/TESTS.md`](references/TESTS.md) | `conftest.py`, `test_webrtc_stream.py`, assertion contracts for other tests |
| [`references/SCENESCAPE.md`](references/SCENESCAPE.md) | **Only when `{{SCENESCAPE}}=yes`** — opt-in multi-camera scene-fusion path (Scene Controller + InfluxDB + Grafana Flux + Scene Management UI), delegating to the external `scenescape-setup` skill |
| [`references/DEMO_POC.md`](references/DEMO_POC.md) | **Only when `{{MODE}}=demo`** — lightweight single-app demo/PoC path: simple DL Streamer pipeline (via `dlstreamer-coding-agent`) or simple OpenVINO inference app (via OpenVINO 2026 docs); no full stack |

## Parameters (from invoking prompt)

| Param | Purpose |
|---|---|
| `{{MODE}}` | `demo` \| `production` (default `production`). `demo` selects the lightweight single-app demo/PoC path — see [`references/DEMO_POC.md`](references/DEMO_POC.md); parameters below apply only to `production` |
| `{{OBJECT}}` | class label in dashboard/alerts (e.g. `person`, `vehicle`, `hardhat`, `defect`, `fall`) — any string valid for MQTT topics and Grafana titles |
| `{{STACK_DIR}}` | e.g. `person-detect-stack`, `ppe-compliance-stack`, `retail-queue-stack`, `anpr-stack` |
| `{{DEFAULT_MODEL}}`, `{{OTHER_MODELS}}` | allowed model options |
| `{{PIPELINE_NAME}}` | canonical DLSPS pipeline `name` (e.g. `yolov11s`). Variants: `<name>`, `<name>_gpu`, `<name>_npu`. MQTT topic: `{{DETECTIONS_TOPIC_PREFIX}}_X/<name>` |
| `{{CLASSIFIER}}` | secondary model or `none`; if set, also `{{CLASSIFIER_URL}}` + `{{CLASSIFIER_XML}}` |
| `{{CLASS_FILTER_IDS}}` | JSON array of class IDs to keep (`[]`=all). Filtered in Node-RED |
| `{{DEFAULT_RULE}}` | e.g. `count>2 in 10s` |
| `{{RULE_SCOPE}}` | `per-source` \| `aggregate` (default `per-source`) |
| `{{ALERT_TOPIC}}` | e.g. `alerts/{{OBJECT}}` |
| `{{DETECTIONS_TOPIC_PREFIX}}` | e.g. `object_detection` (per-source `_1`, `_2`, …) |
| `{{COUNT_TOPIC}}` | e.g. `stats/{{OBJECT}}_count` |
| `{{LABEL_RULE_NOTE}}` | model-specific classification note for Node-RED |
| `{{DASHBOARD_SLUG}}` | e.g. `smart-parking` |
| `{{NUM_SOURCES}}` | default `4` |
| `{{SCENESCAPE}}` | `yes` \| `no` (default `no`). `yes` selects the opt-in multi-camera spatial-analysis path — see [`references/SCENESCAPE.md`](references/SCENESCAPE.md) |
| `{{SCENE_NAME}}` | (SceneScape only) human-readable scene name, e.g. `intersection-1` |
| `{{CAMERA_IDS}}` | (SceneScape only) unique IDs (no `/`), one per input stream, same order as inputs |
| `{{TURN_USER}}`, `{{TURN_PASS}}` | Coturn / MediaMTX ICE credentials (default `turnuser` / a generated secret) |

## Questions (single batched prompt)

**Question 0 — Mode** [`production`]: `demo` (lightweight single-app PoC) or
`production` (full end-to-end stack). If `demo`, STOP here and follow
[Demo/PoC mode](#demopoc-mode) / [`references/DEMO_POC.md`](references/DEMO_POC.md);
do **not** ask questions 1–7. Questions 1–7 below apply only to `production`.

1. Model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`)
2. Classifier [`{{CLASSIFIER}}`] (or `none`)
3. Device [CPU] (GPU, NPU, AUTO)
4. Inputs [{{NUM_SOURCES}}× sample-video] (or RTSP URLs / `/dev/videoN` / local paths)
5. Node-RED rule [`{{DEFAULT_RULE}}`, `{{RULE_SCOPE}}`]
6. Alert channel [MQTT `{{ALERT_TOPIC}}`]
7. SceneScape multi-camera spatial analysis? [`{{SCENESCAPE}}`, default `no`]
   (if `yes`, also collect `{{SCENE_NAME}}` and one unique `{{CAMERA_IDS}}`
   per input stream, then follow
   [`references/SCENESCAPE.md`](references/SCENESCAPE.md))

## Parameter validation (enforce BEFORE `install.sh` runs)

Ship `validate_env.sh` (body in [`references/INSTALL.md`](references/INSTALL.md))
and call as step 0 of `install.sh`. Rules:

| Param | Rule | Failure mode |
|---|---|---|
| `MODE` | `demo`\|`production` | wrong path selected |
| `HOST_IP` | `^([0-9]{1,3}\.){3}[0-9]{1,3}$`, not `0.0.0.0`/`127.0.0.1` | LAN clients can't reach Grafana |
| `NUM_SOURCES` | int, 1–16 | CPU saturates before REST launcher finishes |
| `DEVICE` | `cpu`\|`gpu`\|`npu`\|`auto` | REST 404 on missing variant |
| `PIPELINE_NAME` | `^[a-z0-9_]+$` | uppercase/hyphen breaks REST + MQTT topic |
| `CLASS_FILTER_IDS` | JSON int array, `[]` allowed | Node-RED filter throws silently |
| `RULE_SCOPE` | `per-source`\|`aggregate` | Node-RED flow undefined |
| `DEFAULT_RULE` | `^count[<>]=?\d+\s+in\s+\d+s$` | function-node syntax error |
| `*_TOPIC*` | `^[A-Za-z0-9_/-]+$`, no `#`/`+`, no leading `/` | mosquitto refuses publish |
| `VIDEO_GID`, `RENDER_GID` | int ≥ 0 | Compose rejects `group_add` |
| `TURN_USER`, `TURN_PASS` | non-empty, no space/comma | MediaMTX↔Coturn ICE auth fails → black WebRTC panel |
| `CLASSIFIER` | `none` OR (URL + XML both set) | gvaclassify fails at pipeline start |
| Inputs | `rtsp://…`, `file:///…mp4` (exists), or `/dev/video[0-9]+` (exists) | pipeline state = `ERROR` |
| `SCENESCAPE` | `yes`\|`no` | wrong path selected |
| `SCENE_NAME` | (if `SCENESCAPE=yes`) non-empty | scene create via REST fails |
| `CAMERA_IDS` | (if `SCENESCAPE=yes`) count == input streams, unique, no `/` | camera↔stream mismatch → bad fusion |

## Reference architecture

Single Docker Compose network `app_network`. Nginx publishes 80/443;
**Coturn also publishes `3478/udp`** for WebRTC TURN.

```
Browser ─HTTPS 443─▶ Nginx ─▶ /api/              → DLSPS REST
                            ├▶ /grafana/         → Grafana
                            ├▶ /nodered/         → Node-RED
                            ├▶ /mediamtx/<pid>/  → MediaMTX WHEP player (iframe)
                            ├▶ /<pid>/whep|whip  → MediaMTX WHEP/WHIP signalling
                            └▶ /webrtc/          → MediaMTX local TCP (ICE, 8189)

DLSPS ─MQTT──────────────▶ Mosquitto ─▶ Node-RED ─▶ Grafana (mqtt datasource)
DLSPS ─WebRTC/WHIP───────▶ MediaMTX (peer-id={{DETECTIONS_TOPIC_PREFIX}}_N) ◀─ICE/TURN─ Coturn (3478/udp)
                              │
                         Grafana <iframe src="/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_N/">
```

## Demo/PoC mode

When Question 0 selects `demo`, **do not build the full stack** — no Docker
Compose topology, no MediaMTX/Coturn/Node-RED/Grafana/Nginx, no SceneScape.
Instead produce a single lightweight application that proves a model runs on
Intel hardware and emits inference output. Two sub-paths (ask the user which):

- **DL Streamer app** — a simple DL Streamer / GStreamer pipeline (detect and
  overlay/print results). Delegate to the `dlstreamer-coding-agent` skill.
- **OpenVINO app** — a minimal Python inference script using the OpenVINO
  runtime (load → `compile_model` → infer → post-process). No dedicated skill
  exists; follow the OpenVINO 2026 docs.

Full authoring guidance, delegation details, and the lightweight completion
criteria live in [`references/DEMO_POC.md`](references/DEMO_POC.md) — load it
only on this branch. The production completion criteria (1–11 below) do **not**
apply in demo mode.

## SceneScape spatial-analysis path (optional, `{{SCENESCAPE}}=yes`)

When Question 7 selects SceneScape, **branch** off the default recipe: keep the
DLSPS detection pipeline but replace the MediaMTX/WebRTC + Node-RED + Grafana-MQTT
tail with an Intel® SceneScape multi-camera scene-fusion stack (smart-intersection
style). **Do not re-implement it by hand** — delegate to the external
`scenescape-setup` skill, passing `{{SCENE_NAME}}` and `{{CAMERA_IDS}}`. Full
architecture, images, validation, and completion criteria live in
[`references/SCENESCAPE.md`](references/SCENESCAPE.md); load it only on this
branch. The default (`{{SCENESCAPE}}=no`) path is unchanged.

## Images — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published tag on Docker Hub** before
generating the stack (e.g. `curl -s "https://hub.docker.com/v2/repositories/<repo>/tags?page_size=25&ordering=last_updated"`),
then pin that concrete version — never the floating `:latest`. Refresh the
versions below if newer stable ones exist. **Grafana is the one exception:** it
MUST stay pinned to `11.5.4` because the MQTT datasource plugin only works on
that tag.

- `intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24` (latest **stable** DL Streamer release; check Docker Hub for a newer stable — ignore `*-weekly` pre-releases)
- `eclipse-mosquitto:2.1.2-alpine`
- `nodered/node-red:5.0.4`
- `nginx:1.31.3-alpine`
- `bluenviron/mediamtx:1.20.0` (WebRTC server; WHIP in from DLSPS, WHEP out to browser)
- `coturn/coturn:4.17.0` (ICE/TURN signalling for WebRTC)
- `grafana/grafana:11.5.4` (**pinned — do not upgrade**, MQTT plugin only works on this tag) with `GF_INSTALL_PLUGINS="grafana-mqtt-datasource 1.3.3,yesoreyeram-infinity-datasource 3.11.1"`
  (verify each plugin version exists via `curl -s https://grafana.com/api/plugins/<slug>/versions | jq '.items[].version'` — `plugin.versionNotFound` kills the container and Nginx returns 502)
- `intel/dlstreamer:2026.1.0-ubuntu24` (latest **stable**; one-shot in `install.sh` for model download + INT8 quantize + TLS cert)

## Layout (flat)

```
{{STACK_DIR}}/
├── README.md
├── docker-compose.yml
├── .env
├── validate_env.sh
├── install.sh                     # HOST_IP, GIDs, model dl+INT8, videos, cert
├── sample_start.sh                # POST N pipelines + start watchdog
├── sample_stop.sh                 # kill watchdog + DELETE pipelines
├── sample_status.sh               # GET /api/pipelines/status
├── sample_watchdog.sh             # respawn COMPLETED file-source pipelines
├── update_dashboard.sh            # rewrite WEBRTC_URL → https://<HOST>/mediamtx/
├── src/
│   ├── dlstreamer-pipeline-server/{config.json, models/, videos/}
│   ├── mosquitto/config/mosquitto.conf
│   ├── node-red/{flows.json, install_package.sh, public/}
│   ├── grafana/{dashboards.yml, datasources.yml, dashboards/{{DASHBOARD_SLUG}}.json}
│   └── nginx/{nginx.conf, ssl/{server.crt, server.key}}
└── tests/
    ├── conftest.py
    ├── test_stack_up.py
    ├── test_pipeline_running.py
    ├── test_mqtt_detections.py
    ├── test_webrtc_stream.py
    ├── test_nodered_alert.py
    ├── test_grafana_mqtt_data.py
    └── test_grafana_dashboard_content.py   # video iframes + MQTT connected on dashboard
```

## Template variable substitution

Every `{{VAR}}` in code blocks (JSON/YAML/shell/Python/HTML/nginx) MUST be
substituted with its concrete value BEFORE writing the file — literal
`{{...}}` left in `nginx.conf`, `config.json`, `flows.json`, the dashboard
JSON, or the test files is a syntax error.

## Execution guardrails

- Hard timeouts: model dl+INT8 300 s; video dl 120 s/file; `compose pull`
  300 s; `compose up -d` 120 s + 180 s healthy; each pytest 60 s.
- Max 2 retries per step, then STOP and print last 30 log lines from the
  failing container. Never loop.
- Before `compose up`: `ss -ltn` must show `:80` and `:443` free, and
  `ss -lun` must show `:3478` free (Coturn TURN).
- **Bypass host proxy for all localhost/LAN curl** — corporate
  `http_proxy`/`https_proxy` routes `https://localhost/...` through an
  unreachable proxy (→ `Could not resolve host` / 502). Every curl in
  `sample_*.sh` MUST use `--noproxy '*'` (and `-k` for the self-signed
  cert); tests set `NO_PROXY=*` in `conftest.py`.
- Test WebRTC signalling: `curl -k --noproxy '*' -sf -o /dev/null -w '%{http_code}' https://<HOST>/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_1/` (expect `200`, the WHEP player page; the stream exists only after `sample_start.sh` runs).
- Test MQTT: `docker run --rm --network <project>_app_network eclipse-mosquitto:2.1.2-alpine mosquitto_sub -h broker -t '#' -v`.
- pytest venv at `./.venv` inside stack dir (`python -m venv .venv`) —
  system pip is PEP-668 blocked; `/tmp` may be `noexec`.

## Optional external skills

If available in the session, invoke; otherwise write files from the reference
templates.
- `dlstreamer-coding-agent` — pipeline JSON authoring (also the **demo/PoC** DL Streamer single-app path when `{{MODE}}=demo`)
- `dlsps-user` (open-edge-platform/skills) — DL Streamer Pipeline Server deploy/config/REST operations; invoke when building the **full-stack multi-microservice** app that runs DLSPS (this recipe's default `{{MODE}}=production` path — see [`references/PIPELINE.md`](references/PIPELINE.md))
- `model-download` (open-edge-platform/edge-ai-libraries) — OMZ model IR
- `scenescape-setup` (open-edge-platform/skills) — **only when `{{SCENESCAPE}}=yes`**; orchestrates the multi-camera SceneScape deploy (see [`references/SCENESCAPE.md`](references/SCENESCAPE.md))

## Reference implementation

The upstream
[`smart-parking/src/`](https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.2.0/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking/src)
recipe uses the same MediaMTX + Coturn + WebRTC path. Consult it for
`config.json`, `mosquitto.conf`, `nginx.conf`, `datasources.yml`,
`dashboards.yml`, and `flows.json` shapes; drop `prometheus`,
`otel-collector`, and `metrics-manager` when streamlining.

## Completion criteria (all must pass)

> When `{{SCENESCAPE}}=yes`, criteria 3–11 are **superseded** by the
> SceneScape-branch criteria in
> [`references/SCENESCAPE.md`](references/SCENESCAPE.md); criteria 1–2 still apply.

1. `./install.sh` succeeds: `.env` populated; INT8 model + optional
   classifier IR under `src/dlstreamer-pipeline-server/models/…`; videos
   downloaded; TLS cert with SAN generated.
2. `./validate_env.sh cpu` exits 0 with a valid `.env`;
   `HOST_IP=127.0.0.1 ./validate_env.sh cpu` exits non-zero.
3. `docker compose up -d` → all containers `running` / `healthy`
   (including `mediamtx-server` and `coturn`).
4. `curl -k https://localhost/api/pipelines/status` returns 3 variants.
5. `./sample_start.sh <cpu|gpu|npu>` launches `{{NUM_SOURCES}}` pipelines;
   none `QUEUED`, all `RUNNING`.
6. Detections arrive on
   `{{DETECTIONS_TOPIC_PREFIX}}_1..{{NUM_SOURCES}}/{{PIPELINE_NAME}}`
   (or `_gpu`/`_npu`) within 30 s.
7. `curl -k https://localhost/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_1/`
   returns 200 (WHEP player HTML) once pipelines are running; MediaMTX
   logs show the WHIP publisher connected for each `peer-id`
   `{{DETECTIONS_TOPIC_PREFIX}}_1..{{NUM_SOURCES}}`.
8. Node-RED publishes JSON `{{ALERT_TOPIC}}` and **scalar**
   `{{COUNT_TOPIC}}` / `stats/alert_active` / `stats/alert_total` per
   `{{RULE_SCOPE}}`. `mosquitto_sub -t '{{COUNT_TOPIC}}/#' -C 1` MUST
   parse as `int()` — JSON here silently breaks Grafana plotting.
9. Grafana at `https://localhost/grafana` (admin/admin) shows live
   {{OBJECT}} counts + alert data and `{{NUM_SOURCES}}` `<iframe>` WebRTC
   panels playing the annotated streams (needs
   `GF_SECURITY_ALLOW_EMBEDDING=true`). The MQTT datasource health endpoint
   (`/grafana/api/datasources/uid/mqtt_ds/health`) MUST return
   `"MQTT Connected"` — the broker address goes in **`jsonData.uri`**
   (`tcp://broker:1883`), NOT `url:` or `jsonData.host/port` (ignored →
   blank panels). If the dashboard root redirect-loops, drop the trailing
   slash from the `/grafana/` `proxy_pass`.
10. `pytest -q tests/` passes. `pytest --collect-only -q tests/ | tail -1`
    reports ≥ 9 tests collected (no empty stub files).
11. **Watchdog continuity** (file:// sources): after `video-length + 30 s`,
    `/api/pipelines/status` shows `{{NUM_SOURCES}}` `RUNNING` (`COMPLETED`
    history entries are fine), WebRTC re-establishes (same `peer-id`), MQTT
    still flowing. >`{{NUM_SOURCES}}` `RUNNING` means the watchdog dedup
    guard is missing.
