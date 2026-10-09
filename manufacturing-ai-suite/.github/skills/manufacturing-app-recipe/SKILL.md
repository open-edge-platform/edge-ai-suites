---
name: manufacturing-app-recipe
description: >-
  Stand up a complete, ready-to-run manufacturing analytics stack on Intel
  hardware with one Docker Compose command, across five deployment shapes:
  vision-only inspection, sensor-only (time-series) anomaly detection,
  vision+sensor multimodal, vision+sensor multimodal with VLM narrative explanation,
  and the same with full agentic orchestration — covering any
  manufacturing-quality vertical (weld defects, CNC tool wear, PCB
  inspection, predictive maintenance, wind-turbine/pump/HVAC monitoring)
  with no glue code. See "When to use this skill" and "Deployment modes" for the full
  component list, trigger conditions, and boundaries.
license: Apache-2.0
compatibility: >-
  Docker + Docker Compose v2 on an Intel CPU host (optional GPU/NPU via
  `video`/`render` groups); outbound access to Docker Hub, ghcr.io, and
  Hugging Face for model/dataset downloads. Frees ports 80/443 (or
  `${GRAFANA_PORT}`), the Coturn UDP port (`multimodal`/`vllm`/`agentic`),
  and `${OPCUA_SERVER_PORT_MAPPING}` (`ts`, OPC-UA). Tested against the
  manufacturing-ai-suite Time Series / Multimodal references, v2026.2.0.
---

# Manufacturing App Recipe — vision / time-series / multimodal / VLM / agentic stacks on Intel hardware

Build a manufacturing quality/monitoring stack on Intel hardware with Docker
Compose, in one of **five deployment modes** (Question 0 picks the shape):

| Mode | Shape | Components added on top of the previous mode |
|---|---|---|
| `vision` | lightweight single vision pipeline (demo/PoC only — no full stack) | DLSPS or a custom GStreamer pipeline |
| `ts` | sensor-only anomaly detection | Telegraf/InfluxDB + Time Series Analytics Microservice (Kapacitor UDF) + Grafana, as a new `apps/<name>/` folder (or a bare UDF in demo mode) |
| `multimodal` | vision + sensor, one fused verdict | DLSPS + the `ts` stack + Fusion Analytics correlator, as a new flat stack directory |
| `vllm` | `multimodal` + narrative explanation | an LLM/VLM (OVMS/vLLM) that explains each fused alert in natural language |
| `agentic` | `vllm` + full agent orchestration | `agent-quality-handler` + `model-download` + (optional) `metrics-manager` microservices orchestrating the VLM layer, instead of a bare OVMS call |

`vllm` and `agentic` **always include the sensor path** — there is no
vision-only or sensor-only VLM/agentic mode; both require the Fusion
Analytics correlator from `multimodal` as their foundation, since the thing being
explained is a **fused** verdict. Follows the open-edge-platform
[Industrial Edge Insights — Time Series](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-time-series)
reference (wind-turbine-anomaly-detection sample, `ts` mode) and
[Industrial Edge Insights — Multimodal](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-multimodal)
reference (weld-defect-detection sample, `multimodal`/`vllm`/`agentic` modes).

## When to use this skill

**Use when** building any manufacturing quality-inspection or sensor-monitoring
pipeline that is one of:

- **`vision`** — a quick local demo/PoC proving a vision model runs on Intel
  hardware, no dashboard/alerting stack.
- **`ts`** — a full deployable sensor-only app (simulator or real OPC-UA/MQTT
  ingest, Kapacitor UDF, MQTT/OPC-UA alerting, Grafana dashboard), or a bare
  UDF prototype against an already-running microservice.
- **`multimodal`** — a camera feed correlated with a sensor stream into **one**
  fused anomaly verdict (AND/OR logic) — weld defect detection, CNC
  tool-wear/vibration correlation, PCB visual + electrical test multimodal.
- **`vllm`** — the `multimodal` stack plus an LLM/VLM that turns each fused verdict
  into a human-readable explanation.
- **`agentic`** — the `vllm` stack plus full agent-orchestration microservices
  (batching, worker agents, metrics) instead of a bare LLM call.

