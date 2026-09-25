---
name: manufacturing-timeseries-app-recipe
description: >-
  Stand up a complete, ready-to-run sensor time-series anomaly-detection
  stack on Intel hardware with one Docker Compose command — point it at an
  OPC-UA server or MQTT publisher (simulated or real) to get Telegraf/InfluxDB
  ingestion, a Kapacitor UDF anomaly model, MQTT/OPC-UA alerts, and a Grafana
  dashboard, for any manufacturing sensor-monitoring vertical (wind-turbine
  power curve, pump/motor vibration, HVAC energy, predictive maintenance),
  with no glue code. Scaffolds a new use case as a self-contained `apps/<name>/`
  folder in the pluggable Time Series AI Stack. See "When to use this skill"
  for the full component list, trigger conditions, and boundaries.
license: Apache-2.0
compatibility: >-
  Requires Docker + Docker Compose v2, host with Intel CPU (optionally Intel
  GPU with `render` group for GPU-accelerated UDF inference), outbound network
  access to Docker Hub and github.com (for image + sample dataset). Port
  `${GRAFANA_PORT}` (Nginx TLS proxy, default `3000`) must be free on the host;
  the OPC-UA simulator additionally publishes `${OPCUA_SERVER_PORT_MAPPING}`
  (default `30003`). Tested with the open-edge-platform Industrial Edge
  Insights — Time Series reference (manufacturing-ai-suite, v2026.2.0 image
  tags).
---

# Manufacturing Time Series App Recipe — Telegraf/InfluxDB + Time Series Analytics + Grafana + Nginx

Build a sensor-only `{{OBJECT}}`-anomaly-detection stack on Intel hardware in
`./{{STACK_DIR}}/`, as a new `apps/{{APP_NAME}}/` folder inside the generic
**Time Series AI Stack** (TICK-stack based: Telegraf, InfluxDB, Kapacitor via
the Time Series Analytics Microservice, Grafana), with Docker Compose.
**Vertical-agnostic:** the same seven-container topology (Nginx, Telegraf,
InfluxDB, Time Series Analytics Microservice, Mosquitto, Grafana, and one of
an OPC-UA-server or MQTT-publisher simulator) serves any single-modality
sensor-anomaly use case — only the simulated/real dataset, the UDF/TICKscript,
and the Grafana dashboard differ per `apps/<name>/` folder. Follows the
open-edge-platform
[Industrial Edge Insights — Time Series](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-time-series)
reference (wind-turbine-anomaly-detection sample). **No vision/DLSPS
component** — for a vision+sensor fusion use case, use
`manufacturing-multimodal-app-recipe` instead. Data flows one way: sensor
device/simulator → Telegraf (OPC-UA or MQTT input) → InfluxDB (storage) +
Time Series Analytics Microservice (Kapacitor UDF anomaly model) → MQTT/OPC-UA
alert → Grafana — see architecture below.

## When to use this skill

**Use when** scaffolding a new **sensor-only** time-series monitoring/
anomaly-detection app that needs the full deployable stack (ingestion +
storage + Kapacitor UDF + alerting + dashboard), not just a UDF deployed onto
an already-running microservice, and not a vision+sensor fusion use case.
Typical triggers: "add a new sample app for `<sensor use case>`", "stand up a
predictive-maintenance dashboard for `<equipment>`", "wire OPC-UA/MQTT sensor
data into Kapacitor and alert on anomalies".

**Not for:** a vision-only or vision+sensor-fusion pipeline (use
`metro-ai-app-recipe` / `manufacturing-multimodal-app-recipe`), authoring just
a UDF/TICKscript against an **already-deployed** microservice with no
simulator/dashboard/app-registry scaffold needed (use
`time-series-analytics-user` directly), or non-Intel/cloud-only deployments.

## Supported verticals & use-cases

| Vertical | Sensor signal | Example use-cases (each = one invoking prompt) |
|---|---|---|
| Renewable energy | wind speed, grid active power | power-curve anomaly, underperformance detection |
| Rotating machinery | vibration, RPM, current | bearing wear, misalignment, cavitation |
| HVAC / facilities | temperature, energy draw, airflow | efficiency drift, compressor fault |
| Process / utilities | pressure, flow, level | leak detection, blockage, pump fault |
| Custom | any OPC-UA/MQTT numeric tag | any scikit-learn model or rule via UDF |

