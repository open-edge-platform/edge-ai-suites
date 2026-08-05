---
name: metro-ai-apps-recipe
description: >-
  Build an end-to-end computer-vision analytics stack on Intel hardware in the spirit of the open-edge-platform Metro Vision AI App Recipe, in a streamlined single-compose form that   streams live annotated video over WebRTC via MediaMTX + Coturn (as in the upstream smart-parking recipe) but drops Prometheus and OpenTelemetry; SceneScape is off by default but available as an opt-in multi-camera spatial-analysis path (smart-intersection style). The **architecture is vertical-agnostic**: the same DLSPS + MediaMTX/WebRTC + Mosquitto + Node-RED + Grafana + Nginx stack serves any DL Streamer / OpenVINO computer-vision pipeline. Only the invoking prompt changes — model, class filter, alert rule, dashboard slug, and topic names differ per use-case. Reference verticals include (non-exhaustive) smart-city / ITS (person detection, vehicle detection & ANPR, smart-parking occupancy, pedestrian safety, traffic-flow counting, wrong-way detection), retail (customer counting, queue-length, shelf-out-of-stock, loss-prevention, dwell-time heatmaps), industrial / manufacturing (defect detection, PPE compliance, worker-safety zone intrusion, conveyor object counting, forklift tracking, thermal anomaly), logistics / warehouse (pallet counting, forklift-pedestrian proximity, dock-door status, package damage), healthcare (patient fall detection, hand-hygiene compliance, bed occupancy, PPE/mask compliance), agriculture (livestock counting, crop-disease detection, pest identification, weed detection), energy & utilities (substation intrusion, transformer thermal, meter reading, PPE at height), building / facilities (occupancy counting, tailgating detection, mask/badge compliance, elevator crowding), sports & media (player tracking, ball tracking, crowd density), and any custom OpenVINO/ONNX detector or classifier. Detection metadata flows DLSPS→MQTT→Node-RED→Grafana; video is decoupled: DLSPS overlays detections and streams WebRTC to MediaMTX (WHIP), signalled through Coturn, and is embedded in Grafana as `<iframe>` panels pointing at MediaMTX's built-in WHEP player. Encodes hard-won rules (proxy blanking, per-pipeline MQTT topics, cgroup rules for GPU/NPU, pinned image tags, SAN in self-signed cert, class-filter in Node-RED, Grafana Text-panel sanitizer stripping `<script>`, WebRTC via iframe→MediaMTX WHEP with `GF_SECURITY_ALLOW_EMBEDDING`, Nginx WHEP/WHIP + WebRTC-TCP proxying, DLSPS `frame.type=webrtc peer-id` destination). Invoke this whenever a prompt asks for a full end-to-end *stack* / *recipe* / *solution* for **any** CV analytics use-case. The invoking prompt supplies the vertical/use-case, object(s) of interest, model list, class-filter rules, alert rule default, MQTT topic names, and stack directory name.
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
class filter, alert rule, dashboard, and topic names differ. Inspired
by the open-edge-platform
[Metro Vision AI App Recipe](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe)
and using its **MediaMTX + Coturn + WebRTC** video path, but streamlined:
**no Prometheus, no OTel**. SceneScape is **off by default** but available
as an **opt-in multi-camera spatial-analysis path** (smart-intersection
style — see
[`references/SCENESCAPE.md`](references/SCENESCAPE.md)). Detection metadata (counts,
alerts) flows DLSPS→MQTT→Node-RED→Grafana. Video is decoupled: DLSPS
overlays detections (`gvawatermark`) and pushes each source as a WebRTC
stream to MediaMTX via WHIP (`ENABLE_WEBRTC=true`,
`WEBRTC_SIGNALING_SERVER=http://mediamtx-server:8889`, per-source
`peer-id`); Coturn provides ICE/TURN; Grafana panels are `<iframe>` tags
pointing at MediaMTX's built-in WHEP player at `/mediamtx/<peer-id>/`
(proxied by Nginx).

## Supported verticals & use-cases (illustrative, not exhaustive)

The same stack has been / can be instantiated for — among others:

