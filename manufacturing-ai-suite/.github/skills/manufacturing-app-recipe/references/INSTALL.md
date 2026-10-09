# File layout, `.env`, validation, install/Makefile steps (per mode)

## Layout — `multimodal`/`vllm`/`agentic` modes (flat `{{STACK_DIR}}/`)

```
{{STACK_DIR}}/
├── README.md
├── docker-compose.yml
├── .env
├── install.sh                   # HOST_IP, model dl, dataset dl, TLS cert
├── Makefile                     # up/down/status wrapping docker compose; check_env_variables/validate_host_ip targets (optional; sample_*.sh also fine)
├── configs/
│   ├── dlstreamer-pipeline-server/
│   │   ├── config.json          # PIPELINE.md
│   │   ├── pipeline-request-cpu.json
│   │   └── models/              # vision model IR, downloaded by install.sh
│   ├── time-series-analytics-microservice/
│   │   ├── config.json          # TIMESERIES.md
│   │   ├── udfs/<name>.py
│   │   ├── tick_scripts/<name>.tick
│   │   └── models/<name>.pkl
│   ├── telegraf/
│   │   ├── entrypoint.sh
│   │   └── config/Telegraf.conf
│   ├── influxdb/{config,init-influxdb.sh}
│   ├── mqtt-broker/mosquitto.conf
│   ├── grafana/{dashboards_jsons/,provisioning/{dashboards.yml,datasources.yml}}
│   ├── nginx/{nginx.conf,nginx-cert-gen.sh}
│   └── seaweedfs-s3/{seaweedfs_s3_config.json.template,s3-init-buckets.sh}
├── fusion-analytics/
│   ├── Dockerfile
│   ├── fusion.py                # FUSION.md
│   ├── api.py
│   └── requirements.txt
├── <data-simulator-or-adapter>/  # name it for THIS vertical, e.g. {{STACK_DIR}}-simulator/
│   │                             # — never keep the reference's weld-data-simulator/ name;
│   │                             #   swap for real camera+sensor in production
│   ├── Dockerfile
│   ├── publisher.py
│   └── simulation-data/*.avi + *.csv pairs
├── vllm/                          # {{DEPLOYMENT}}=vllm or agentic only — see VLM.md
│   └── vllm-explainer/{Dockerfile,explainer.py,requirements.txt}
├── agentic/                      # {{DEPLOYMENT}}=agentic only — see AGENTIC.md
│   └── docker-compose-agentic.yml + docker-compose-vllm.yml overlays
└── tests/                        # only if {{GENERATE_TESTS}}=yes — TESTS.md
    ├── conftest.py
    └── test_fusion_pipeline.py  # TESTS.md
```

This is a curated layout, not a mirror of the reference repo — omit
`docker-compose-vllm.yml`/`docker-compose-agentic.yml`/`configs/agentic/`
(unless `{{DEPLOYMENT}}` is `vllm`/`agentic`), `insights-workbench/`,
`ui-service/`, `training/`, `helm/`, vertical-specific `docs/`,
`README-dockerhub.md`, `CHANGELOG.md`, and `third-party-programs.txt` from
the reference — see *Reference implementation* below for the full
copy/leave-behind table and renaming rule.

## Layout — `ts` mode

See [`APPS_CONVENTION.md`](APPS_CONVENTION.md) for the full `apps/{{APP_NAME}}/`
tree (`simulation-data/`, `telegraf-config/`, `time-series-analytics-config/`,
`grafana-dashboard.json`, `training/`) — this mode adds one folder to an
existing shared repo, it does not generate a new Compose topology.

## `.env` — `multimodal`/`vllm`/`agentic` modes