The invoking prompt maps its vertical to concrete `{{OBJECT}}`,
`{{APP_NAME}}`, `{{SENSOR_UDF_NAME}}`, `{{DASHBOARD_TITLE}}` — nothing else
changes.

## How to use this skill

1. Read this file end-to-end.
2. Ask **Question 0 (mode)** first. If **demo**, STOP and delegate entirely to
   `time-series-analytics-user` (no scaffold, no simulator, no Grafana); else
   (**production**, default) continue.
3. Ask the 9 questions in ONE batched message (defaults in brackets); accept
   `go`/`defaults`/empty.
4. Run parameter validation (below); refuse to proceed on any failure.
5. Load reference file(s) on demand — **not all up front**: ANALYTICS always
   (delegates UDF/TICKscript authoring to `time-series-analytics-user`);
   INGEST for the simulator/real-device choice; BENCHMARK only when
   `{{NUM_STREAMS}}>1`; APPS_CONVENTION always (the scaffold this skill
   exists to automate).
6. Verify against completion criteria before declaring success;
   `check_env_variables` (validate_env.sh equivalent) is step 0 of every
   `make up_*` target.

## Reference files (load on demand)

| File | Load when authoring |
|---|---|
| [`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md) | the `apps/<name>/` scaffold itself (`simulation-data/`, `telegraf-config/`, `time-series-analytics-config/`, `grafana-dashboard.json`, `training/`), Makefile `SAMPLE_APP_LIST` registration — **this skill's core differentiator, always load** |
| [`references/INGEST.md`](references/INGEST.md) | OPC-UA-server vs MQTT-publisher simulator choice, dual-plugin Telegraf wiring, connecting to a real OPC-UA server/MQTT broker instead of the simulator, secure (TLS/auth) connections |
| [`references/ANALYTICS.md`](references/ANALYTICS.md) | Time Series Analytics Microservice `config.json` variants (streaming/batch/OPC-UA-alert), delegates UDF/TICKscript pattern choice to `time-series-analytics-user` |
| [`references/BENCHMARK.md`](references/BENCHMARK.md) | **`{{NUM_STREAMS}}>1` only** — multi-stream load generation via `generate-telegraf-config.py`, `ENABLE_BENCHMARKING` |
| [`references/PROXY_UI.md`](references/PROXY_UI.md) | `nginx.conf` proxy (`/ts-api`, optional raw MQTT TCP stream proxy), Grafana dashboard provisioning per app |
| [`references/INSTALL.md`](references/INSTALL.md) | file layout, `.env`, `Makefile` targets (`up_mqtt_ingestion`/`up_opcua_ingestion`/`batch`/`status`/`down`), validation rules |
| [`references/TESTS.md`](references/TESTS.md) | test contracts for ingestion, UDF flagging, alerting, dashboard |
| [`references/DEMO_POC.md`](references/DEMO_POC.md) | **`{{MODE}}=demo` only** — bare UDF deployment with no scaffold |

## Parameters (from invoking prompt)

| Param | Purpose |
|---|---|
| `{{MODE}}` | `demo` \| `production` (default `production`). `demo` = delegate straight to `time-series-analytics-user`, skip everything else |
| `{{OBJECT}}` | anomaly label in dashboard/alerts (e.g. `wind_turbine`, `bearing_wear`, `hvac_drift`); any MQTT/Grafana/InfluxDB-safe string |
| `{{APP_NAME}}` | the new `apps/<name>/` folder name, kebab-case (e.g. `wind-turbine-anomaly-detection`, `pump-vibration-monitor`) |
| `{{STACK_DIR}}` | resolved by Question 1 (*Working directory*) — never assumed. Either the absolute path to an existing `industrial-edge-insights-time-series` checkout to add `apps/{{APP_NAME}}/` into, or where to clone the reference repo fresh if no checkout exists yet |
| `{{SENSOR_UDF_NAME}}` | Time Series Analytics UDF name (e.g. `windturbine_anomaly_detector`); pattern chosen via `time-series-analytics-user`'s `references/patterns.md` |
| `{{SENSOR_TAGS}}` | the OPC-UA node IDs / MQTT field names to ingest (e.g. `grid_active_power`, `wind_speed`) |
| `{{INGEST_TRANSPORT}}` | `opcua` \| `mqtt` (default `opcua`) — which simulator/Telegraf input plugin drives ingestion |
| `{{ALERT_CHANNEL}}` | `mqtt` (default) \| `opcua` — **enable only one**, per the reference's own caveat |
| `{{ALERT_TOPIC}}` | MQTT topic for crit alerts (e.g. `alerts/wind_turbine`), only when `{{ALERT_CHANNEL}}=mqtt` |
| `{{DASHBOARD_TITLE}}` | Grafana dashboard title for `apps/{{APP_NAME}}/grafana-dashboard.json` |
| `{{NUM_STREAMS}}` | default `1`; `>1` triggers the multi-stream benchmarking path ([BENCHMARK](references/BENCHMARK.md)) |
| `{{BATCH_MODE}}` | `no` (default, per-point streaming UDF) \| `yes` (windowed batch inference, ships as `config-batch.json`) |
| `{{HOST_IP}}` | host IP for Nginx/Grafana (default `localhost`) |

## Questions (single batched prompt)

**Question 0 — Mode** [`production`]: `demo` (bare UDF, no scaffold) or
`production` (full app-registry stack). If `demo`, STOP and delegate to
`time-series-analytics-user` directly — skip questions 1–9.

1. **Working directory** — the absolute path to an existing
   `industrial-edge-insights-time-series` checkout to add `apps/{{APP_NAME}}/`
   into (must already contain `docker-compose.yml` + `Makefile` + `apps/` at
   its root), or, if no checkout exists yet, where to clone the reference
   repo first. Only skip asking this when the invoking context already makes
   it unambiguous (e.g. the conversation is already anchored inside such a
   checkout) — never guess a path, default to the current working directory,
   or start creating files before this is resolved.
2. App name [`{{APP_NAME}}`] — new `apps/<name>/` folder to create
3. Sensor pattern [pretrained model] (threshold, rate-of-change, rolling
   z-score, pretrained model — see `time-series-analytics-user`
   `references/patterns.md`) + `{{SENSOR_TAGS}}`
4. Ingestion transport [`opcua`] (or `mqtt`) — drives which simulator/Telegraf
   input plugin is used
5. Real device or simulator? [simulator with a sample CSV] (or a real
   OPC-UA server URL / MQTT broker to connect Telegraf to directly)
6. Alert channel [`mqtt`, `{{ALERT_TOPIC}}`] (or `opcua`) — **enable only one**
7. Windowed batch inference needed? [`no`] (`yes` ships `config-batch.json`
   in addition to the streaming `config.json`)
8. Dashboard title [`{{DASHBOARD_TITLE}}`]
9. Multi-stream benchmarking? [`{{NUM_STREAMS}}=1`] (`>1` load-tests with
   synthetic parallel streams — see [BENCHMARK](references/BENCHMARK.md))

## Sensor model availability — ask, don't fabricate

When Question 2 selects the "pretrained model" pattern, `{{SENSOR_UDF_NAME}}`'s
`.pkl` (or `.xml`/`.bin`) must come from one of:

- a file the user already has and names a path to — reuse it verbatim, per
  `time-series-analytics-user`'s `references/patterns.md` (never retrain or
  substitute a different model for a named existing file), or
- training a new model against a concrete dataset (the simulator's own
  sample CSV, a real historical dataset the user names, or one you
  generate/synthesize with the user's sign-off) — document this in
  `apps/{{APP_NAME}}/training/README.md` per
  [APPS_CONVENTION.md](references/APPS_CONVENTION.md).

If neither is available — no existing model file named, and no dataset to
train one from — **stop before handing off to `time-series-analytics-user`
and ask the user** whether to (a) supply an existing model file, (b) point at
a dataset to train from, or (c) fall back to a rule-based pattern
(threshold/rate-of-change/rolling z-score) that needs no model at all. Do not
silently switch patterns or ship an empty/placeholder
`models/{{SENSOR_UDF_NAME}}.pkl` path.

## Parameter validation (enforce BEFORE `make up_*` runs)

Before anything else, confirm the **working directory** resolved in
Question 1 actually looks like the right repo checkout — `docker-compose.yml`,
`Makefile`, and `apps/` all present at its root — or that cloning the
reference repo fresh there was explicitly agreed with the user. Refuse to
create `apps/{{APP_NAME}}/` or touch the Makefile at any other path, and
never fall back to the current working directory just because one wasn't
named.

Reuse the Makefile's own `check_env_variables` target as step 0 (it already
validates `INFLUXDB_USERNAME`/`PASSWORD`, `VISUALIZER_GRAFANA_USER`/
`PASSWORD` against the length/charset rules in `.env`'s comments — do not
reimplement these, call the target). Additional rules this skill enforces
before generating files: full **validation rules table** (`APP_NAME` unique
in `SAMPLE_APP_LIST`, `INGEST_TRANSPORT`∈`opcua`/`mqtt`,
`ALERT_CHANNEL`∈`mqtt`/`opcua` with only one enabled, `NUM_STREAMS` positive
integer, config.json ≤ 5 KB) are in
[`references/INSTALL.md`](references/INSTALL.md).

## Reference architecture

Single Compose network `timeseries_network`. Nginx publishes
`${GRAFANA_PORT}` (TLS) and, optionally, a raw MQTT TCP proxy on `1883`.
Nginx routes: `/ts-api/`→Time Series Analytics Microservice REST,
`/`→Grafana. Data flow:

- **Ingest:** sensor device or simulator (`ia-opcua-server` **or**
  `ia-mqtt-publisher`, never both at once — the Makefile scales the unused
  one to `0`) → Telegraf (`[[inputs.opcua]]` or `[[inputs.mqtt_consumer]]`,
  selected by `TELEGRAF_INPUT_PLUGIN`) → **two** `[[outputs.influxdb]]`
  blocks: one to InfluxDB (measurement storage) and one to the Time Series
  Analytics Microservice's own REST-backed InfluxDB-compatible endpoint
  (this is how Telegraf feeds Kapacitor without a separate output plugin).
- **Analyze:** Time Series Analytics Microservice runs `{{SENSOR_UDF_NAME}}`
  (Kapacitor UDF) per point (or per window if `{{BATCH_MODE}}=yes`), writes
  flagged results to InfluxDB, and publishes a crit alert on
  `{{ALERT_CHANNEL}}` (`{{ALERT_TOPIC}}` via MQTT, or `POST
  /opcua_alerts` via OPC-UA).
- **Visualize:** Grafana renders `apps/{{APP_NAME}}/grafana-dashboard.json`
  against InfluxDB, behind the Nginx TLS proxy.

## Demo/PoC mode

When Question 0 selects `demo`, **do not create an `apps/<name>/` folder or
touch the Makefile/Compose file at all** — delegate the entire task to
`time-series-analytics-user` against an already-running (or freshly
`docker compose up`'d, per that skill's own step 1) microservice instance.
No simulator, no Grafana, no Nginx. Production completion criteria (1–10) do
**not** apply; success is `time-series-analytics-user`'s own evidence bar
(REST response bodies, flagged-log lines, MQTT capture — see its "Evidence
you must show" section).

## Images — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published stable tag on Docker Hub**
(query the repo's `tags` API with `ordering=last_updated`), pin it, ignore
`*-weekly` pre-releases.

- `intel/ia-time-series-analytics-microservice:<latest>` (Kapacitor + UDF)
- `telegraf:1.39.3-alpine`, `influxdb:1.12.4`
- `eclipse-mosquitto:2.0.22`
- `grafana/grafana-oss:13.0.2`
- `nginx:1.31.4`
- `intel/ia-opcua-server:<latest>` (simulator, built from
  `simulator/opcua-server/Dockerfile` if no prebuilt tag is pinned) — only
  when `{{INGEST_TRANSPORT}}=opcua` and using the simulator
- `intel/ia-mqtt-publisher:<latest>` (simulator, built from
  `simulator/mqtt-publisher/Dockerfile`) — only when
  `{{INGEST_TRANSPORT}}=mqtt` and using the simulator

## Layout — a new `apps/{{APP_NAME}}/` folder inside the existing stack

This skill does **not** generate a whole new Compose topology per vertical —
it adds one self-contained folder to the existing generic Time Series AI
Stack repo (`docker-compose.yml`, `Makefile`, `configs/` at the repo root are
shared across all apps):

```
apps/{{APP_NAME}}/
├── simulation-data/<dataset>.csv       # or real-device: omit, point Telegraf at the live source instead
├── telegraf-config/Telegraf.conf       # [[inputs.opcua]] and/or [[inputs.mqtt_consumer]] blocks
├── time-series-analytics-config/
│   ├── config.json                     # streaming (default)
│   ├── config-batch.json               # only if {{BATCH_MODE}}=yes
│   ├── config-opcua.json               # only if {{ALERT_CHANNEL}}=opcua
│   ├── udfs/{{SENSOR_UDF_NAME}}.py
│   ├── tick_scripts/{{SENSOR_UDF_NAME}}.tick
│   ├── models/{{SENSOR_UDF_NAME}}.pkl  # omit for pure rule-based UDFs
│   └── {{APP_NAME}}.tar                # packaged UDF, built by time-series-analytics-user's package script
├── grafana-dashboard.json
└── training/README.md                  # optional — how the .pkl was trained, if applicable
```

Then register `{{APP_NAME}}` in the repo-root `Makefile`'s
`SAMPLE_APP_LIST` (and `DEFAULT_SAMPLE_APP` only if it should become the
new default) — full annotated steps in
[`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md), which
mirrors the reference's own
[`create-a-new-sample-app.md`](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/docs/user-guide/how-to-guides/create-a-new-sample-app.md)
guide.