| Vertical | Example use-cases (each = one invoking prompt) |
|---|---|
| Smart city / ITS | person detection, vehicle detection, ANPR / LPR, smart-parking occupancy, pedestrian-safety zone, traffic-flow counting, wrong-way / red-light violation |
| Retail | customer counting, queue-length monitoring, shelf out-of-stock, loss-prevention, dwell-time heatmap, age/gender demographics |
| Industrial / manufacturing | surface-defect detection, PPE compliance (hardhat/vest/glove), worker-safety zone intrusion, conveyor object counting, forklift tracking, thermal anomaly |
| Logistics / warehouse | pallet counting, forklift-pedestrian proximity, dock-door status, package damage detection, barcode / label read |
| Healthcare | patient fall detection, hand-hygiene compliance, bed occupancy, mask / PPE compliance, waiting-room count |
| Agriculture | livestock counting & health, crop-disease detection, pest / weed identification, fruit counting |
| Energy & utilities | substation perimeter intrusion, transformer thermal anomaly, meter reading, PPE at height |
| Building & facilities | occupancy counting, tailgating detection, badge / mask compliance, elevator crowding |
| Sports & media | player / ball tracking, crowd density estimation, event highlight tagging |
| Custom | any OpenVINO IR / ONNX detector + optional classifier registered with DL Streamer |

The invoking prompt maps its vertical to concrete `{{OBJECT}}`,
`{{PIPELINE_NAME}}`, `{{DEFAULT_MODEL}}`, `{{CLASS_FILTER_IDS}}`,
`{{DEFAULT_RULE}}`, and `{{DASHBOARD_SLUG}}`. Nothing in this skill,
`docker-compose.yml`, `nginx.conf`, `mosquitto.conf`, or the test
skeleton changes across verticals.

## How to use this skill

1. Read this file end-to-end.
2. Ask the 7 questions in ONE batched message (defaults in brackets); accept
   `go` / `defaults` / empty to proceed. Question 7 selects the **SceneScape**
   opt-in spatial-analysis path.
3. Run parameter validation (see below). Refuse to proceed on any failure.
4. Load the relevant references file(s) on demand when authoring each
   component. **Do not load all references up front.** Load
   [`references/SCENESCAPE.md`](references/SCENESCAPE.md) only when
   `{{SCENESCAPE}}=yes`.
5. Verify against the completion criteria before declaring success.

## Reference files (load on demand)

| File | Load when authoring |
|---|---|
| [`references/PIPELINE.md`](references/PIPELINE.md) | DLSPS `config.json`, GPU/NPU variants, REST launcher, watchdog |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | `nginx.conf` (WHEP/WHIP + WebRTC-TCP proxy), Grafana WebRTC iframe panels, dashboard provisioning, Mosquitto |
| [`references/NODE_RED.md`](references/NODE_RED.md) | `flows.json`, MQTT wildcard, `gva_meta` probe, alert flow |
| [`references/INSTALL.md`](references/INSTALL.md) | `.env`, `validate_env.sh`, `install.sh`, `docker-compose.yml` (MediaMTX + Coturn) volumes |
| [`references/TESTS.md`](references/TESTS.md) | `conftest.py`, `test_webrtc_stream.py`, assertion contracts for other tests |
| [`references/SCENESCAPE.md`](references/SCENESCAPE.md) | **Only when `{{SCENESCAPE}}=yes`** — opt-in multi-camera scene-fusion path (Scene Controller + InfluxDB + Grafana Flux + Scene Management UI), delegating to the external `scenescape-setup` skill |

## Parameters (from invoking prompt)

| Param | Purpose |
|---|---|
| `{{OBJECT}}` | class label surfaced in dashboard/alerts, e.g. `person`, `vehicle`, `hardhat`, `pallet`, `defect`, `cow`, `queue`, `mask`, `fall`, `plate` — any string valid for MQTT topics and Grafana titles |
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