**Not for:** vision-only pipelines that need a **full** end-to-end
dashboard/alerting stack (use `metro-ai-app-recipe` instead — `vision` mode
here is demo/PoC only), non-Intel or cloud-only deployments, or
training/exporting models.

## Supported verticals & use-cases

| Vertical | Vision signal | Sensor signal | Typical mode |
|---|---|---|---|
| Welding / joining | weld-seam defect classification | pressure, gas flow, current | `multimodal`/`vllm`/`agentic` |
| Machining / CNC | tool/surface defect detection | vibration, spindle current | `multimodal`/`vllm`/`agentic` |
| Electronics / PCB | solder-joint/component defect detection | in-circuit test current/voltage | `multimodal`/`vllm`/`agentic` |
| Predictive maintenance | thermal/visual anomaly detection | vibration, temperature, RPM | `multimodal`/`vllm`/`agentic` or `ts`-only |
| Renewable energy | — | wind speed, grid active power | `ts` |
| Rotating machinery | — | vibration, RPM, current | `ts` |
| HVAC / facilities | — | temperature, energy draw, airflow | `ts` |
| Process / utilities | — | pressure, flow, level | `ts` |
| Camera-only inspection, quick PoC | any OpenVINO IR / ONNX classifier or detector | — | `vision` |
| Custom | any OpenVINO IR / ONNX classifier or detector | any scikit-learn model or rule via UDF | any mode |

The invoking prompt maps its vertical to concrete `{{OBJECT}}`,
`{{APP_NAME}}`/`{{STACK_DIR}}`, `{{DEFAULT_MODEL}}`, `{{SENSOR_UDF_NAME}}`,
`{{DASHBOARD_SLUG}}`/`{{DASHBOARD_TITLE}}` — nothing else changes.

## How to use this skill

1. Read this file end-to-end.
2. Ask **Question 0 (deployment mode)** first — `vision` \| `ts` \| `multimodal` \|
   `vllm` \| `agentic`. No default; the five modes build materially different
   artifacts, so always confirm explicitly rather than guessing.
3. Branch into the mode-specific question set (below) in ONE batched message
   (defaults in brackets); accept `go`/`defaults`/empty.
4. Run parameter validation (below); refuse to proceed on any failure.
5. Load reference file(s) on demand per the mode's row in *Reference files* —
   **not all up front**.
6. Verify against the mode's completion criteria before declaring success;
   `make check_env_variables` is **step 0** of install/`make up_*`.

## Reference files (load on demand)