### `apps/{{APP_NAME}}/README.md` note (optional but recommended)

Not required by the reference convention, but recommended: document the
dataset provenance, the UDF pattern chosen, and the exact `make` command to
run this app (`make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}`).

## Template variable substitution

Every `{{VAR}}` MUST be substituted with its concrete value BEFORE writing the
file — a literal `{{...}}` left in `Telegraf.conf`, `config.json`, the
TICKscript, the dashboard JSON, or a test file is a syntax error.

## Execution guardrails

- Hard timeouts: `compose pull` 300 s; `compose up -d` 120 s + 180 s healthy;
  each pytest 60 s.
- Max 2 retries per step, then STOP and print last 30 log lines from the
  failing container. Never loop.
- **`config.json` (and its `config-batch.json`/`config-opcua.json` siblings)
  MUST stay ≤ 5 KB** — the microservice rejects larger payloads; keep model
  weights out of it (they live in `models/*.pkl`, referenced by filename
  only).
- **Enable only one alert channel** — MQTT and OPC-UA alert blocks in the
  same TICKscript is explicitly unsupported by the reference; pick one per
  `{{ALERT_CHANNEL}}` and delete/comment the other.
- Bypass host proxy for all localhost/LAN curl: every curl MUST use
  `--noproxy '*'` + `-k` (self-signed cert).
