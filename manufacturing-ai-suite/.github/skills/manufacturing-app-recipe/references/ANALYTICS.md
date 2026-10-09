# Time Series Analytics Microservice reference (`ts` mode — delegates to `time-series-analytics-user`)

> **Skill pointer:** for choosing the UDF pattern (threshold, rate-of-change,
> rolling z-score, or pretrained model) and writing the UDF's `Handler`
> methods + TICKscript, invoke external `time-series-analytics-user` and
> follow its `references/patterns.md` + `references/udf-authoring.md` +
> `references/tickscript-basics.md`. Below are recipe-specific overrides for
> landing that output inside an `apps/{{APP_NAME}}/` folder with this repo's
> three config-variant convention. For the flat `{{STACK_DIR}}/` shape used
> by `multimodal`/`vllm`/`agentic` modes, see [`TIMESERIES.md`](TIMESERIES.md)
> instead.

## `config.json` — two variants, same `udfs`/`alerts` shape

| File | When to ship it | Difference from `config.json` |
|---|---|---|
| `config.json` | always | streaming, per-point UDF (`time-series-analytics-user`'s default pattern) |
| `config-opcua.json` | `{{ALERT_CHANNEL}}=opcua` | `alerts` section omits `mqtt` — OPC-UA alerting is wired in the TICKscript's `.post(...)` call, not `config.json` (see below) |

**Do not ship `config-batch.json`/windowed-batch UDFs** — the reference
`Makefile`'s `upload_tar_file` only sets `src_model`/`dst_model` inside its
`wind-turbine-anomaly-detection` branch; for any other `{{APP_NAME}}` it
exits with a "source model not found" error before the upload ever runs.
Only the streaming pattern is supported for newly scaffolded apps.

Both share this shape (fill in from the chosen pattern):

```json
{
  "udfs": {
    "name": "{{SENSOR_UDF_NAME}}",
    "models": "{{SENSOR_UDF_NAME}}.pkl",
    "device": "CPU"
  },
  "alerts": {
    "mqtt": {
      "mqtt_broker_host": "ia-mqtt-broker",
      "mqtt_broker_port": 1883,
      "name": "my_mqtt_broker"
    }
  }
}
```

- Omit `models` entirely for a rule-based (threshold/rate-of-change) UDF.
- **Max size is 5 KB** — never embed model weights here.
- If the pattern is "pretrained model" and no existing model file or
  training dataset is available, stop before generating this file and ask
  the user for one — see SKILL.md's *Model availability* section. Do not
  point `udfs.models` at a filename that will never exist on disk.
- **Pre-upload consistency check** (do this even when `config.json` was
  copied/adapted from another app, not just when authoring from scratch):
  if `udfs.models` is present, confirm the exact named file exists under
  `time-series-analytics-config/models/` **and** is a real artifact for this
  UDF — never create a placeholder/dummy `.pkl` just to satisfy the
  microservice's package validation (an HTTP 422 with "Missing model file
  for task ..." means the config/pattern/package are out of sync, not that
  a stub file is missing). If the UDF is rule-based, delete the `models` key
  from `config.json` and drop the `models/` folder from the tar entirely
  instead of inventing a file to match a stale key.

## Alert channel — enable exactly one

**MQTT** (default) — the TICKscript's native `.mqtt(...)` alert node, same as
`time-series-analytics-user`'s standard pattern:

```
.alert()
    .crit(lambda: "anomaly_status" > 0)
    .message('...')
    .noRecoveries()
    .mqtt('my_mqtt_broker')
    .topic('{{ALERT_TOPIC}}')
    .qos(1)
```

**OPC-UA** — replace the `.mqtt(...)`/`.topic(...)` pair with an explicit
HTTP POST to the microservice's own OPC-UA alert bridge:

```
.alert()
    .crit(lambda: "anomaly_status" > 0)
    .message('Anomaly detected: ...')
    .noRecoveries()
    .post('http://localhost:5000/opcua_alerts')
    .timeout(30s)
```

Per the reference documentation's own explicit caveat: **enabling both in
the same TICKscript is unsupported** — pick one based on
`{{ALERT_CHANNEL}}` and delete the other block entirely, don't comment it out
and leave both wired.

## Packaging and deploying

Reuse `time-series-analytics-user`'s `scripts/package_udf.sh` to build the
`.tar`, but land it at
`apps/{{APP_NAME}}/time-series-analytics-config/{{APP_NAME}}.tar` (this
repo's convention names the tar after the **app**, not the UDF, when there is
exactly one UDF per app — confirm against the reference's own
`wind-turbine-anomaly-detection.tar` naming before deviating).

Deploy via the Makefile's `post_config` step (REST sequencing against
`https://localhost:${GRAFANA_PORT}/ts-api/config`, with `-k` for the
self-signed cert), not a hand-written curl — call
`make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}}` and let it
run `upload_tar_file` + `post_config` for you. **Note:** as of this writing
`post_config`/`upload_tar_file` do not pass `--noproxy '*'`, so with a host
proxy configured these can still be routed through it and fail — this is a
gap in the reference Makefile, not something this recipe's own guardrail
fixes for you.

## Verifying the UDF in isolation

```bash
docker logs ia-time-series-analytics-microservice 2>&1 | grep -F "Flagged anomalous point"
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '{{ALERT_TOPIC}}' -p 1883
```

Confirm a flagged line **and** a captured MQTT/OPC-UA alert before declaring
the analytics half done — an empty `config.json` upload can return HTTP 200
while silently deploying no UDF if `udfs.name` doesn't match the `.tar`'s
internal filename; do not trust the 200 alone.