| File | Load for mode(s) | When authoring |
|---|---|---|
| [`references/DEMO_POC.md`](references/DEMO_POC.md) | `vision`, `ts` (demo sub-path) | lightweight single-component path — no full stack |
| [`references/PIPELINE.md`](references/PIPELINE.md) | `vision`, `multimodal`, `vllm`, `agentic` | DLSPS `config.json` (RTSP source, classification/detection, S3 frame write, WebRTC, MQTT metadata), GPU/NPU variants |
| [`references/INGEST.md`](references/INGEST.md) | `ts` | OPC-UA/MQTT simulator choice, Telegraf wiring, real-device connection |
| [`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md) | `ts` | the `apps/<name>/` scaffold, Makefile `SAMPLE_APP_LIST` registration |
| [`references/ANALYTICS.md`](references/ANALYTICS.md) | `ts` | Time Series Analytics Microservice `config.json` variants (streaming/batch/OPC-UA-alert) for the standalone `apps/<name>/` shape |
| [`references/TIMESERIES.md`](references/TIMESERIES.md) | `multimodal`, `vllm`, `agentic` | Telegraf MQTT→InfluxDB ingestion + Time Series Analytics Microservice wiring inside the flat multimodal-stack shape (delegates UDF pattern choice to `time-series-analytics-user`) |
| [`references/FUSION.md`](references/FUSION.md) | `multimodal`, `vllm`, `agentic` | Fusion Analytics service (MQTT correlate-by-timestamp, AND/OR logic, InfluxDB write) — **always load for these three modes**, the core differentiator |
| [`references/VLM.md`](references/VLM.md) | `vllm`, `agentic` | the bare LLM/VLM narrative-explanation layer (OVMS/vLLM call over a fused-alert batch) — **always load for these two modes** |
| [`references/AGENTIC.md`](references/AGENTIC.md) | `agentic` only | the agent-orchestration overlay (`agent-quality-handler` + `model-download` + optional `metrics-manager`) on top of `VLM.md`'s bare LLM call |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | all production modes | `nginx.conf` proxy, Grafana dashboard provisioning, Mosquitto, (multimodal+ family) SeaweedFS S3 |
| [`references/INSTALL.md`](references/INSTALL.md) | all production modes | file layout, `.env`, validation rules, `install.sh`/Makefile targets, image tags, copy/leave-behind + renaming rules, and completion criteria per mode |
| [`references/TESTS.md`](references/TESTS.md) | all production modes, only if `{{GENERATE_TESTS}}=yes` | `conftest.py`, per-mode assertion contracts |
| [`references/PARAMETERS.md`](references/PARAMETERS.md) | all | full `{{VAR}}` glossary — purpose, default, and applicable modes |

## Parameters (from invoking prompt)

The invoking prompt supplies concrete values for every `{{VAR}}` used below
(e.g. `{{OBJECT}}`, `{{STACK_DIR}}`/`{{APP_NAME}}`, `{{DEFAULT_MODEL}}`,
`{{SENSOR_UDF_NAME}}`, `{{FUSION_MODE}}`, `{{DASHBOARD_SLUG}}`). Full glossary
with purpose/defaults/applicable-modes in
[`references/PARAMETERS.md`](references/PARAMETERS.md) — load it before
asking Question 0 if any `{{VAR}}` meaning below is unclear.

## Questions (single batched prompt, per mode)

**Question 0 — Deployment mode** (no default, ask explicitly): `vision` \|
`ts` \| `multimodal` \| `vllm` \| `agentic` — see the *Deployment modes* table
above. Then ask ONLY the questions for the chosen mode:

### `vision` mode

0b. Demo sub-path: a DL Streamer/GStreamer pipeline (`dlstreamer-coding-agent`)
    or a REST-driven DLSPS instance (`dlsps-user`)? No default — the two
    produce unrelated artifacts.
1. Vision model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`)
2. Vision device [CPU] (GPU, NPU, AUTO)
3. Video input [sample video] (or RTSP URL / `/dev/videoN` / local path)

Full guidance in [`references/DEMO_POC.md`](references/DEMO_POC.md) —
*Vision-only* section.

### `ts` mode

0b. Sub-mode [`production`]: `demo` (bare UDF, no scaffold — STOP and
    delegate entirely to `time-series-analytics-user`, skip questions below)
    or `production` (full `apps/<name>/` stack).

Production questions:

1. **Working directory** — the absolute path to an existing
   `industrial-edge-insights-time-series` checkout to add
   `apps/{{APP_NAME}}/` into (must already contain `docker-compose.yml` +
   `Makefile` + `apps/` at its root), or where to clone the reference repo
   fresh if none exists. Never guess a path or default to the current
   working directory.
2. App name [`{{APP_NAME}}`] — new `apps/<name>/` folder to create
3. Sensor pattern [pretrained model] (threshold, rate-of-change, rolling
   z-score, pretrained model — see `time-series-analytics-user`
   `references/patterns.md`) + `{{SENSOR_TAGS}}`
4. Ingestion transport [`opcua`] (or `mqtt`) — drives which simulator/Telegraf
   input plugin is used
5. Real device or simulator? [simulator with a sample CSV] (or a real
   OPC-UA server URL / MQTT broker to connect Telegraf to directly)
6. Alert channel [`mqtt`, `{{ALERT_TOPIC}}`] (or `opcua`) — **enable only one**
7. Dashboard title [`{{DASHBOARD_TITLE}}`]
8. Generate pytest tests in `tests/`? [`{{GENERATE_TESTS}}`, no default —
   ask explicitly] (yes/no) — skip the `tests/` folder entirely if no

### `multimodal` mode (and the shared base for `vllm`/`agentic`)

1. **Working directory** — the absolute parent path to create
   `{{STACK_DIR}}/` in. A **new, flat, standalone** stack directory, not a
   folder inside an existing repo checkout — confirm explicitly.