- Only one of `ia-opcua-server`/`ia-mqtt-publisher` runs at a time — verify
  with `docker compose ps` that the unused simulator is scaled to `0`, not
  merely stopped (the Makefile uses `--scale <service>=0`, not `docker stop`).
- pytest venv at `./.venv` inside the repo dir (`python -m venv .venv`) —
  system pip is PEP-668 blocked.
- **Never fabricate a missing pretrained model** — if `{{SENSOR_UDF_NAME}}`
  needs a `.pkl` and no existing file or training dataset is available, stop
  and ask the user (see *Sensor model availability* above) instead of
  shipping an empty `models/` path. This also applies to a rule-based UDF
  that inherited/copied a stale `udfs.models` key: delete the key and the
  `models/` folder rather than creating a placeholder `.pkl` to make package
  validation pass — a validation failure here means the config/pattern are
  out of sync, not that a stub file is owed (see
  [ANALYTICS.md](references/ANALYTICS.md)).

## Optional external skills

If available, invoke; otherwise write files from the reference templates.
- `time-series-analytics-user` — **always** for the UDF + TICKscript
  authoring/packaging step ([ANALYTICS](references/ANALYTICS.md)); this
  skill only owns the surrounding scaffold (simulator, Telegraf wiring,
  Grafana dashboard, app registry)
