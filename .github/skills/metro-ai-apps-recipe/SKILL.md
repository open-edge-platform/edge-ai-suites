---
name: metro-ai-apps-recipe
description: >-
  Build an end-to-end computer-vision analytics stack on Intel hardware, in the spirit of the open-edge-platform Metro Vision AI App Recipe. The architecture is vertical-agnostic: one DLSPS + FFmpeg-HLS + Mosquitto + Node-RED + Grafana + Nginx stack serves any DL Streamer / OpenVINO CV pipeline — only the model, class filter, alert rule, dashboard slug, and MQTT topic names change per use-case. Detection metadata flows DLSPS -> MQTT -> Node-RED -> Grafana; video is decoupled as low-latency HLS served by Nginx and embedded in Grafana iframe panels. USE FOR: generating a full end-to-end stack / recipe / solution for any CV analytics use-case (people, vehicles, ANPR, PPE compliance, parking occupancy, retail queues, surface defects). DO NOT USE FOR: authoring a single DL Streamer pipeline in isolation, model download only, or non-vision analytics. The invoking prompt supplies the vertical, objects of interest, model list, class-filter rules, alert rule, MQTT topics, and stack directory name.
license: Apache-2.0
compatibility: >-
  Requires Docker + Docker Compose v2, host with Intel CPU (and optionally
  Intel GPU/NPU with `video`/`render` groups), outbound network access to
  Docker Hub, ghcr.io, and github.com (for model + sample video downloads).
  Ports 80 and 443 must be free on the host. Tested with the open-edge-platform
  Metro Vision AI App Recipe reference (v2026.1.0 image tags).
---

# Metro AI Apps Recipe — DLSPS + FFmpeg-HLS + Mosquitto + Node-RED + Grafana + Nginx

Build an end-to-end `{{OBJECT}}`-analytics stack on Intel hardware in
`./{{STACK_DIR}}/` with Docker Compose. The **architecture is
vertical-agnostic** — the same six-container topology below serves any
DL Streamer / OpenVINO CV pipeline; only the invoking prompt's model,
class filter, alert rule, dashboard, and topic names differ. Inspired
by the open-edge-platform
[Metro Vision AI App Recipe](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe)
but simplified: **no MediaMTX, no Coturn, no WebRTC, no Prometheus, no
OTel**. Detection metadata (counts, alerts) flows DLSPS→MQTT→Node-RED→
Grafana. Video is decoupled: an `ffmpeg` sidecar reads the source files/
streams and produces low-latency HLS to a shared tmpfs; Nginx serves the
segments; Grafana panels are `<iframe>` tags pointing at a static
`player.html` (hls.js) served by Nginx at the origin.

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
2. Ask the 6 questions in ONE batched message (defaults in brackets); accept
   `go` / `defaults` / empty to proceed.
3. Run parameter validation (see below). Refuse to proceed on any failure.
4. Load the relevant references file(s) on demand when authoring each
   component. **Do not load all references up front.**
5. Verify against the completion criteria before declaring success.

## Reference files (load on demand)

| File | Load when authoring |
|---|---|
| [`references/PIPELINE.md`](references/PIPELINE.md) | DLSPS `config.json`, GPU/NPU variants, REST launcher, watchdog |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | `nginx.conf`, Grafana video panels, dashboard provisioning, Mosquitto |
| [`references/NODE_RED.md`](references/NODE_RED.md) | `flows.json`, MQTT wildcard, `gva_meta` probe, alert flow |
| [`references/INSTALL.md`](references/INSTALL.md) | `.env`, `validate_env.sh`, `install.sh`, `docker-compose.yml` volumes |
| [`references/TESTS.md`](references/TESTS.md) | `conftest.py`, `test_frames_served.py`, assertion contracts for other tests |

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
| `{{MJPEG_FPS}}` | default `5` (>10 loads the browser) |

## Questions (single batched prompt)

1. Model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`)
2. Classifier [`{{CLASSIFIER}}`] (or `none`)
3. Device [CPU] (GPU, NPU, AUTO)
4. Inputs [{{NUM_SOURCES}}× sample-video] (or RTSP URLs / `/dev/videoN` / local paths)
5. Node-RED rule [`{{DEFAULT_RULE}}`, `{{RULE_SCOPE}}`]
6. Alert channel [MQTT `{{ALERT_TOPIC}}`]

## Parameter validation (enforce BEFORE `install.sh` runs)

Ship `validate_env.sh` (body in [`references/INSTALL.md`](references/INSTALL.md))
and call as step 0 of `install.sh`. Rules:

| Param | Rule | Failure mode |
|---|---|---|
| `HOST_IP` | `^([0-9]{1,3}\.){3}[0-9]{1,3}$`, not `0.0.0.0`/`127.0.0.1` | LAN clients can't reach Grafana |
| `NUM_SOURCES` | int, 1–16 | CPU saturates before REST launcher finishes |
| `MJPEG_FPS` | int, 1–15 | `<img>` polling stutters, tmpfs fills |
| `DEVICE` | `cpu`\|`gpu`\|`npu`\|`auto` | REST 404 on missing variant |
| `PIPELINE_NAME` | `^[a-z0-9_]+$` | uppercase/hyphen breaks REST + MQTT topic |
| `CLASS_FILTER_IDS` | JSON int array, `[]` allowed | Node-RED filter throws silently |
| `RULE_SCOPE` | `per-source`\|`aggregate` | Node-RED flow undefined |
| `DEFAULT_RULE` | `^count[<>]=?\d+\s+in\s+\d+s$` | function-node syntax error |
| `*_TOPIC*` | `^[A-Za-z0-9_/-]+$`, no `#`/`+`, no leading `/` | mosquitto refuses publish |
| `VIDEO_GID`, `RENDER_GID` | int ≥ 0 | Compose rejects `group_add` |
| `CLASSIFIER` | `none` OR (URL + XML both set) | gvaclassify fails at pipeline start |
| Inputs | `rtsp://…`, `file:///…mp4` (exists), or `/dev/video[0-9]+` (exists) | pipeline state = `ERROR` |