1. Model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`)
2. Classifier [`{{CLASSIFIER}}`] (or `none`)
3. Device [CPU] (GPU, NPU, AUTO)
4. Inputs [{{NUM_SOURCES}}× sample-video] (or RTSP URLs / `/dev/videoN` / local paths)
5. Node-RED rule [`{{DEFAULT_RULE}}`, `{{RULE_SCOPE}}`]
6. Alert channel [MQTT `{{ALERT_TOPIC}}`]
7. SceneScape multi-camera spatial analysis? [`{{SCENESCAPE}}`, default `no`]
   (smart-intersection style: Scene Controller fusion + InfluxDB + Grafana Flux
   + Scene Management UI; if `yes`, also collect `{{SCENE_NAME}}` and one unique
   `{{CAMERA_IDS}}` per input stream, then follow
   [`references/SCENESCAPE.md`](references/SCENESCAPE.md))

## Parameter validation (enforce BEFORE `install.sh` runs)

Ship `validate_env.sh` (body in [`references/INSTALL.md`](references/INSTALL.md))
and call as step 0 of `install.sh`. Rules:

| Param | Rule | Failure mode |
|---|---|---|
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

## SceneScape spatial-analysis path (optional, `{{SCENESCAPE}}=yes`)

When Question 7 selects SceneScape, **branch** off the default recipe: keep the
DLSPS detection pipeline, but replace the MediaMTX/WebRTC + Node-RED-alert +
Grafana-MQTT tail with an Intel® SceneScape multi-camera **scene-fusion** stack
(Scene Controller + InfluxDB + Grafana Flux + Scene Management UI + NTP),
modeled on the open-edge-platform **smart-intersection** reference. **Do not
re-implement SceneScape by hand** — delegate to the external
[`scenescape-setup`](https://github.com/open-edge-platform/skills/tree/main/.agents/skills/scenescape-setup)
skill, passing `{{SCENE_NAME}}`, `{{CAMERA_IDS}}`, and the per-camera input
streams. Full architecture, pinned images, validation, run steps, and
completion criteria live in
[`references/SCENESCAPE.md`](references/SCENESCAPE.md); load it only on this
branch. The default (`{{SCENESCAPE}}=no`) path and every other reference in
this skill are unchanged.

## Pinned images (no `:latest`)

- `intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24`
- `eclipse-mosquitto:2.0.22`
- `nodered/node-red:4.1`
- `nginx:1.30.2-alpine`
- `bluenviron/mediamtx:1.11.3` (WebRTC server; WHIP in from DLSPS, WHEP out to browser)
- `coturn/coturn:4.12.0` (ICE/TURN signalling for WebRTC)
- `grafana/grafana:11.5.4` with `GF_INSTALL_PLUGINS="grafana-mqtt-datasource 1.3.3,yesoreyeram-infinity-datasource 3.11.1"`
  (verify each version exists via `curl -s https://grafana.com/api/plugins/<slug>/versions | jq '.items[].version'` — `plugin.versionNotFound` kills the container and Nginx returns 502)
- `intel/dlstreamer:2026.1.0-ubuntu24` (one-shot in `install.sh` for model download + INT8 quantize + TLS cert)

## Layout (flat)

```
{{STACK_DIR}}/
├── README.md
├── docker-compose.yml
├── .env
├── validate_env.sh
├── install.sh                     # HOST_IP, GIDs, model dl+INT8, videos, cert
├── sample_start.sh                # POST N pipelines for chosen device + start watchdog
├── sample_stop.sh                 # kill watchdog + DELETE all pipelines
├── sample_status.sh               # GET /api/pipelines/status
├── sample_watchdog.sh             # respawn COMPLETED file-source pipelines
├── update_dashboard.sh            # rewrite WEBRTC_URL placeholder → https://<HOST>/mediamtx/
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

Every `{{VAR}}` in code blocks (JSON/YAML/shell/Python/HTML/nginx) MUST
be substituted with the concrete value BEFORE writing the file. The test
files, `nginx.conf`, `config.json`, `flows.json`, and the dashboard JSON
are the usual culprits — literal `{{...}}` in Python = syntax error.

## Execution guardrails

- Hard timeouts: model dl+INT8 300 s; video dl 120 s/file; `compose pull`
  300 s; `compose up -d` 120 s + 180 s healthy; each pytest 60 s.
- Max 2 retries per step, then STOP and print last 30 log lines from the
  failing container. Never loop.
- Before `compose up`: `ss -ltn` must show `:80` and `:443` free, and
  `ss -lun` must show `:3478` free (Coturn TURN).
- **Bypass host proxy for all localhost/LAN curl.** Corporate hosts
  export `http_proxy`/`https_proxy` that route `https://localhost/...`
  through an unreachable external proxy → `Could not resolve host` / 502.
  Every curl in `sample_*.sh` MUST include `--noproxy '*'` (and `-k` for
  the self-signed cert). Tests set `NO_PROXY=*` in `conftest.py`.