- No delegate skill exists for the OPC-UA/MQTT simulators or the
  `apps/<name>/` registry convention itself — author them from
  [`references/INGEST.md`](references/INGEST.md) /
  [`references/APPS_CONVENTION.md`](references/APPS_CONVENTION.md) templates

## Reference implementation

The upstream
[`industrial-edge-insights-time-series/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-time-series)
wind-turbine-anomaly-detection sample uses the same path — consult it for
`docker-compose.yml`, `Makefile`, `generate-telegraf-config.py`,
`apps/wind-turbine-anomaly-detection/{telegraf-config,time-series-analytics-config,grafana-dashboard.json,training}`,
`configs/nginx/nginx.conf`, `simulator/{opcua-server,mqtt-publisher}` shapes.

## Completion criteria (all must pass)

1. `apps/{{APP_NAME}}/` exists with all five subpaths from the Layout
   section; `{{APP_NAME}}` is registered in the Makefile's
   `SAMPLE_APP_LIST`.
2. `make check_env_variables` exits 0 with a valid `.env`; an unset/weak
   `INFLUXDB_PASSWORD` exits non-zero.
3. `make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` → all
   containers `running`/`healthy`; the unused simulator service shows
   `--scale ...=0` (no container, not just stopped).
4. `curl -k --noproxy '*' https://<HOST_IP>:${GRAFANA_PORT}/ts-api/kapacitor/v1/ping` returns 204/200.
5. InfluxDB measurement for the raw sensor stream is populated within 30 s
   of startup (`select * from "<measurement>"`).
6. `config.json`'s `udfs.models` key is consistent with the chosen UDF
   pattern — absent for rule-based UDFs (no matching `models/` folder in the
   tar either), or naming a real, non-placeholder file for a pretrained-model
   UDF; confirmed by inspecting `tar -tvf` output, not by the upload HTTP
   status alone.
7. The UDF-flagged measurement is populated once an anomalous row is
   ingested; `docker exec ia-mqtt-broker mosquitto_sub -t '{{ALERT_TOPIC}}' -C 1`
   (if `{{ALERT_CHANNEL}}=mqtt`) captures the crit alert JSON — or, for
   `opcua`, the alert POST to `/opcua_alerts` is confirmed via the
   microservice log.
8. Grafana at `https://<HOST_IP>:${GRAFANA_PORT}` shows
   `apps/{{APP_NAME}}/grafana-dashboard.json` provisioned and rendering live
   InfluxDB data.
9. `pytest -q tests/` passes; `pytest --collect-only -q tests/ | tail -1`
   reports ≥ 6 tests collected (no empty stubs).
10. If `{{BATCH_MODE}}=yes`: posting `config-batch.json` instead of
   `config.json` succeeds (HTTP 200) and windowed (not per-point) results
   land in InfluxDB.
11. If `{{NUM_STREAMS}}>1`: `generate-telegraf-config.py` produced
    `Telegraf_multi_stream.conf` and all `{{NUM_STREAMS}}` simulated streams
    show up as distinct tag values in InfluxDB (see
    [BENCHMARK](references/BENCHMARK.md)).

## Final summary — surface the proof (don't just name files)

Graders see only your **final message** + tool *names*, not file contents. An
expectation counts as met only if you **state it and quote the one decisive
line** in your closing summary — walk every completion criterion plus the
proof-point checklist (app registered in `SAMPLE_APP_LIST`, correct simulator
scaled to `0`, config.json size, single alert channel enabled, no literal
`{{...}}`, `check_env_variables` step 0, curl `--noproxy '*'` + `-k`, batch
mode if requested, multi-stream if requested) detailed in
[`references/INSTALL.md`](references/INSTALL.md) → *Final-summary proof
points*. A claim with no quoted evidence is treated as unmet.
