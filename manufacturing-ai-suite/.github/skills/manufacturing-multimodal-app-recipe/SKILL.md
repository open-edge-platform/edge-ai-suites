---
name: manufacturing-multimodal-app-recipe
description: >-
  Stand up a complete, ready-to-run vision + time-series fusion analytics
  stack on Intel hardware with one Docker Compose command — point it at a
  camera feed and a sensor stream to get live annotated WebRTC video, sensor
  anomaly detection, AND/OR fused defect alerts, and a Grafana dashboard, for
  any manufacturing-quality-inspection vertical (weld defects, CNC tool wear,
  PCB inspection, predictive maintenance), with no glue code. See "When to use
  this skill" for the full component list, trigger conditions, and boundaries.
license: Apache-2.0
compatibility: >-
  Requires Docker + Docker Compose v2, host with Intel CPU (and optionally
  Intel GPU/NPU with `video`/`render` groups), outbound network access to
  Docker Hub, ghcr.io, and github.com/huggingface.co (for model + sample
  dataset downloads). Ports 80/443 (or `${GRAFANA_PORT}`) for the Nginx TLS
  proxy plus the Coturn UDP port must be free on the host. Tested with the
  open-edge-platform Industrial Edge Insights — Multimodal reference
  (manufacturing-ai-suite, v2026.2.0 image tags).
---

# Manufacturing Multimodal App Recipe — DLSPS + Telegraf/InfluxDB + Time Series Analytics + Fusion Analytics + Grafana + Nginx

Build an end-to-end `{{OBJECT}}`-fusion-analytics stack on Intel hardware in
`./{{STACK_DIR}}/` with Docker Compose. **Vertical-agnostic:** the same
eleven-container topology (Nginx, DLSPS, MediaMTX, Coturn, SeaweedFS S3,
Mosquitto, Telegraf, InfluxDB, Time Series Analytics Microservice, Fusion
Analytics, Grafana) serves any vision-defect + sensor-anomaly fusion use case —
only the vision model, sensor UDF/TICKscript, fusion topics/mode, and
dashboard differ. Follows the open-edge-platform
[Industrial Edge Insights — Multimodal](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-multimodal)
reference (weld-defect-detection sample). The **agentic LLM/VLM
explainability layer is off by default** (opt-in narrative-explanation add-on).
Data flows two ways that meet in Fusion Analytics: **vision** DLSPS→MQTT, and
**sensor** simulator/device→MQTT→Telegraf→InfluxDB + MQTT→Time Series
Analytics Microservice (Kapacitor UDF)→MQTT; Fusion Analytics correlates both
MQTT streams by timestamp and writes the fused verdict to InfluxDB + MQTT —
see architecture below.

## When to use this skill

**Use when** building a manufacturing quality-inspection pipeline that must
correlate a **camera feed** (defect classification/detection) with a
**time-series sensor stream** (pressure, current, vibration, temperature,
CO2 flow, etc.) and raise a single fused anomaly verdict — weld defect
detection, CNC tool-wear/vibration correlation, PCB visual + electrical test
fusion, or any custom OpenVINO/ONNX classifier + scikit-learn/UDF sensor model
pair. Optionally adds an LLM/VLM narrative-explanation layer over flagged
events, or a lightweight demo/PoC single-modality app when no full stack is
needed.

**Not for:** vision-only pipelines with no sensor correlation (use
`metro-ai-app-recipe` / `dlsps-user` instead), sensor-only pipelines with no
video (use `time-series-analytics-user` instead), non-Intel or cloud-only
deployments, or training/exporting models.

## Supported verticals & use-cases