```
COMPOSE_PROJECT_NAME={{STACK_DIR_SLUG}}
HOST_IP=localhost
GRAFANA_PORT=3000

INFLUXDB_USERNAME=            # alphabets only, >=5 chars, not "admin"
INFLUXDB_PASSWORD=            # >=10 alphanumeric, at least 1 digit, no shell-special chars
VISUALIZER_GRAFANA_USER=      # alphabets only, >=5 chars
VISUALIZER_GRAFANA_PASSWORD=  # same rule as INFLUXDB_PASSWORD
S3_STORAGE_USERNAME=
S3_STORAGE_PASSWORD=
MTX_WEBRTCICESERVERS2_0_USERNAME={{TURN_USER}}
MTX_WEBRTCICESERVERS2_0_PASSWORD=   # generated: openssl rand -hex 16

CONTINUOUS_SIMULATOR_INGESTION=true   # false = ingest once, no loop
SIMULATION_REPLAY_COUNT=3
SIMULATION_TARGET_FPS=10
TS_TOPIC={{SENSOR_MEASUREMENT}}       # topic the simulator/device publishes RAW points to (Telegraf's mqtt_consumer input) — name it TS_TOPIC, matching the reference Compose simulator service's `${TS_TOPIC}` env var verbatim

FUSION_MODE={{FUSION_MODE}}           # AND | OR
TOLERANCE_NS={{TOLERANCE_NS}}         # e.g. 50e6

INFLUXDB_RETENTION_DURATION=1h0m0s
S3_BUCKET_TTL=30m
LOG_LEVEL=INFO

# vllm/agentic modes only:
LLM_MODEL_NAME={{LLM_MODEL_NAME}}
LLM_DEVICE={{LLM_DEVICE}}
LLM_WEIGHT_FORMAT={{LLM_WEIGHT_FORMAT}}
HUGGINGFACEHUB_API_TOKEN=
```

### Env validation rules (`make check_env_variables`/`validate_host_ip`)

| Var | Rule |
|---|---|
| `{{DEPLOYMENT}}` | `vision` \| `ts` \| `multimodal` \| `vllm` \| `agentic` |
| `MODE` | `demo` \| `production` (`vision`/`ts` only) |
| `HOST_IP` | non-empty; reject `127.0.0.1` when validating for remote/WebRTC access |
| `FUSION_MODE` | exactly `AND` or `OR` — reject anything else |
| `TOLERANCE_NS` | numeric (accepts scientific notation e.g. `50e6`), `> 0` |
| `INFLUXDB_USERNAME`/`PASSWORD`, `VISUALIZER_GRAFANA_USER`/`PASSWORD` | non-empty, satisfy the length/charset rules from `.env` comments — reject weak/empty creds before `docker compose up` |
| `PIPELINE_NAME` | matches the DLSPS `config.json` pipeline name exactly |
| `{{VISION_TOPIC}}`, `{{TS_TOPIC}}`, `{{SENSOR_ALERT_TOPIC}}`, `{{FUSION_TOPIC}}` | non-empty, distinct from each other (a collision silently merges two data streams) |
| `MTX_WEBRTCICESERVERS2_0_USERNAME`/`PASSWORD` | non-empty (Coturn auth) |
| `INPUT_TYPE` | `simulator` \| `rtsp` \| `device` \| `opcua` |
| `vllm`/`agentic` only | `LLM_MODEL_NAME` set, `MODEL_PATH` resolvable |
| Vision model file (`configs/dlstreamer-pipeline-server/models/{{DEFAULT_MODEL}}/…`), sensor `.pkl`/`.xml`/`.bin` if the pattern is pretrained | must exist on disk before `up`. This check existing is not a substitute for asking the user up front when the model has no known source — see SKILL.md's *Model availability* rule |