- Test WebRTC signalling: `curl -k --noproxy '*' -sf -o /dev/null -w '%{http_code}' https://<HOST>/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_1/` (expect `200`; the WHEP player page). The stream only exists after `sample_start.sh` launches the pipelines.
- Test MQTT: `docker run --rm --network <project>_app_network eclipse-mosquitto:2.0.22 mosquitto_sub -h broker -t '#' -v`.
- pytest venv at `./.venv` inside stack dir (`python -m venv .venv`) —
  system pip is PEP-668 blocked; `/tmp` may be `noexec`.

## Optional external skills

If available in the session, invoke; otherwise write files directly using
the reference templates.
- `dlstreamer-coding-agent` — pipeline JSON authoring
- `model-download` (open-edge-platform/edge-ai-libraries) — OMZ model IR
- `scenescape-setup` (open-edge-platform/skills) — **only when `{{SCENESCAPE}}=yes`**; orchestrates the multi-camera SceneScape deploy (see [`references/SCENESCAPE.md`](references/SCENESCAPE.md))

## Reference implementation

The upstream `smart-parking` recipe uses the same MediaMTX + Coturn +
WebRTC video path this skill adopts, plus Prometheus + OTel + SceneScape
which this skill drops. Consult it for `config.json`, `mosquitto.conf`,
`nginx.conf`, `datasources.yml`, `dashboards.yml`, `flows.json`, and the
`compose-without-scenescape.yml` MediaMTX/Coturn service shapes, then
apply the streamlining (remove `prometheus`, `otel-collector`,
`metrics-manager`, and their env) from the references:
[`smart-parking/src/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking/src).

## Completion criteria (all must pass)

> When `{{SCENESCAPE}}=yes`, criteria 3–11 below are **superseded** by the
> SceneScape-branch completion criteria in
> [`references/SCENESCAPE.md`](references/SCENESCAPE.md) (scene created,
> multi-camera fused tracking, InfluxDB/Grafana-Flux, Scene Management UI,
> `DEPLOY COMPLETE` + `scene_uid`). Criteria 1–2 (install + `.env`) still apply.

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
   {{OBJECT}} counts + alert data (MQTT datasource) and `{{NUM_SOURCES}}`
   `<iframe>` WebRTC video panels playing the annotated streams
   (requires `GF_SECURITY_ALLOW_EMBEDDING=true`). Dashboard root
   URL MUST NOT redirect-loop (if it does, `/grafana/` `proxy_pass` has a
   trailing slash — remove it). The MQTT datasource health endpoint
   (`/grafana/api/datasources/uid/mqtt_ds/health`) MUST return
   `"MQTT Connected"` — the broker address goes in **`jsonData.uri`**
   (`tcp://broker:1883`), NOT the top-level `url:` or `jsonData.host/port`
   (those are ignored → "dial tcp: missing address", blank panels).
10. `pytest -q tests/` passes. `pytest --collect-only -q tests/ | tail -1`
    reports ≥ 9 tests collected (no empty stub files).
11. **Watchdog continuity** (file:// sources): after `video-length + 30 s`,
    `/api/pipelines/status` shows `{{NUM_SOURCES}}` in `RUNNING`
    (`COMPLETED` history entries are fine — DLSPS retains them). WebRTC
    streams re-establish (same `peer-id`), MQTT still flowing. Any
    duplicate spawn (>`{{NUM_SOURCES}}` `RUNNING`) indicates the watchdog
    dedup guard is missing.