| Vertical | Vision signal | Sensor signal | Example use-cases (each = one invoking prompt) |
|---|---|---|---|
| Welding / joining | weld-seam defect classification | pressure, gas flow, current | porosity, burn-through, cold weld |
| Machining / CNC | tool/surface defect detection | vibration, spindle current | tool wear, chatter, surface finish |
| Electronics / PCB | solder-joint/component defect detection | in-circuit test current/voltage | cold joint, tombstoning, short |
| Predictive maintenance | thermal/visual anomaly detection | vibration, temperature, RPM | bearing wear, misalignment, overheating |
| Custom | any OpenVINO IR / ONNX classifier or detector | any scikit-learn model or rule via UDF | any two-modality fusion use-case |

The invoking prompt maps its vertical to concrete `{{OBJECT}}`,
`{{PIPELINE_NAME}}`, `{{DEFAULT_MODEL}}`, `{{SENSOR_UDF_NAME}}`,
`{{DASHBOARD_SLUG}}` — nothing else changes.

## How to use this skill

1. Read this file end-to-end.
2. Ask **Question 0 (mode)** first. If **demo**, branch to
   [Demo/PoC mode](#demopoc-mode) + load
   [`references/DEMO_POC.md`](references/DEMO_POC.md), skip questions 1–10; else
   (**production**, default) continue.
3. Ask the 10 questions in ONE batched message (defaults in brackets); accept
   `go`/`defaults`/empty. Question 10 selects the **agentic explainability**
   path.
4. Run parameter validation (below); refuse to proceed on any failure.
5. Load reference file(s) on demand — **not all up front** (per the *Reference
   files* table): PIPELINE for the vision model/GPU/NPU; TIMESERIES for the
   UDF/TICKscript; FUSION always (it's the core of this skill); AGENTIC only
   when `{{AGENTIC}}=yes`.
6. Verify against completion criteria before declaring success;
   `validate_env.sh` is **step 0 of `install.sh`**.

## Reference files (load on demand)

| File | Load when authoring |
|---|---|
| [`references/PIPELINE.md`](references/PIPELINE.md) | DLSPS `config.json` (RTSP source from MediaMTX/real camera, classification or detection, S3 frame write, WebRTC, MQTT metadata), GPU/NPU variants |
| [`references/TIMESERIES.md`](references/TIMESERIES.md) | Telegraf MQTT→InfluxDB ingestion, Time Series Analytics Microservice `config.json` + UDF + TICKscript (delegates pattern choice to `time-series-analytics-user`) |
| [`references/FUSION.md`](references/FUSION.md) | Fusion Analytics service (MQTT correlate-by-timestamp, AND/OR logic, InfluxDB write) — **always load**, this is the skill's core differentiator |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | `nginx.conf` proxy (ts-api/dsps-api/image-store/WHIP-WHEP), Grafana iframe + InfluxDB panels, dashboard provisioning, Mosquitto, SeaweedFS S3 |
| [`references/INSTALL.md`](references/INSTALL.md) | file layout, `.env`, `validate_env.sh` + rules, `install.sh`, `docker-compose.yml` volumes |
| [`references/TESTS.md`](references/TESTS.md) | `conftest.py`, fusion/vision/sensor assertion contracts |
| [`references/AGENTIC.md`](references/AGENTIC.md) | **`{{AGENTIC}}=yes` only** — vLLM/OVMS LLM/VLM explainability layer over fused alerts |
| [`references/DEMO_POC.md`](references/DEMO_POC.md) | **`{{MODE}}=demo` only** — lightweight single-modality path (vision-only or sensor-only); no full stack |

## Parameters (from invoking prompt)

| Param | Purpose |
|---|---|
| `{{MODE}}` | `demo` \| `production` (default `production`). `demo` = single-modality path ([DEMO_POC](references/DEMO_POC.md)); rows below are `production`-only |
| `{{OBJECT}}` | fused defect label in dashboard/alerts (e.g. `weld_defect`, `tool_wear`, `solder_defect`); any MQTT/Grafana/InfluxDB-safe string |
| `{{STACK_DIR}}` | resolved by Question 1 (*Working directory*) — the absolute parent path to create this new, flat, standalone stack directory in (e.g. `weld-defect-stack`, `cnc-tool-wear-stack`, `pcb-inspection-stack`); never assumed from the current working directory |
| `{{DEFAULT_MODEL}}`, `{{OTHER_MODELS}}` | vision classifier/detector options for DLSPS |
| `{{PIPELINE_NAME}}` | canonical DLSPS pipeline `name` (e.g. `weld_defect_classification`); variants `<name>`/`_gpu`/`_npu` |
| `{{VISION_TOPIC}}` | MQTT topic DLSPS publishes classification/detection metadata to (e.g. `vision_weld_defect_classification`) |
| `{{SENSOR_UDF_NAME}}` | Time Series Analytics UDF name (e.g. `weld_anomaly_detector`); backed by a pretrained model or a threshold/rate-of-change rule ([time-series-analytics-user](../time-series-analytics-user/references/patterns.md) patterns) |
| `{{SENSOR_MEASUREMENT}}` | InfluxDB measurement / MQTT `topic` the raw sensor stream lands on (e.g. `weld-sensor-data`) |
| `{{TS_TOPIC}}` | MQTT topic the Time Series Analytics UDF publishes flagged points to (e.g. `ts_weld_anomaly_detection`) |
| `{{SENSOR_ALERT_TOPIC}}` | MQTT topic for the sensor-only crit alert (e.g. `alerts/weld_defect_detection`) |
| `{{FUSION_TOPIC}}` | MQTT topic Fusion Analytics publishes the fused verdict to (e.g. `fusion/anomaly_detection_results`) |
| `{{FUSION_MODE}}` | `AND` \| `OR` (default `OR`) — both vs either modality must flag anomaly |
| `{{TOLERANCE_NS}}` | timestamp-matching tolerance in nanoseconds for fusing vision+sensor messages (default `50e6` = 50 ms) |
| `{{DASHBOARD_SLUG}}` | e.g. `weld-defect-detection` |
| `{{INPUT_TYPE}}` | `simulator` (default, looped sample video+CSV pairs) \| `rtsp`/`device` (real camera) + `mqtt`/`opcua` (real sensor feed) |
| `{{AGENTIC}}` | `yes` \| `no` (default `no`). `yes` = LLM/VLM explainability path ([AGENTIC](references/AGENTIC.md)) |
| `{{HOST_IP}}` | host IP for Nginx/Grafana/WebRTC (default `localhost`) |
| `{{TURN_USER}}`, `{{TURN_PASS}}` | Coturn / MediaMTX ICE credentials (default `turnuser` / a generated secret) |

## Questions (single batched prompt)

**Question 0 — Mode** [`production`]: `demo` (single-modality PoC) or
`production` (full fusion stack). If `demo`, STOP and follow
[Demo/PoC mode](#demopoc-mode); skip questions 1–10 (they apply to
`production` only).

1. **Working directory** — the absolute parent path to create `{{STACK_DIR}}/`
   in. This skill generates a **new, flat, standalone** stack directory, not
   a folder inside an existing repo checkout — confirm this explicitly
   unless the invoking context already names one; never default to the
   current working directory or a temp location without asking.
2. Vision model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`) — classifier or detector
3. Vision device [CPU] (GPU, NPU, AUTO)
4. Video input [simulator sample video] (or RTSP URL / `/dev/videoN` / local path); sets DLSPS source
5. Sensor pattern [pretrained model] (threshold, rate-of-change, rolling z-score,
   pretrained model — see `time-series-analytics-user` `references/patterns.md`)
6. Sensor input [simulator sample CSV] (or MQTT/OPC UA live feed); sets Telegraf `TELEGRAF_INPUT_PLUGIN`
7. Fusion mode [`{{FUSION_MODE}}`, default `OR`] + `{{TOLERANCE_NS}}` [default `50e6`]
8. Alert channels [MQTT `{{SENSOR_ALERT_TOPIC}}` + `{{FUSION_TOPIC}}`]
9. Dashboard slug [`{{DASHBOARD_SLUG}}`]
10. LLM/VLM explainability layer over fused alerts? [`{{AGENTIC}}`, default `no`]
   (if `yes`, also collect the LLM model + device →
   [`references/AGENTIC.md`](references/AGENTIC.md))

## Parameter validation (enforce BEFORE `install.sh` runs)

Before anything else, confirm the **working directory** resolved in
Question 1 is where the user actually wants `{{STACK_DIR}}/` created — never
fall back to the current working directory or a temp path just because none
was named. Ship `validate_env.sh` and call it as step 0 of `install.sh`;
reject on any failure. The script body and full **validation rules table**
(`MODE`, `HOST_IP`, `FUSION_MODE`∈`AND`/`OR`, `TOLERANCE_NS` numeric,
`PIPELINE_NAME`, topics, TURN creds, inputs, Agentic params, …) are in
[`references/INSTALL.md`](references/INSTALL.md).

## Reference architecture

Single Compose network `timeseries_network`. Nginx publishes the TLS port
(`${GRAFANA_PORT}`); Coturn also publishes its UDP ICE port. Nginx routes:
`/ts-api/`→Time Series Analytics Microservice REST, `/dsps-api/`→DLSPS REST,
`/image-store/`→SeaweedFS filer (stored frames), `/<peer-id>/whip|whep`→WebRTC
signalling, `/`→Grafana. Data flow:

- **Vision path:** camera/simulator→MediaMTX (RTSP)→DLSPS (`gvaclassify`/
  `gvadetect`)→MQTT `{{VISION_TOPIC}}` + WebRTC (annotated) + S3 write
  (SeaweedFS, stored frames).
- **Sensor path:** sensor/simulator→MQTT (raw)→Telegraf→InfluxDB
  `{{SENSOR_MEASUREMENT}}`; Telegraf also forwards to the Time Series
  Analytics Microservice REST `/input`, which runs the `{{SENSOR_UDF_NAME}}`
  UDF (Kapacitor), writes flagged points to InfluxDB, and publishes MQTT
  `{{TS_TOPIC}}` (every point) + `{{SENSOR_ALERT_TOPIC}}` (crit alerts only).
- **Fusion:** Fusion Analytics subscribes to `{{VISION_TOPIC}}` +
  `{{TS_TOPIC}}`, buffers both streams, matches messages within
  `{{TOLERANCE_NS}}` by timestamp, applies `{{FUSION_MODE}}` logic, writes the
  fused verdict + raw vision metadata to InfluxDB, and publishes
  `{{FUSION_TOPIC}}`.
- **Visualization:** Grafana renders InfluxDB panels (sensor trend, fusion
  verdict table) plus a WebRTC `<iframe>` of the annotated video, all behind
  the Nginx TLS proxy.

## Demo/PoC mode

When Question 0 selects `demo`, **do not build the full stack** (no Compose
topology, no Telegraf/InfluxDB/Fusion Analytics/Grafana/Nginx/SeaweedFS/
MediaMTX/Coturn, no Agentic layer). Produce one lightweight single-modality
app proving either the vision model or the sensor UDF runs on Intel hardware.
Two sub-paths (ask which):

- **Vision-only** — a simple DL Streamer / GStreamer pipeline; delegate to the
  `dlstreamer-coding-agent` skill, or `dlsps-user` for a REST-driven pipeline
  server instance.
- **Sensor-only** — a single UDF + TICKscript deployed on the Time Series
  Analytics Microservice; delegate to `time-series-analytics-user`.

Full guidance + lightweight criteria are in
[`references/DEMO_POC.md`](references/DEMO_POC.md) — load only on this branch;
production criteria (1–11) do **not** apply in demo mode.

## Agentic explainability path (optional, `{{AGENTIC}}=yes`)

When Question 10 selects Agentic, **add** an LLM/VLM layer that subscribes to
Fusion Analytics' "batch-complete" MQTT event and generates a natural-language
explanation of the flagged defect (why it was flagged, which modality drove
it, suggested next action), served via OVMS/vLLM. **Do not re-implement the
agent framework by hand** — reuse the `agent-quality-handler` +
`model-download` + `metrics-manager` microservices as the reference compose
overlay documents. Architecture, images, validation, criteria in
[`references/AGENTIC.md`](references/AGENTIC.md); load only on this branch.
Default (`{{AGENTIC}}=no`) path is unchanged and has no LLM/GPU-memory
footprint.

## Images — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published stable tag on Docker Hub** (query
the repo's `tags` API with `ordering=last_updated`), pin it, and ignore
`*-weekly` pre-releases.

- `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24` (vision)
- `intel/ia-time-series-analytics-microservice:<latest>` (Kapacitor + UDF)
- `intel/ia-multimodal-fusion-analytics:<latest>` (fusion correlator, built
  from `fusion-analytics/Dockerfile` if no prebuilt tag is pinned yet)
- `telegraf:1.39.3-alpine`, `influxdb:1.12.4`
- `eclipse-mosquitto:2.0.22`
- `grafana/grafana-oss:13.0.2`
- `nginx:1.31.4`
- `bluenviron/mediamtx:1.20.1` (WebRTC: WHIP in, WHEP out)
- `coturn/coturn:4.17.2-alpine` (ICE/TURN)
- `chrislusf/seaweedfs:4.42` (S3-compatible object storage for stored frames)
- Agentic-only: `intel/agent-quality-handler`, `intel/model-download`,
  `intel/metrics-manager`, `openvino/model_server:<gpu-tag>` (OVMS for the LLM)

## Layout (flat)

Generate a flat `{{STACK_DIR}}/`: `README.md`, `docker-compose.yml`, `.env`,
`validate_env.sh`, `install.sh`, `Makefile` (or `sample_*.sh` scripts), a
`configs/` tree (`dlstreamer-pipeline-server/`, `time-series-analytics-microservice/`
with `udfs/`+`tick_scripts/`+`models/`, `telegraf/`, `influxdb/`, `mqtt-broker/`,
`grafana/`, `nginx/`, `seaweedfs-s3/`), a `fusion-analytics/` service source
tree (`Dockerfile`, `fusion.py`, `api.py`, `requirements.txt`), a data
simulator (or real-input adapter), and `tests/`. Full annotated tree in
[`references/INSTALL.md`](references/INSTALL.md).

Name the data simulator directory for **this** vertical (e.g.
`{{STACK_DIR}}-simulator/`) — never keep the reference's `weld-data-simulator/`
name in a stack for a different vertical; see
[Reference implementation](#reference-implementation--a-template-to-read-not-a-folder-to-clone)
below for the full renaming/pruning rule.

### `README.md` (required content)

The generated `README.md` MUST document, at minimum:

- **Architecture** — the two-path data flow (vision + sensor) meeting in
  Fusion Analytics, decoupled video (`DLSPS WHIP → MediaMTX → browser WHEP`),
  Coturn ICE/TURN, SeaweedFS stored-frame S3 write, behind the Nginx TLS
  proxy; include the ASCII diagram + eleven containers.
- **Quick start** — `./install.sh` → `docker compose up -d` (or `make up`),
  plus status/down commands.
- **Access URLs + credentials** — dashboard `https://<HOST_IP>:${GRAFANA_PORT}/`
  (Grafana login from `.env`, change on first login), Time Series Analytics
  REST `https://<HOST_IP>:${GRAFANA_PORT}/ts-api`, DLSPS REST
  `https://<HOST_IP>:${GRAFANA_PORT}/dsps-api`.
- **Configuration** — key `.env` values (`HOST_IP`, `FUSION_MODE`,
  `TOLERANCE_NS`, InfluxDB/Grafana creds, TURN creds) + how to swap the
  simulator for a real camera + real sensor feed.

## Template variable substitution

Every `{{VAR}}` MUST be substituted with its concrete value BEFORE writing the
file — a literal `{{...}}` left in `nginx.conf`, `config.json`, `fusion.py`,
the dashboard JSON, or a test file is a syntax error.

## Execution guardrails

- Hard timeouts: model dl 300 s; simulator dataset dl 120 s; `compose pull`
  300 s; `compose up -d` 120 s + 180 s healthy; each pytest 60 s.
- Max 2 retries per step, then STOP and print last 30 log lines from the
  failing container. Never loop.
- Before `compose up`: confirm the Nginx TLS port and Coturn UDP port are free
  on the host.
- **Bypass host proxy for all localhost/LAN curl** — corporate proxies route
  `https://localhost/...` through an unreachable proxy. Every curl MUST use
  `--noproxy '*'` (+ `-k`/`--cacert` for the self-signed cert generated at
  startup).
- Test fusion end-to-end via MQTT, not just REST 200s: `docker exec
  <mqtt-broker> mosquitto_sub -h localhost -v -t '#'` and confirm all three
  topics (`{{VISION_TOPIC}}`, `{{TS_TOPIC}}`, `{{FUSION_TOPIC}}`) appear.
- **Known startup-order caveat** (from the reference implementation): Fusion
  Analytics only starts fusing once the vision metadata carries an RTP sender
  timestamp — DLSPS may not emit that for its first ~300 packets, so allow a
  short warm-up delay before asserting fused output in tests.
- pytest venv at `./.venv` inside stack dir (`python -m venv .venv`) — system
  pip is PEP-668 blocked; `/tmp` may be `noexec`.

## Optional external skills

If available, invoke; otherwise write files from the reference templates.
- `dlsps-user` — DLSPS deploy/config/REST for the vision half ([PIPELINE](references/PIPELINE.md))
- `dlstreamer-coding-agent` — custom GStreamer pipeline authoring (+ demo/PoC vision-only app)
- `time-series-analytics-user` — sensor UDF + TICKscript authoring/deploy for the sensor half ([TIMESERIES](references/TIMESERIES.md))
- `model-download-user` — OMZ/OpenVINO model IR for the vision model, or LLM weights for the Agentic layer
- No delegate skill exists yet for the **Fusion Analytics** correlator itself — author it from
  [`references/FUSION.md`](references/FUSION.md) templates (Python `paho-mqtt` + `influxdb` client + FastAPI)

## Reference implementation — a template to read, not a folder to clone

The upstream
[`industrial-edge-insights-multimodal/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-multimodal)
weld-defect-detection sample is the **shape reference** for
`docker-compose.yml`, `configs/dlstreamer-pipeline-server/config.json`,
`configs/time-series-analytics-microservice/{config.json,tick_scripts,udfs}`,
`fusion-analytics/{fusion.py,api.py}`, `configs/nginx/nginx.conf`,
`configs/grafana/provisioning/datasources.yml`, and the data simulator's
`publisher.py` — read these to learn the structure, then **author the new
stack's files with vertical-specific names and content**. Do **not** `cp -r`
the reference repo into `{{STACK_DIR}}/` and patch it in place — that leaves
weld-specific leftovers (unused `weld_anomaly_detector.*` files, a
`weld-data-simulator/` folder for a non-weld vertical, weld training scripts,
the weld VLM insights workbench, weld docs) sitting in a stack that has
nothing to do with welding, and is the single most common mistake when using
this skill.

### What to copy vs. what to leave behind

| Copy (adapt names/content to `{{OBJECT}}`/`{{SENSOR_UDF_NAME}}`/`{{STACK_DIR}}`) | Leave out unless explicitly requested |
|---|---|
| `docker-compose.yml` topology, `.env` keys, `Makefile`/`sample_*.sh` targets | `docker-compose-vllm.yml`, `docker-compose-agentic.yml`, `configs/agentic/` — only when `{{AGENTIC}}=yes` |
| `configs/{dlstreamer-pipeline-server,time-series-analytics-microservice,telegraf,influxdb,mqtt-broker,grafana,nginx,seaweedfs-s3}/` structure | `insights-workbench/`, `ui-service/` — weld-specific VLM/agentic UI, not part of the base fusion stack |
| `fusion-analytics/{Dockerfile,fusion.py,api.py,requirements.txt}` (generalize label lists — see [FUSION.md](references/FUSION.md)) | `training/` (weld classifier/VLM training scripts) — the new vertical's model is either supplied by the user or fetched via `model-download-user`, not trained here |
| the data simulator's `Dockerfile`/`publisher.py` control flow (paired video+CSV replay) | `docs/user-guide/weld-defect-detection/`, `README-dockerhub.md`, `CHANGELOG.md`, `third-party-programs.txt` — reference-repo metadata, not part of the generated sample |
| one dashboard JSON as a layout template | the reference's other dashboard variants (`*_agentic.json`, `*_vlm.json`) unless `{{AGENTIC}}=yes` |
| `helm/` **only if Kubernetes deployment was requested** | `helm/` otherwise — the plan's one-line Kubernetes note is enough; don't carry the full chart into a Compose-only stack |
| `tests/` structure/pattern from [TESTS.md](references/TESTS.md) | the reference's actual weld-assertion test bodies — write new assertions against `{{VISION_TOPIC}}`/`{{TS_TOPIC}}`/`{{FUSION_TOPIC}}` |

### Renaming rule — no leftover vertical-specific names

Every file, directory, service name, container name, image env var, MQTT
topic, InfluxDB measurement, WebRTC peer-id, and dashboard filename that is
vertical-specific in the reference (contains `weld`/`Weld`, or any other old
vertical's name) MUST be renamed to match this stack's own
`{{OBJECT}}`/`{{SENSOR_UDF_NAME}}`/`{{STACK_DIR}}` — never leave the
reference's naming in a generated stack for a different vertical:

- data simulator directory + Compose service (`weld-data-simulator` →
  e.g. `{{STACK_DIR}}-simulator`), its image env var (`WELD_SIMULATOR_IMAGE`
  → e.g. `{{OBJECT}}_SIMULATOR_IMAGE`)
- UDF file/class + tick script (`weld_anomaly_detector.py`/`.tick` →
  `{{SENSOR_UDF_NAME}}.py`/`.tick`) — **delete** the reference's original
  `weld_anomaly_detector.*` files entirely, don't leave them unused alongside
  the new ones
- pretrained sensor model file(s) (`weld_anomaly_detector.pkl`/`.json`/`.txt`/
  `_labels.pkl` → `{{SENSOR_UDF_NAME}}.pkl` + whatever metadata the chosen
  pattern needs) — delete the unused reference model files from
  `configs/time-series-analytics-microservice/models/`
- vision model directory (`weld-defect-classification-f16-DeiT` → a name
  matching `{{DEFAULT_MODEL}}`) — delete the reference's model directory once
  the new one is in place
- WebRTC `peer-id` / S3 `folder_prefix` (`samplestream` /
  `weld-defect-classification` → `{{STACK_DIR}}`-scoped names, per
  [PIPELINE.md](references/PIPELINE.md))
- MQTT topics, InfluxDB measurements, dashboard JSON filename — already
  templated as `{{VISION_TOPIC}}`/`{{TS_TOPIC}}`/`{{FUSION_TOPIC}}`/
  `{{DASHBOARD_SLUG}}` elsewhere in this skill; confirm the files on disk
  actually use the substituted values, not the weld reference's literals

## Vision/sensor model availability — ask, don't fabricate

`{{DEFAULT_MODEL}}` (vision) and, if the sensor pattern is "pretrained
model", the sensor `.pkl`/`.xml`/`.bin` must be either:

- already available locally (a real file path the invoking prompt names), or
- fetchable from a concrete, resolvable URL (OMZ/OpenVINO Model Zoo, Hugging
  Face, or a URL the invoking prompt supplied) via `model-download-user`/
  `install.sh`.

If neither is true — no known download source and no local file — **stop
before writing `install.sh`'s model-download step and ask the user to
provide the model** (a local path, an upload, or a URL). Do not invent a
plausible-looking model directory/filename and leave it as an empty
placeholder for the user to discover later; a `validate_env.sh` failure on a
missing model file is not a substitute for asking up front.

## Completion criteria (all must pass)

> When `{{AGENTIC}}=yes`, criteria 1–10 still apply; the Agentic layer adds
> its own criteria from [`references/AGENTIC.md`](references/AGENTIC.md).

1. `./install.sh` succeeds: `.env` populated; vision model IR + sensor UDF
   `.pkl` (or equivalent) under `configs/…`; simulator dataset present (if
   `{{INPUT_TYPE}}=simulator`); TLS cert generated. No leftover
   reference-vertical artifacts remain (e.g. a `weld_anomaly_detector.*` file
   or a `weld-data-simulator/` folder in a non-weld stack).
2. `./validate_env.sh` exits 0 with a valid `.env`; an invalid `FUSION_MODE`
   (not `AND`/`OR`) exits non-zero.
3. `docker compose up -d` → all containers `running`/`healthy` (incl.
   `mediamtx`, `coturn`, `seaweedfs-*`).
4. `curl -k --noproxy '*' https://<HOST_IP>:${GRAFANA_PORT}/dsps-api/pipelines/status` shows the pipeline `RUNNING`.
5. `curl -k --noproxy '*' https://<HOST_IP>:${GRAFANA_PORT}/ts-api/kapacitor/v1/ping` returns 204/200.
6. MQTT `{{VISION_TOPIC}}` carries classification/detection metadata within
   30 s of pipeline start.
7. MQTT `{{TS_TOPIC}}` and `{{SENSOR_ALERT_TOPIC}}` carry flagged sensor
   points once anomalous rows are ingested.
8. MQTT `{{FUSION_TOPIC}}` carries a fused verdict JSON matching
   `{{FUSION_MODE}}` semantics once both a vision and sensor anomaly land
   within `{{TOLERANCE_NS}}` of each other; InfluxDB measurement for the
   fused result is populated (`select * from "<fusion-measurement>"`).
9. Grafana at `https://<HOST_IP>:${GRAFANA_PORT}` shows the
   `{{DASHBOARD_SLUG}}` dashboard with a live WebRTC `<iframe>` panel + sensor
   trend + fusion verdict table.
10. `pytest -q tests/` passes; `pytest --collect-only -q tests/ | tail -1`
    reports ≥ 9 tests collected (no empty stubs).
11. **Simulator continuity** (if `{{INPUT_TYPE}}=simulator` and
    `CONTINUOUS_SIMULATOR_INGESTION=true`): after one full replay cycle,
    video + sensor ingestion resumes automatically (looped), fusion output
    keeps flowing.

## Final summary — surface the proof (don't just name files)

Graders see only your **final message** + tool *names*, not file contents. An
expectation counts as met only if you **state it and quote the one decisive
line** in your closing summary — walk every completion criterion plus the
proof-point checklist (topology, both MQTT vision+sensor topics, fusion
verdict with `{{FUSION_MODE}}` logic visible, pinned tags, no literal
`{{...}}`, `validate_env.sh` step 0, curl `--noproxy '*'` + cert flag,
tolerance/timestamp-matching behavior, Agentic layer if requested) detailed in
[`references/INSTALL.md`](references/INSTALL.md) → *Final-summary proof points*.
A claim with no quoted evidence is treated as unmet.