2. Vision model [`{{DEFAULT_MODEL}}`] (also: `{{OTHER_MODELS}}`) — classifier
   or detector
3. Vision device [CPU] (GPU, NPU, AUTO)
4. Video input [simulator sample video] (or RTSP URL / `/dev/videoN` / local
   path); sets DLSPS source
5. Sensor pattern [pretrained model] (threshold, rate-of-change, rolling
   z-score, pretrained model — see `time-series-analytics-user`
   `references/patterns.md`)
6. Sensor input [simulator sample CSV] (or MQTT/OPC UA live feed); sets
   Telegraf `TELEGRAF_INPUT_PLUGIN`
7. Multimodal mode [`{{FUSION_MODE}}`, default `OR`] + `{{TOLERANCE_NS}}`
   [default `50e6`]
8. Alert channels [MQTT `{{SENSOR_ALERT_TOPIC}}` + `{{FUSION_TOPIC}}`]
9. Dashboard slug [`{{DASHBOARD_SLUG}}`]
10. Generate pytest tests in `tests/`? [`{{GENERATE_TESTS}}`, no default —
    ask explicitly] (yes/no) — skip the `tests/` folder entirely if no

### `vllm` mode

Ask the 10 `multimodal`-mode questions above, **plus**:

11. LLM/VLM model [none — must be named, OMZ/HF, or a local path] +
    `{{LLM_DEVICE}}` [GPU] + `{{LLM_WEIGHT_FORMAT}}` [int4] — or
    `LLM_MODE=fallback` for a rule-based templated explanation with no live
    model.
