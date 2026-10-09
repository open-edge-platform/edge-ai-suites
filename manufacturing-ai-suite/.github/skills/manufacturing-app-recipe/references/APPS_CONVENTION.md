# The `apps/<name>/` convention — `ts` mode's core differentiator

The Time Series AI Stack is one shared Compose topology
(`docker-compose.yml`, `Makefile`, `configs/` at the repo root) that many
verticals plug into via a per-vertical `apps/<name>/` folder. Adding a new
sample app means creating this folder and registering it — it does **not**
mean writing a new `docker-compose.yml`. This convention applies only to
`ts` mode; `multimodal`/`vllm`/`agentic` modes generate a flat, standalone
`{{STACK_DIR}}/` instead (see [`INSTALL.md`](INSTALL.md)).

## Steps (mirrors the reference `create-a-new-sample-app.md`)

1. **Create the folder**: `apps/{{APP_NAME}}/` with the five subpaths below.
   The fastest correct starting point is copying the reference
   `apps/wind-turbine-anomaly-detection/` folder and replacing its contents,
   not writing each file from a blank page.

2. **`simulation-data/<dataset>.csv`** — a curated CSV of the vertical's
   sensor tags, time-ordered, one row per ingestion tick. Only needed when
   `{{INGEST_TRANSPORT}}` uses the bundled simulator rather than a real
   device; see [`INGEST.md`](INGEST.md) for the exact column-to-tag mapping
   both simulators expect — **the bundled OPC-UA simulator is hardcoded to
   the wind-turbine schema**, not column-generic like the MQTT one, so
   `{{INGEST_TRANSPORT}}=opcua` additionally needs either a per-app
   simulator adapter or a switch to `mqtt` (see INGEST.md).

3. **`telegraf-config/Telegraf.conf`** — copy the reference file's
   `[agent]`/`[[outputs.influxdb]]` blocks verbatim (they are
   generic/stack-level, not app-specific) and only edit the
   `[[inputs.opcua]]` and/or `[[inputs.mqtt_consumer]]` sections to match
   `{{SENSOR_TAGS}}`. See [`INGEST.md`](INGEST.md) for the exact node/topic
   wiring.

4. **`time-series-analytics-config/`** — the UDF deployment package:
   `config.json` (+ `config-opcua.json` variant),
   `udfs/{{SENSOR_UDF_NAME}}.py`, `tick_scripts/{{SENSOR_UDF_NAME}}.tick`,
   `models/{{SENSOR_UDF_NAME}}.pkl` (if pretrained). **Do not author these by
   hand** — delegate the pattern choice and file contents to
   `time-series-analytics-user`, then move its output into this directory
   and repackage the `.tar` (see [`ANALYTICS.md`](ANALYTICS.md)). If the
   pretrained-model pattern is chosen but no existing `.pkl` or training
   dataset is available, stop and ask the user for one instead of
   scaffolding an empty `models/` folder.

5. **`grafana-dashboard.json`** — one Grafana dashboard JSON, volume-mounted
   directly by the repo-root `docker-compose.yml` at
   `./apps/${SAMPLE_APP}/grafana-dashboard.json` (note: **not** a directory
   like the `multimodal`/`vllm`/`agentic` modes' `dashboards_jsons/` — this repo
   mounts the single file straight into Grafana's provisioning path). See
   [`PROXY_UI.md`](PROXY_UI.md) for the panel requirements.

6. **`training/README.md`** (optional) — only if `{{SENSOR_UDF_NAME}}` is
   backed by a pretrained model; document how the `.pkl` was built (dataset,
   algorithm, hyperparameters) so the model is reproducible/auditable. Skip
   for pure rule-based UDFs (threshold/rate-of-change).

## Registering the app

Edit the repo-root `Makefile`:

```make
DEFAULT_SAMPLE_APP := wind-turbine-anomaly-detection
SAMPLE_APP_LIST := wind-turbine-anomaly-detection {{APP_NAME}}
```

- Append `{{APP_NAME}}` to `SAMPLE_APP_LIST` (space-separated) — the Makefile
  validates `app=<name>` against this list and **errors out** on an
  unregistered name (`Sample app '<name>' not found. Valid options: ...`).
- Only change `DEFAULT_SAMPLE_APP` if the invoking prompt says this new app
  should become the default when `make up_*` is run with no `app=` argument
  — otherwise leave the existing default untouched so other apps keep
  working unmodified.

## Running the new app

```bash
make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}
make status
make down
```