Implement as `check_env_variables`/`validate_host_ip` Makefile targets (no
standalone `validate_env.sh` script — the reference repo doesn't have one),
exiting non-zero with a clear message on first failure; chain both as a
dependency of the `up`/`up_vllm`/`up_agentic` targets, same convention as
`ts` mode's `make check_env_variables`.

### `install.sh` — steps (`multimodal`/`vllm`/`agentic`)

1. **Preflight**: `make check_env_variables` (also `validate_host_ip` when
   validating for remote/WebRTC access).
2. **`.env` population**: `HOST_IP`, generated TURN creds
   (`openssl rand -hex 16`), video/render GIDs for GPU/NPU via
   `getent group video|render` (so DLSPS/UDF containers get `/dev/dri`
   access).
3. **Vision model download**: use `model-download-user` for OMZ/OpenVINO
   models, or fetch the vertical's specific classifier IR from its published
   location. Land it under
   `configs/dlstreamer-pipeline-server/models/{{DEFAULT_MODEL}}/` — a name
   that matches this vertical, never the reference's model directory name.
   **If no local file and no resolvable download URL exist, stop here and
   ask the user for the model instead of writing this step against a path
   that will never be populated.**
4. **Sensor UDF/model**: if the pattern is "pretrained model"
   (`time-series-analytics-user`'s taxonomy), fetch/package the `.pkl` (or
   `.xml`/`.bin`) into `configs/time-series-analytics-microservice/models/`
   under `{{SENSOR_UDF_NAME}}.*`, not the reference's filename; for
   rule-based patterns (threshold/rate-of-change) there is nothing to
   download. Same stop-and-ask rule as step 3 if a pretrained model has no
   known source.
5. **Simulator dataset** (if `{{INPUT_TYPE}}=simulator`): the paired
   `.avi`+`.csv` sample set for this vertical must come from the invoking
   prompt or the user — **do not silently download the reference's
   Intel_Robotic_Welding_Multimodal_Dataset** (that's the weld-defect
   sample's own dataset, not a generic stand-in for every vertical). If no
   local file and no resolvable URL exist, stop here and ask the user for
   one instead of fetching an unrelated dataset, per SKILL.md's *Model
   availability* rule. Once provided, land it under
   `<simulator>/simulation-data/`.
6. **Grafana dashboard swap**: `rm configs/grafana/provisioning/*.json &&
   cp configs/grafana/dashboards_jsons/{{DASHBOARD_SLUG}}.json
   configs/grafana/provisioning/{{DASHBOARD_SLUG}}.json` — dashboards live in
   `dashboards_jsons/` as source-of-truth and get copied into the
   auto-provisioned `provisioning/` directory at install/up time (mirrors the
   reference `Makefile`'s `up:` target).
7. **TLS cert**: generated by Nginx's own entrypoint script
   (`nginx-cert-gen.sh`) on first container start — `install.sh` does not
   need to pre-generate it, just ensure the tmpfs cert volume exists.
8. **Fusion Analytics image**: `docker compose build ia-fusion-analytics` (it
   has no prebuilt registry tag in the reference — always build from
   `fusion-analytics/Dockerfile` unless a registry tag is pinned).
9. **`vllm`/`agentic` only — LLM weights**: run `model-download` ahead of
   `apm-llm` startup; confirm `MODEL_PATH` resolves before marking install
   complete.

### `Makefile` targets (optional, mirrors the reference) — `multimodal`/`vllm`/`agentic`

- `up`: `check_env_variables` → `validate_host_ip` → `down` → dashboard swap →
  `docker compose up -d` — plain `multimodal` mode, no LLM/VLM overlay.
- `up_vllm`: same preflight chain (+ `check_hardware`/`check_models`) plus
  `docker-compose-vllm.yml` — use this one, not `up`, when
  `{{DEPLOYMENT}}=vllm`.
- `up_agentic`: same preflight chain plus `docker-compose-agentic.yml` (which
  itself layers in the vLLM service) — use this one when
  `{{DEPLOYMENT}}=agentic`. Never bring up `vllm`/`agentic` mode by manually
  passing `-f docker-compose-vllm.yml`/`-f docker-compose-agentic.yml` to a
  bare `docker compose up` — these three targets are the actual entry
  points, one per `{{DEPLOYMENT}}` value, not a single conditional `up`.
- `down`: `docker compose down -v --remove-orphans`.
- `status`: `docker ps` table filtered to this stack's network, then tail the
  last 5 log lines of every container and flag any containing `error`
  (case-insensitive) — do not fail the whole command on a false-positive
  first-login Grafana token warning, just surface it.

### Final-summary proof points — `multimodal`/`vllm`/`agentic`

Quote in the closing summary: the `docker compose up -d` output showing all
containers `healthy`/`running`; the three MQTT topic subscriptions
(`{{VISION_TOPIC}}`, `{{TS_TOPIC}}`, `{{FUSION_TOPIC}}`) each with one
captured message; the `FUSION_MODE` value and one example fused-decision JSON
that matches its semantics; the InfluxDB `select * from` output for the
multimodal measurement; the Grafana dashboard URL + confirmation the WebRTC
iframe/panel is present; and, if `{{DEPLOYMENT}}` is `vllm`/`agentic`, the LLM
explanation text for one flagged event.

## `.env` — `ts` mode (required fields, shared across all apps — do not fork per app)

```
COMPOSE_PROJECT_NAME=timeseriessoftware
TIMESERIES_UID=2999
KAPACITOR_PORT=9092
GRAFANA_PORT=3000
LOG_LEVEL=INFO

CONTINUOUS_SIMULATOR_INGESTION=true   # false = ingest once, no loop

INFLUXDB_USERNAME=            # alphabets only, >=5 chars, not "admin"
INFLUXDB_PASSWORD=            # >=10 alphanumeric, at least 1 digit, no shell-special chars
VISUALIZER_GRAFANA_USER=      # alphabets only, >=5 chars
VISUALIZER_GRAFANA_PASSWORD=  # same rule as INFLUXDB_PASSWORD
VISUALIZER_GRAFANA_INACTIVE_TIMEOUT=1h

INFLUXDB_RETENTION_DURATION=1h0m0s
OPCUA_SERVER_PORT_MAPPING=30003
```

No per-vertical topic/mode vars belong in `.env` — those live inside
`apps/{{APP_NAME}}/` (Telegraf input blocks, `config.json`'s `alerts`
section) per [`APPS_CONVENTION.md`](APPS_CONVENTION.md).

### Validation — reuse the Makefile's own target, don't reimplement (`ts`)

```bash
make check_env_variables
```

This already validates `INFLUXDB_USERNAME`/`PASSWORD` and
`VISUALIZER_GRAFANA_USER`/`PASSWORD` against the exact charset/length rules
documented above, and is a hard dependency of both `up_mqtt_ingestion` and
`up_opcua_ingestion` — you never need to call it manually before `make up_*`,
but do call it manually when just scaffolding files (before the first
`make up_*`) to fail fast on a bad `.env`.

Additional rules **this skill** enforces before generating files (not
covered by the Makefile target):

| Var | Rule |
|---|---|
| `{{APP_NAME}}` | kebab-case, not already present in `SAMPLE_APP_LIST` |
| `{{INGEST_TRANSPORT}}` | exactly `opcua` or `mqtt` |
| `{{ALERT_CHANNEL}}` | exactly `mqtt` or `opcua` — never both enabled in the same TICKscript |
| `config.json`/variants | ≤ 5 KB each (microservice hard limit) |
| `{{SENSOR_UDF_NAME}}` | matches the UDF's internal filename inside the packaged `.tar` exactly |

### `Makefile` targets (reference — do not duplicate, just call) — `ts`

- `make up_opcua_ingestion app={{APP_NAME}}` — OPC-UA simulator path;
  MQTT publisher scaled to `0`.
- `make up_mqtt_ingestion app={{APP_NAME}}` — MQTT publisher path; OPC-UA
  simulator scaled to `0`.
- `make status` — table of running containers filtered to this stack +
  a best-effort scan of the last 5 log lines per container for the word
  "error" (informational, not a hard gate — a stale first-login Grafana
  warning is expected noise).
- `make down` — `docker compose down -v --remove-orphans`.

### Final-summary proof points — `ts`

Quote in the closing summary: `{{APP_NAME}}` appearing in the Makefile's
`SAMPLE_APP_LIST` diff; the `make check_env_variables` pass/fail output; the
`make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` container-healthy
output confirming the unused simulator is scaled to `0`; the InfluxDB
`select * from` output for the raw sensor measurement; the flagged-anomaly
log line + the captured MQTT/OPC-UA alert; and the Grafana dashboard URL
with confirmation `apps/{{APP_NAME}}/grafana-dashboard.json` is what's
rendering (not a stale previous app's dashboard).

## Image tags — pin to the latest available tag (never `:latest`)

Resolve each image to the **newest published stable tag on Docker Hub**
(query the repo's `tags` API with `ordering=last_updated`), pin it, and
ignore `*-weekly` pre-releases.

- `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24` (vision — `vision`,
  `multimodal`, `vllm`, `agentic`)
- `intel/ia-time-series-analytics-microservice:<latest>` (Kapacitor + UDF —
  `ts`, `multimodal`, `vllm`, `agentic`)
- `intel/ia-multimodal-fusion-analytics:<latest>` (multimodal correlator, built
  from `fusion-analytics/Dockerfile` if no prebuilt tag is pinned yet —
  `multimodal`, `vllm`, `agentic`)
- `telegraf:1.39.3-alpine`, `influxdb:1.12.4` (all production modes)
- `eclipse-mosquitto:2.0.22`, `grafana/grafana-oss:13.0.2`, `nginx:1.31.4`
  (all production modes)
- `bluenviron/mediamtx:1.20.1` (WebRTC WHIP/WHEP), `coturn/coturn:4.17.2-alpine`
  (ICE/TURN), `chrislusf/seaweedfs:4.42` (S3) — `multimodal`, `vllm`, `agentic` only
- `intel/ia-opcua-server:<latest>` / `intel/ia-mqtt-publisher:<latest>`
  (simulators) — `ts` only, whichever matches `{{INGEST_TRANSPORT}}`
- `openvino/model_server:<gpu-tag>` (OVMS, serves the LLM/VLM) — `vllm`,
  `agentic` only
- Agentic-only: `intel/agent-quality-handler`, `intel/model-download`,
  `intel/metrics-manager` (only if `{{AGENT_METRICS}}=yes`) — `agentic` only

## Reference implementation — a template to read, not a folder to clone

The upstream
[`industrial-edge-insights-time-series/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-time-series)
wind-turbine-anomaly-detection sample (`ts` mode) and
[`industrial-edge-insights-multimodal/`](https://github.com/open-edge-platform/edge-ai-suites/tree/main/manufacturing-ai-suite/industrial-edge-insights-multimodal)
weld-defect-detection sample (`multimodal`/`vllm`/`agentic` modes) are the
**shape reference** — read them to learn the structure, then **author the
new stack's files with vertical-specific names and content**. Do **not**
`cp -r` either reference repo and patch it in place — that leaves
vertical-specific leftovers (unused `weld_anomaly_detector.*` files, a
`weld-data-simulator/` folder for a non-weld vertical, weld training
scripts, weld docs) sitting in a stack that has nothing to do with that
vertical, and is the single most common mistake when using this skill.

### What to copy vs. what to leave behind (`multimodal`/`vllm`/`agentic`)

| Copy (adapt names/content to `{{OBJECT}}`/`{{SENSOR_UDF_NAME}}`/`{{STACK_DIR}}`) | Leave out unless the mode/question explicitly requests it |
|---|---|
| `docker-compose.yml` topology, `.env` keys, `Makefile`/`sample_*.sh` targets | `docker-compose-vllm.yml`/`docker-compose-agentic.yml`/`configs/agentic/` — `vllm`/`agentic` modes only |
| `configs/{dlstreamer-pipeline-server,time-series-analytics-microservice,telegraf,influxdb,mqtt-broker,grafana,nginx,seaweedfs-s3}/` structure | `insights-workbench/`, `ui-service/` — weld-specific VLM/agentic UI, not part of the base multimodal stack |
| `fusion-analytics/{Dockerfile,fusion.py,api.py,requirements.txt}` (generalize label lists — see [FUSION.md](FUSION.md)) | `training/` (weld classifier/VLM training scripts) — the new vertical's model is supplied by the user or fetched via `model-download-user`, not trained here |
| the data simulator's `Dockerfile`/`publisher.py` control flow (paired video+CSV replay) | `docs/user-guide/weld-defect-detection/`, `README-dockerhub.md`, `CHANGELOG.md`, `third-party-programs.txt` — reference-repo metadata |
| one dashboard JSON as a layout template | the reference's other dashboard variants (`*_agentic.json`, `*_vlm.json`) unless `{{DEPLOYMENT}}` is `vllm`/`agentic` |
| `tests/` structure/pattern from [TESTS.md](TESTS.md) — only if `{{GENERATE_TESTS}}=yes` | the reference's actual weld-assertion test bodies — write new assertions against `{{VISION_TOPIC}}`/`{{TS_TOPIC}}`/`{{FUSION_TOPIC}}`; the whole `tests/` folder if `{{GENERATE_TESTS}}=no` |
| `helm/` | always — Helm/Kubernetes deployment is out of scope for this skill; Docker Compose only |

### What to copy vs. what to leave behind (`ts`)

| Copy | Leave out |
|---|---|
| `simulation-data/`, `telegraf-config/`, `time-series-analytics-config/` shape, `grafana-dashboard.json` | another app's `training/` scripts — write new ones only if this vertical trains a model |
| the chosen simulator's control flow (OPC-UA server or MQTT publisher) | the unused simulator (OPC-UA vs MQTT) entirely |
| `Makefile` `SAMPLE_APP_LIST` registration pattern | `DEFAULT_SAMPLE_APP` change, unless explicitly requested |

### Renaming rule — no leftover vertical-specific names

Every file, directory, service name, container name, image env var, MQTT
topic, InfluxDB measurement, WebRTC peer-id, and dashboard filename that is
vertical-specific in a reference (contains `weld`/`Weld`, `wind-turbine`, or
any other old vertical's name) MUST be renamed to match this stack's own
`{{OBJECT}}`/`{{SENSOR_UDF_NAME}}`/`{{STACK_DIR}}`/`{{APP_NAME}}` — never
leave the reference's naming in a generated stack for a different vertical
(data simulator directory + Compose service, its image env var, UDF
file/class + tick script — **delete** the reference's original files
entirely rather than leaving them unused alongside the new ones, pretrained
model files, vision model directory, WebRTC `peer-id`/S3 `folder_prefix`,
MQTT topics, InfluxDB measurements, dashboard JSON filename).

## Completion criteria (per mode, all applicable must pass)

**`vision`** (demo/PoC — see [`DEMO_POC.md`](DEMO_POC.md)):
1. The chosen delegate skill's container(s) start successfully.
2. One inference call round-trips end-to-end with evidence quoted verbatim.
3. No literal `{{...}}` remains.

**`ts`** (demo — same bar as `time-series-analytics-user`; production — all
of these):
1. `apps/{{APP_NAME}}/` exists with all required subpaths; registered in
   `SAMPLE_APP_LIST`.
2. `make check_env_variables` exits 0 with a valid `.env`.
3. `make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` → all
   containers `running`/`healthy`; unused simulator scaled to `0`.
4. `curl -k --noproxy '*' https://<HOST_IP>:${GRAFANA_PORT}/ts-api/kapacitor/v1/ping` returns 204/200 (`-k` only valid when `{{HOST_IP}}=localhost`; otherwise use `--cacert`/`--resolve` per SKILL.md's *Execution guardrails*).
5. InfluxDB measurement for the raw sensor stream populated within 30 s.
6. `config.json`'s `udfs.models` key consistent with the chosen UDF pattern.
7. The UDF-flagged measurement populates; the alert channel captures one
   crit alert.
8. Grafana shows `apps/{{APP_NAME}}/grafana-dashboard.json` rendering live
   data.
9. If `{{GENERATE_TESTS}}=yes`: `pytest -q tests/` passes, ≥ 6 tests
   collected.

**`multimodal`** (all of these; **`vllm`/`agentic` add their own criteria below**):
1. `./install.sh` succeeds; no leftover reference-vertical artifacts.
2. `make check_env_variables` exits 0; an invalid `FUSION_MODE` exits non-zero.
3. `docker compose up -d` → all containers `running`/`healthy` (incl.
   `mediamtx`, `coturn`, `seaweedfs-*`).
4. All three MQTT topics (`{{VISION_TOPIC}}`, `{{TS_TOPIC}}`,
   `{{FUSION_TOPIC}}`) carry data.
5. A fused message appears only per `{{FUSION_MODE}}` semantics, within
   `{{TOLERANCE_NS}}`.
6. InfluxDB has both the raw vision measurement and the multimodal measurement
   populated.
7. Grafana renders the WebRTC panel + sensor trend + multimodal verdict table.
8. If `{{GENERATE_TESTS}}=yes`: `pytest -q tests/` passes, ≥ 9 tests
   collected.
9. No literal `{{...}}` remains anywhere.

**`vllm`** (criteria 1–9 above, plus):
10. The LLM/VLM service (OVMS/vLLM) health check passes before it is marked
    ready.
11. Publishing a synthetic fused-alert batch produces one explanation output,
    quoted verbatim in the final summary.
12. `LLM_MODE=fallback` (if selected) still produces a structured explanation
    with no LLM running.

**`agentic`** (criteria 1–12 above, plus):
13. `model-download` completes and `apm-llm`'s health check passes
    (`GET /v3/config` returns 200) before `apm-agent` is marked healthy.
14. Publishing a synthetic `apm/batch-complete` MQTT event produces one
    agent-orchestrated explanation in `apm-agent`'s `OUTPUT_DIR`, quoted
    verbatim.
15. If `{{AGENT_METRICS}}=yes`: `metrics-manager`/Prometheus reports at
    least one LLM-latency metric.
