# Telegraf + Time Series Analytics Microservice reference (the sensor half)

> **Skill pointer:** for authoring the UDF + TICKscript pattern itself
> (threshold, rate-of-change, rolling z-score, or pretrained-model
> inference), invoke external `time-series-analytics-user` and follow its
> `references/patterns.md` — do not hand-roll a new pattern here. Below are
> recipe-specific overrides for wiring that service into the fusion stack.

## Telegraf — MQTT ingest bridge

Telegraf is the only component that talks to both the raw sensor transport
and InfluxDB/the Time Series Analytics Microservice; it does not run any
analytics itself.

Required env on the `ia-telegraf` service:

- `MQTT_BROKER_HOST=ia-mqtt-broker`, `TELEGRAF_INPUT_PLUGIN=mqtt_consumer`
  (default) — set to `opcua_listener`/another Telegraf input plugin if
  `{{INPUT_TYPE}}=opcua` or a different live sensor bus; the recipe's
  `entrypoint.sh` picks the plugin block from `TELEGRAF_INPUT_PLUGIN`.
- `INFLUX_SERVER=ia-influxdb`, `INFLUXDB_DBNAME=datain`,
  `INFLUXDB_USERNAME`/`INFLUXDB_PASSWORD` from `.env`.
- `TS_MS_SERVER_URL=http://ia-time-series-analytics-microservice:${KAPACITOR_PORT}`
  — Telegraf forwards every ingested point to the microservice's REST
  `/input` endpoint **in addition to** writing it to InfluxDB; both happen
  from the same input plugin instance, no separate output config needed.
- `TELEGRAF_METRIC_BATCH_SIZE=100` — batch size per flush to InfluxDB; leave
  as-is unless the vertical has a much higher/lower sensor rate.

The raw sensor stream lands in InfluxDB measurement `{{SENSOR_MEASUREMENT}}`
(e.g. `weld-sensor-data`) and is simultaneously fed point-by-point to
Kapacitor via the microservice REST API — this is what the UDF processes.

## Time Series Analytics Microservice — `config.json`

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

- `models` is omitted entirely for a pure rule-based UDF (threshold /
  rate-of-change) with no `.pkl` — only set it when
  `time-series-analytics-user`'s pattern choice is "pretrained model".
  `.xml`/`.bin` (OpenVINO) also supported per that skill's device rule.
- `device: GPU` triggers UDF inference on the host iGPU — same volume/device
  mounts as DLSPS (`/dev/dri`, `render` GID group_add); leave `CPU` unless the
  vertical's model is compute-heavy.
- **Max config.json size is 5 KB** — keep `udfs`/`alerts` minimal; do not
  embed model weights or large parameter blobs here.

## TICKscript — one stream, two/three sinks

Author `{{SENSOR_UDF_NAME}}.tick` in this shape — one `stream|from()`
reading `{{SENSOR_MEASUREMENT}}`, piped through the UDF once, then fanned out
(do not copy the reference's `weld_anomaly_detector.tick` file onto disk and
rename it — write a new file with this content, substituted for this
vertical):

```
dbrp "datain"."autogen"

var data0 = stream
        |from()
                .database('datain')
                .retentionPolicy('autogen')
                .measurement('{{SENSOR_MEASUREMENT}}')
        @{{SENSOR_UDF_NAME}}()

data0
        |influxDBOut()
                .buffer(0)
                .database('datain')
                .measurement('{{SENSOR_MEASUREMENT}}-anomaly-data')
                .retentionPolicy('autogen')

data0
        |alert()
                .crit(lambda: "anomaly_status" >= 0)
                .message('{"time": "{{ index .Time }}", "anomaly_status": {{ index .Fields "anomaly_status" }}, "predicted_category": "{{ index .Fields "predicted_category" }}", "confidence": "{{ index .Fields "confidence" }}"}')
                .noRecoveries()
                .mqtt('my_mqtt_broker')
                .topic('{{TS_TOPIC}}')
                .qos(1)

data0
        |alert()
                .crit(lambda: "anomaly_status" > 0)
                .message('{"time": "{{ index .Time }}", "anomaly_status": {{ index .Fields "anomaly_status" }}}')
                .noRecoveries()
                .mqtt('my_mqtt_broker')
                .topic('{{SENSOR_ALERT_TOPIC}}')
                .qos(1)
```

- **Two separate alert blocks, two different crit conditions, by design**:
  the first (`>= 0`, i.e. always) publishes **every processed point** to
  `{{TS_TOPIC}}` — this is Fusion Analytics' sensor-side input and needs
  every point (even non-anomalous ones) so timestamp correlation always has a
  candidate to compare against. The second (`> 0`, anomalies only) publishes
  to `{{SENSOR_ALERT_TOPIC}}` for a human/ops-facing MQTT alert subscriber.
  Do not collapse these into one alert — Fusion Analytics would then miss
  non-anomalous baseline points to compare confidence against.
- `qos(1)` on both — at-least-once delivery so a broker reconnect doesn't
  silently drop a crit alert.
- Field names (`anomaly_status`, `predicted_category`, `confidence`) come
  from whatever the UDF's `Handler.point()` method sets via
  `response.point.fieldsDouble`/`fieldsString` — match them exactly to what
  `time-series-analytics-user`'s generated UDF emits for this vertical.

## Wiring into Fusion Analytics

Keep these three names in lockstep across `TIMESERIES.md` and `FUSION.md`:

| Name | Set here | Consumed by |
|---|---|---|
| `{{SENSOR_MEASUREMENT}}` | TICKscript `.measurement(...)` + Telegraf output | InfluxDB queries only |
| `{{TS_TOPIC}}` | TICKscript first `.topic(...)` | Fusion Analytics `TS_TOPIC` env var |
| `{{SENSOR_ALERT_TOPIC}}` | TICKscript second `.topic(...)` | ops/human MQTT subscriber only — **not** consumed by Fusion Analytics |

## Verifying the sensor half in isolation (before wiring fusion)

```bash
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '{{TS_TOPIC}}' -p 1883
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '{{SENSOR_ALERT_TOPIC}}' -p 1883
docker exec -it ia-influxdb influx -username <user> -password <pass> \
  -execute 'use datain; select * from "{{SENSOR_MEASUREMENT}}-anomaly-data"'
```

Confirm both topics carry data and the UDF's flagged rows land in InfluxDB
**before** authoring/troubleshooting `references/FUSION.md` — Fusion Analytics
failures are much easier to diagnose once the sensor half is proven working
standalone.