## Reference architecture

Single Docker Compose network `app_network`. **Only Nginx publishes host
ports** (80 redirect → 443 TLS).

```
Browser ─HTTPS 443─▶ Nginx ─▶ /api/           → DLSPS REST
                            ├▶ /grafana/      → Grafana
                            ├▶ /nodered/      → Node-RED
                            └▶ /frames/N.jpg  → shared tmpfs (static, MJPEG-refresh)

DLSPS ─MQTT──────────▶ Mosquitto ─▶ Node-RED ─▶ Grafana (mqtt datasource)
DLSPS ─multifilesink─▶ /frames/{{DETECTIONS_TOPIC_PREFIX}}_N.jpg (shared tmpfs, path per REST param)
                              │
                         Nginx serves ─▶ Grafana <img> panel (poll {{MJPEG_FPS}} fps)
```

## Pinned images (no `:latest`)

- `intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24`
- `eclipse-mosquitto:2.0.22`
- `nodered/node-red:4.1`
- `nginx:1.30.2-alpine`
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
├── update_dashboard.sh            # optional (URLs already relative)
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
    ├── test_frames_served.py
    ├── test_nodered_alert.py
    └── test_grafana_mqtt_data.py
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
- Before `compose up`: `ss -ltn` must show `:80` and `:443` free.
- **Bypass host proxy for all localhost/LAN curl.** Corporate hosts
  export `http_proxy`/`https_proxy` that route `https://localhost/...`
  through an unreachable external proxy → `Could not resolve host` / 502.
  Every curl in `sample_*.sh` MUST include `--noproxy '*'` (and `-k` for
  the self-signed cert). Tests set `NO_PROXY=*` in `conftest.py`.
- Test frame: `curl -k --noproxy '*' -sf https://<HOST>/frames/{{DETECTIONS_TOPIC_PREFIX}}_1.jpg -o ./f.jpg && file ./f.jpg` (expect "JPEG image data").
- Test MQTT: `docker run --rm --network <project>_app_network eclipse-mosquitto:2.0.22 mosquitto_sub -h broker -t '#' -v`.
- pytest venv at `./.venv` inside stack dir (`python -m venv .venv`) —
  system pip is PEP-668 blocked; `/tmp` may be `noexec`.

## Optional external skills

If available in the session, invoke; otherwise write files directly using
the reference templates.
- `dlstreamer-coding-agent` — pipeline JSON authoring
- `model-download` (open-edge-platform/edge-ai-libraries) — OMZ model IR

## Reference implementation

The `smart-parking` recipe uses MediaMTX + Coturn + WebRTC + Prometheus +
OTel; this skill diverges. Consult it for `config.json`, `mosquitto.conf`,
`nginx.conf`, `datasources.yml`, `dashboards.yml`, `flows.json` shapes,
then apply the MJPEG-panel modifications from the references:
[`smart-parking/src/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking/src).

## Completion criteria (all must pass)

1. `./install.sh` succeeds: `.env` populated; INT8 model + optional
   classifier IR under `src/dlstreamer-pipeline-server/models/…`; videos
   downloaded; TLS cert with SAN generated.
2. `./validate_env.sh cpu` exits 0 with a valid `.env`;
   `HOST_IP=127.0.0.1 ./validate_env.sh cpu` exits non-zero.
3. `docker compose up -d` → all containers `running` / `healthy`.
4. `curl -k https://localhost/api/pipelines/status` returns 3 variants.
5. `./sample_start.sh <cpu|gpu|npu>` launches `{{NUM_SOURCES}}` pipelines;
   none `QUEUED`, all `RUNNING`.
6. Detections arrive on
   `{{DETECTIONS_TOPIC_PREFIX}}_1..{{NUM_SOURCES}}/{{PIPELINE_NAME}}`
   (or `_gpu`/`_npu`) within 30 s.
7. `curl -k https://localhost/frames/{{DETECTIONS_TOPIC_PREFIX}}_1.jpg`
   returns 200 `image/jpeg`; two successive fetches spaced
   `1/{{MJPEG_FPS}}` s return different bytes.
8. Node-RED publishes JSON `{{ALERT_TOPIC}}` and **scalar**
   `{{COUNT_TOPIC}}` / `stats/alert_active` / `stats/alert_total` per
   `{{RULE_SCOPE}}`. `mosquitto_sub -t '{{COUNT_TOPIC}}/#' -C 1` MUST
   parse as `int()` — JSON here silently breaks Grafana plotting.
9. Grafana at `https://localhost/grafana` (admin/admin) shows live
   {{OBJECT}} counts + alert data (MQTT datasource) and `{{NUM_SOURCES}}`
   `<img>` video panels updating at ~`{{MJPEG_FPS}}` fps. Dashboard root
   URL MUST NOT redirect-loop (if it does, `/grafana/` `proxy_pass` has a
   trailing slash — remove it).
10. `pytest -q tests/` passes. `pytest --collect-only -q tests/ | tail -1`
    reports ≥ 8 tests collected (no empty stub files).
11. **Watchdog continuity** (file:// sources): after `video-length + 30 s`,
    `/api/pipelines/status` shows `{{NUM_SOURCES}}` in `RUNNING`
    (`COMPLETED` history entries are fine — DLSPS retains them). Frames
    still updating, MQTT still flowing. Any duplicate spawn
    (>`{{NUM_SOURCES}}` `RUNNING`) indicates the watchdog dedup guard is
    missing.