12. Batch trigger for the explanation layer [`{{BATCH_TRIGGER_MODE}}=size`,
    `{{BATCH_SIZE}}=10`] (or `time`, `{{BATCH_INTERVAL_S}}=30`) — Fusion
    Analytics flushes a `batch-complete` MQTT event on this trigger; never
    leave it unset (see FUSION.md's *Batching for the explanation layer*).

### `agentic` mode

Ask the 12 `vllm`-mode questions above, **plus**:

13. Include the optional `metrics-manager`/Prometheus overlay for
    LLM-usage/latency metrics? [`{{AGENT_METRICS}}`, default `no`]

## Parameter validation (enforce BEFORE install/`make up_*` runs)

Confirm the **working directory** (`{{STACK_DIR}}` or `{{TS_REPO_DIR}}`) is
where the user actually wants files created — never fall back to the current
working directory or a temp path. Reuse `make check_env_variables`/
`validate_host_ip` (all production modes) as step 0; reject on any failure.
Full validation rules tables (per mode) are in
[`references/INSTALL.md`](references/INSTALL.md).

## Reference architecture

- **`vision`** — single DLSPS/GStreamer pipeline, no dashboard. See
  [`references/DEMO_POC.md`](references/DEMO_POC.md).
- **`ts`** — sensor/simulator → Telegraf (OPC-UA or MQTT input) → InfluxDB
  (storage) + Time Series Analytics Microservice (Kapacitor UDF) →
  MQTT/OPC-UA alert → Grafana, behind an Nginx TLS proxy. See
  [`references/INGEST.md`](references/INGEST.md) /
  [`references/ANALYTICS.md`](references/ANALYTICS.md).
- **`multimodal`** — two paths meeting in Fusion Analytics: **vision**
  DLSPS→MQTT, and **sensor** simulator/device→MQTT→Telegraf→InfluxDB +
  MQTT→Time Series Analytics Microservice (Kapacitor UDF)→MQTT; Fusion
  Analytics correlates both MQTT streams by timestamp and writes the fused
  verdict to InfluxDB + MQTT. See [`references/FUSION.md`](references/FUSION.md).
- **`vllm`** — `multimodal`, plus an LLM/VLM (OVMS/vLLM) subscribing to a
  fused-alert batch and publishing a narrative explanation. See
  [`references/VLM.md`](references/VLM.md).
- **`agentic`** — `vllm`, plus `agent-quality-handler` orchestrating the LLM
  call via LangGraph worker agents, `model-download` fetching/converting the
  LLM weights ahead of time, and (optionally) `metrics-manager`. See
  [`references/AGENTIC.md`](references/AGENTIC.md).

## Images — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published stable tag on Docker Hub**
(query the repo's `tags` API with `ordering=last_updated`); never pin
`*-weekly` pre-releases. Full per-component image list in
[`references/INSTALL.md`](references/INSTALL.md) → *Image tags*.

## Layout — per mode

- **`vision`** — no fixed layout; whatever `dlstreamer-coding-agent`/
  `dlsps-user` produces for a single pipeline.
- **`ts`** — a new `apps/{{APP_NAME}}/` folder inside the existing generic
  Time Series AI Stack repo (shared `docker-compose.yml`/`Makefile`/`configs/`
  at the repo root): `simulation-data/`, `telegraf-config/`,
  `time-series-analytics-config/{config.json,udfs/,tick_scripts/,models/}`,
  `grafana-dashboard.json`, `training/`. Full annotated tree in
  [`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md).
- **`multimodal`/`vllm`/`agentic`** — a flat, new `{{STACK_DIR}}/`: `README.md`,
  `docker-compose.yml`, `.env`, `install.sh`, `Makefile`, `configs/`,
  `fusion-analytics/`, a data simulator/adapter, plus (for `vllm`/`agentic`)
  an LLM-service overlay, and `tests/` only if `{{GENERATE_TESTS}}=yes`. Full
  annotated tree in
  [`references/INSTALL.md`](references/INSTALL.md). Name the data simulator
  directory for **this** vertical (e.g. `{{STACK_DIR}}-simulator/`) — never
  keep the reference's `weld-data-simulator/` name in a stack for a
  different vertical; see `references/INSTALL.md` → *Reference
  implementation* for the full renaming/pruning rule.

## Template variable substitution

Every `{{VAR}}` MUST be substituted with its concrete value BEFORE writing
the file — a literal `{{...}}` left in `nginx.conf`, `config.json`,
`Telegraf.conf`, `fusion.py`, a dashboard JSON, or a test file is a syntax
error.

## Execution guardrails

- Hard timeouts: model dl 300 s; simulator dataset dl 120 s; `compose pull`
  300 s; `compose up -d` 120 s + 180 s healthy; each pytest 60 s (only when
  `{{GENERATE_TESTS}}=yes`).
- Max 2 retries per step, then STOP and print last 30 log lines from the
  failing container. Never loop.
- Before `compose up` (`multimodal`/`vllm`/`agentic`): confirm the Nginx TLS port
  and Coturn UDP port are free on the host. (`ts`): confirm `${GRAFANA_PORT}`
  and, if OPC-UA, `${OPCUA_SERVER_PORT_MAPPING}` are free.
- **Bypass host proxy for localhost/LAN curl, but don't blanket-disable TLS
  verification** — every curl MUST use `--noproxy '*'`. `-k` is only safe for
  the literal `https://localhost/...` bootstrap check (self-signed cert, no
  network path for a MITM); for anything hitting a real `${HOST_IP}`/LAN
  address, extract the generated cert instead (`docker cp <nginx-container>:
  /opt/nginx/certs/cert.pem ./nginx-cert.pem`) and use `--cacert
  ./nginx-cert.pem --resolve ${HOST_IP}:${GRAFANA_PORT}:127.0.0.1` (the cert
  is `CN=localhost` with no SAN, so `--resolve` is required for hostname
  verification to match) — never fall back to `-k` on a non-localhost target.
- `multimodal`/`vllm`/`agentic`: test multimodal end-to-end via MQTT, not just REST
  200s — confirm `{{VISION_TOPIC}}`, `{{TS_TOPIC}}`, `{{FUSION_TOPIC}}` all
  appear on the broker.
- **Known startup-order caveat** (`multimodal`/`vllm`/`agentic`): Fusion Analytics
  only starts fusing once the vision metadata carries an RTP sender
  timestamp — DLSPS may not emit that for its first ~300 packets, so allow a
  short warm-up delay before asserting fused output in tests.
- `ts`: only one of `ia-opcua-server`/`ia-mqtt-publisher` runs at a time —
  verify the unused simulator is scaled to `0`, not merely stopped.
- `ts`: **enable only one alert channel** — MQTT and OPC-UA alert blocks in
  the same TICKscript is unsupported.
- `ts`: `config.json` (and variants) **MUST stay ≤ 5 KB**.
- `{{GENERATE_TESTS}}=yes` only: pytest venv at `./.venv` inside the
  stack/repo dir (`python -m venv .venv`) — system pip is PEP-668 blocked;
  `/tmp` may be `noexec`.
- **Never fabricate a missing pretrained model** (vision or sensor) — if no
  existing file or resolvable download/training source is available, stop
  and ask the user instead of shipping an empty placeholder path (see
  *Model availability* below).

## Model availability — ask, don't fabricate

`{{DEFAULT_MODEL}}` (vision, all non-`ts` modes) and, if the sensor pattern
is "pretrained model", `{{SENSOR_UDF_NAME}}`'s `.pkl`/`.xml`/`.bin` must be
either already available locally (a real path the invoking prompt names), or
fetchable from a concrete, resolvable URL (OMZ/OpenVINO Model Zoo, Hugging
Face, or a URL the invoking prompt supplied) via `model-download-user`/
`install.sh`. The same rule applies to `{{LLM_MODEL_NAME}}` in `vllm`/`agentic`
mode. If neither is true, **stop before writing the model-download step and
ask the user to provide the model** — do not invent a plausible-looking
model directory/filename and leave it as an empty placeholder.

## Optional external skills

If available, invoke; otherwise write files from the reference templates.

- `dlsps-user` — DLSPS deploy/config/REST for the vision half ([PIPELINE](references/PIPELINE.md))
- `dlstreamer-coding-agent` — custom GStreamer pipeline authoring (+ `vision`-mode demo/PoC app)
- `time-series-analytics-user` — sensor UDF + TICKscript authoring/deploy
  ([ANALYTICS](references/ANALYTICS.md) for `ts`, [TIMESERIES](references/TIMESERIES.md)
  for `multimodal`/`vllm`/`agentic`) — the primary delegate for `ts` demo mode
- `model-download-user` — OMZ/OpenVINO model IR for the vision model, or LLM
  weights for `vllm`/`agentic`
- No delegate skill exists yet for the **Fusion Analytics** correlator or the
  bare **VLM narrative-explanation** call — author them from
  [`references/FUSION.md`](references/FUSION.md) /
  [`references/VLM.md`](references/VLM.md)

## Reference implementation — a template to read, not a folder to clone

The upstream
[`industrial-edge-insights-time-series/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-time-series)
wind-turbine-anomaly-detection sample (`ts` mode) and
[`industrial-edge-insights-multimodal/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-multimodal)
weld-defect-detection sample (`multimodal`/`vllm`/`agentic` modes) are the
**shape reference** — read them to learn the structure, then **author the
new stack's files with vertical-specific names and content**; do **not**
`cp -r` either reference repo and patch it in place. Leaving behind
vertical-specific leftovers (e.g. a `weld-data-simulator/` folder for a
non-weld vertical) is the single most common mistake when using this skill.
Full copy-vs-leave-behind tables and the mandatory renaming rule (no
leftover `weld`/`wind-turbine`/etc. names in generated files, services, MQTT
topics, or measurements) are in
[`references/INSTALL.md`](references/INSTALL.md) → *Reference implementation*.

## Completion criteria (per mode, all applicable must pass)

Full per-mode checklists (`vision`: 3 criteria; `ts`: 9; `multimodal`: 9;
`vllm`: +3 more; `agentic`: +3 more) are in
[`references/INSTALL.md`](references/INSTALL.md) → *Completion criteria* —
verify every applicable item before declaring success; no literal `{{...}}`
may remain in any generated file.

## Final summary — surface the proof (don't just name files)

Graders see only your **final message** + tool *names*, not file contents.
An expectation counts as met only if you **state it and quote the one
decisive line** in your closing summary — walk every completion criterion
for the chosen `{{DEPLOYMENT}}` mode plus the proof-point checklist in
[`references/INSTALL.md`](references/INSTALL.md) → *Final-summary proof
points*. A claim with no quoted evidence is treated as unmet.
