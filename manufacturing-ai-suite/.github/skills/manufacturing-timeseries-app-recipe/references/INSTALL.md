# `.env`, `Makefile` targets, and validation rules

## `.env` (required fields, shared across all apps — do not fork per app)

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

## Validation — reuse the Makefile's own target, don't reimplement

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
| `{{NUM_STREAMS}}` | positive integer; `1` skips the benchmarking path entirely |
| `config.json`/variants | ≤ 5 KB each (microservice hard limit) |
| `{{SENSOR_UDF_NAME}}` | matches the UDF's internal filename inside the packaged `.tar` exactly |

## `Makefile` targets (reference — do not duplicate, just call)

- `make up_opcua_ingestion app={{APP_NAME}}` — OPC-UA simulator path;
  MQTT publisher scaled to `0`.
- `make up_mqtt_ingestion app={{APP_NAME}}` — MQTT publisher path; OPC-UA
  simulator scaled to `0`.
- `make batch up_mqtt_ingestion app={{APP_NAME}}` (or `up_opcua_ingestion`)
  — posts `config-batch.json` instead of `config.json`; `batch` must be
  combined with one of the ingestion targets, it is not standalone.
- `make status` — table of running containers filtered to this stack +
  a best-effort scan of the last 5 log lines per container for the word
  "error" (informational, not a hard gate — a stale first-login Grafana
  warning is expected noise).
- `make down` — `docker compose down -v --remove-orphans`.
- `num_of_streams=<N>` and `number_of_data_points_per_stream=<N>` — optional
  extra args on any `up_*` target, see [`BENCHMARK.md`](BENCHMARK.md).

## Final-summary proof points

Quote in the closing summary: `{{APP_NAME}}` appearing in the Makefile's
`SAMPLE_APP_LIST` diff; the `make check_env_variables` pass/fail output; the
`make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` container-healthy
output confirming the unused simulator is scaled to `0`; the InfluxDB
`select * from` output for the raw sensor measurement; the flagged-anomaly
log line + the captured MQTT/OPC-UA alert; and the Grafana dashboard URL
with confirmation `apps/{{APP_NAME}}/grafana-dashboard.json` is what's
rendering (not a stale previous app's dashboard).
