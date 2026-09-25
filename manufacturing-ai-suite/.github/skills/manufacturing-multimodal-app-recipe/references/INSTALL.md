# File layout, `.env`, `validate_env.sh`, `install.sh`

## Layout (annotated)

```
{{STACK_DIR}}/
├── README.md
├── docker-compose.yml
├── .env
├── validate_env.sh              # step 0 of install.sh
├── install.sh                   # HOST_IP, model dl, dataset dl, TLS cert
├── Makefile                     # up/down/status wrapping docker compose (optional; sample_*.sh also fine)
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
└── tests/
    ├── conftest.py
    └── test_fusion_pipeline.py  # TESTS.md
```

This is a curated layout, not a mirror of the reference repo — omit
`docker-compose-vllm.yml`/`docker-compose-agentic.yml`/`configs/agentic/`
(unless `{{AGENTIC}}=yes`), `insights-workbench/`, `ui-service/`, `training/`,
`helm/` (unless Kubernetes was requested), vertical-specific `docs/`,
`README-dockerhub.md`, `CHANGELOG.md`, and `third-party-programs.txt` from
the reference — see SKILL.md's *Reference implementation* section for the
full copy/leave-behind table and renaming rule.

## `.env` (required fields, mirrors the reference)

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
TS_TOPIC_RAW={{SENSOR_MEASUREMENT}}   # topic the simulator/device publishes RAW points to (Telegraf's mqtt_consumer input)

FUSION_MODE={{FUSION_MODE}}           # AND | OR
TOLERANCE_NS={{TOLERANCE_NS}}         # e.g. 50e6

INFLUXDB_RETENTION_DURATION=1h0m0s
S3_BUCKET_TTL=30m
LOG_LEVEL=INFO
```

## `validate_env.sh` — validation rules table

| Var | Rule |
|---|---|
| `MODE` | `demo` \| `production` |
| `HOST_IP` | non-empty; reject `127.0.0.1` when validating for remote/WebRTC access (same rule as `metro-ai-app-recipe`) |
| `FUSION_MODE` | exactly `AND` or `OR` — reject anything else |
| `TOLERANCE_NS` | numeric (accepts scientific notation e.g. `50e6`), `> 0` |
| `INFLUXDB_USERNAME`/`PASSWORD`, `VISUALIZER_GRAFANA_USER`/`PASSWORD` | non-empty, satisfy the length/charset rules from `.env` comments — reject weak/empty creds before `docker compose up` |
| `PIPELINE_NAME` | matches the DLSPS `config.json` pipeline name exactly |
| `{{VISION_TOPIC}}`, `{{TS_TOPIC}}`, `{{SENSOR_ALERT_TOPIC}}`, `{{FUSION_TOPIC}}` | non-empty, distinct from each other (a collision silently merges two data streams) |
| `MTX_WEBRTCICESERVERS2_0_USERNAME`/`PASSWORD` | non-empty (Coturn auth) |
| `INPUT_TYPE` | `simulator` \| `rtsp` \| `device` \| `opcua` |
| Agentic (`{{AGENTIC}}=yes` only) | `LLM_MODEL_NAME` set, `MODEL_PATH` resolvable |
| Vision model file (`configs/dlstreamer-pipeline-server/models/{{DEFAULT_MODEL}}/…`), sensor `.pkl`/`.xml`/`.bin` if the pattern is pretrained | must exist on disk before `up`. This check existing is not a substitute for asking the user up front when the model has no known source — see SKILL.md's *ask, don't fabricate* rule |

Ship it as a `bash -e` script; exit non-zero with a clear message on first
failure. Call it as step 0 of `install.sh` exactly like
`metro-ai-app-recipe`.

## `install.sh` — steps

1. **Preflight**: `./validate_env.sh`.
2. **`.env` population**: `HOST_IP`, generated TURN creds
   (`openssl rand -hex 16`), video/render GIDs for GPU/NPU (same
   `getent group video|render` pattern as `metro-ai-app-recipe`).
3. **Vision model download**: reuse `metro-ai-app-recipe`'s
   `download_public_models.sh`/`model-download-user` pattern for OMZ/OpenVINO
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
5. **Simulator dataset** (if `{{INPUT_TYPE}}=simulator`): download the
   paired `.avi`+`.csv` sample set for the vertical (reference: the
   [Intel_Robotic_Welding_Multimodal_Dataset](https://huggingface.co/datasets/IntelLabs/Intel_Robotic_Welding_Multimodal_Dataset)
   on Hugging Face) into `<simulator>/simulation-data/`.
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

## `Makefile` targets (optional, mirrors the reference)

- `up`: `check_env_variables` → `validate_host_ip` → `down` → dashboard swap →
  `docker compose up -d`.
- `down`: `docker compose down -v --remove-orphans`.
- `status`: `docker ps` table filtered to this stack's network, then tail the
  last 5 log lines of every container and flag any containing `error`
  (case-insensitive) — do not fail the whole command on a false-positive
  first-login Grafana token warning, just surface it.

## Final-summary proof points

Quote in the closing summary: the `docker compose up -d` output showing all
eleven containers `healthy`/`running`; the three MQTT topic subscriptions
(`{{VISION_TOPIC}}`, `{{TS_TOPIC}}`, `{{FUSION_TOPIC}}`) each with one
captured message; the `FUSION_MODE` value and one example fused-decision JSON
that matches its semantics; the InfluxDB `select * from` output for the
fusion measurement; the Grafana dashboard URL + confirmation the WebRTC
iframe/panel is present; and, if `{{AGENTIC}}=yes`, the LLM explanation text
for one flagged event.
