# Ingestion reference — OPC-UA / MQTT simulators + Telegraf wiring

## Choosing a transport

Only **one** ingestion path runs at a time — the Makefile scales the unused
simulator to `0` rather than running both:

```bash
make up_opcua_ingestion app={{APP_NAME}}   # ia-mqtt-publisher --scale=0
make up_mqtt_ingestion  app={{APP_NAME}}   # ia-opcua-server   --scale=0
```

Both targets set `TELEGRAF_INPUT_PLUGIN` (`opcua` or `mqtt_consumer`) and
mount `apps/${SAMPLE_APP}/telegraf-config/` into the Telegraf container —
picking the transport is a `make` target choice, not a `.env` edit.

## OPC-UA path (`{{INGEST_TRANSPORT}}=opcua`, default)

- `ia-opcua-server` (simulator) reads
  `apps/{{APP_NAME}}/simulation-data/<dataset>.csv` and serves it as OPC-UA
  nodes on port `4840` internally (host-mapped via
  `${OPCUA_SERVER_PORT_MAPPING:-30003}`).
- Telegraf's `[[inputs.opcua]]` block needs one `[[inputs.opcua.nodes]]`
  entry per `{{SENSOR_TAGS}}` column, each with `namespace`, `identifier_type`
  (`i` for integer identifiers), and `identifier` matching what the
  simulator assigns per CSV column (increments per column in file order —
  confirm the exact identifier-to-column mapping against the simulator's own
  source before hand-writing these, do not guess):

  ```conf
  [[inputs.opcua]]
    name = "opcua"
    name_override = "{{SENSOR_MEASUREMENT}}"
    endpoint = "$OPCUA_SERVER"
    auth_method = "Anonymous"
    security_policy = "None"
    security_mode = "None"
    [[inputs.opcua.nodes]]
      name = "wind_speed"
      namespace = "1"
      identifier_type = "i"
      identifier = "2003"
      default_tags = { source="opcua_merge" }
  ```

- `name_override` is the InfluxDB measurement name — keep it in sync with
  whatever `{{SENSOR_MEASUREMENT}}` the TICKscript's
  `.measurement(...)` reads (see [`ANALYTICS.md`](ANALYTICS.md)).

## MQTT path (`{{INGEST_TRANSPORT}}=mqtt`)

- `ia-mqtt-publisher` (simulator) reads the same CSV and publishes each row
  as a JSON MQTT message to `ia-mqtt-broker`.
- **No upstream reference app uses this path** — unlike OPC-UA (which has
  `wind-turbine-anomaly-detection` to copy verbatim), there is no existing
  `apps/<name>/telegraf-config/Telegraf.conf` for MQTT in the reference
  repo. Do not hand-write the topic/payload shape from assumption — verify
  both against `simulator/mqtt-publisher/publisher.py`'s own source first.
- **Topic**: unless the Compose service passes `--topic` explicitly (the
  shared `docker-compose.yml` does not), the publisher derives it as
  `{{APP_NAME}}.split("-")[0] + "-simulation-data"` — e.g. `APP_NAME=
  heart-rate-monitor` → topic `heart-simulation-data`. Confirm this by
  reading `simulator/mqtt-publisher/publisher.py`'s `main()`, not by
  inventing a domain-looking topic (e.g. `patient/heart-rate` is wrong).
- **Payload shape**: each message is a **flat** JSON object — every CSV
  column as a top-level key, plus `source` and `filename` — not a nested
  object. Telegraf's `[[inputs.mqtt_consumer]]` must therefore use plain
  `data_format = "json"` (with `json_string_fields`/`tag_keys` for the
  non-numeric columns), **not** `json_v2` with a nested `.object` block —
  `json_v2` will silently fail to extract fields against this flat shape.
  Set `name_override` the same way as the OPC-UA path.
- Verify the actual topic and payload before wiring Telegraf:
  `docker logs ia-mqtt-publisher-1 2>&1 | grep -F 'MQTT Topic'` and
  `docker exec -it ia-mqtt-broker mosquitto_sub -h localhost -t '#' -v` to
  see real messages, rather than trusting the config until Telegraf/InfluxDB
  are confirmed populated (see the verification step below).

## Connecting a real device instead of the simulator

Per the reference guide's own three options — pick whichever matches what
the invoking prompt describes:

1. **Reuse the bundled simulator containers** but point them at a real
   dataset file (still simplest if you just need a different CSV, no protocol
   change).
2. **Swap in an existing real OPC-UA/MQTT simulator/gateway** the user
   already has — adjust the Compose service definition (image, env, network)
   to match; the Telegraf input plugin config is unaffected.
3. **Point Telegraf directly at the live device** — set `endpoint`
   (OPC-UA) or the broker host (MQTT) in `Telegraf.conf` to the real
   device/broker address, and remove the simulator service from the compose
   invocation (`--scale ia-opcua-server=0 --scale ia-mqtt-publisher=0`, or a
   compose override file that drops both).

For a **secure** OPC-UA server (TLS certs, non-anonymous auth) or a
**secure** MQTT broker (TLS, username/password), do not hand-roll the
config — follow the reference's dedicated how-to guides
(`connect-to-secure-opcua-server.md`, `connect-to-secure-mqtt-broker.md`);
they cover cert mounting and `security_policy`/`security_mode` values this
file does not repeat.

## Verifying ingestion in isolation (before wiring the UDF)

```bash
docker exec -it ia-influxdb influx -username <user> -password <pass> \
  -execute 'use datain; select * from "{{SENSOR_MEASUREMENT}}"'
```

Confirm rows are landing with plausible values **before** authoring/
troubleshooting the UDF in `references/ANALYTICS.md` — most "UDF not
receiving data" issues are actually an ingestion wiring mismatch
(wrong `identifier`, wrong topic, wrong `name_override`), not a Kapacitor
problem.
