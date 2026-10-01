# Multi-stream benchmarking reference (`{{NUM_STREAMS}}>1` only)

Only load this file when the invoking prompt asks for load-testing/scale
validation — a normal single-sensor deployment never needs it
(`{{NUM_STREAMS}}=1` is the default and skips all of this).

## What it does

`generate-telegraf-config.py` synthesizes a `Telegraf_multi_stream.conf` that
replicates the app's `[[inputs.opcua]]`/`[[inputs.mqtt_consumer]]` block
`{{NUM_STREAMS}}` times (one per simulated parallel sensor stream), so you
can validate the stack's throughput before wiring up many real devices.

```bash
python3 -m venv ./venv && . ./venv/bin/activate && python3 -m pip install -r requirements.txt
python generate-telegraf-config.py \
  --no_of_streams {{NUM_STREAMS}} \
  --log_level INFO \
  --telegraf_metric_batch_size 100 \
  --ingestion_interval 1s \
  --ingestion_type {{INGEST_TRANSPORT}} \
  --app_name {{APP_NAME}}
deactivate
```

This is invoked automatically by the Makefile's `multi_stream_check` when
`num_of_streams>1` is passed — do not run it manually unless debugging the
generation step itself:

```bash
make up_{{INGEST_TRANSPORT}}_ingestion app={{APP_NAME}} num_of_streams={{NUM_STREAMS}}
```

## What changes at runtime

- `TELEGRAF_CONFIG_PATH` switches from `Telegraf.conf` to
  `Telegraf_multi_stream.conf` automatically once `num_of_streams>1`.
- For the MQTT path, the Makefile launches **one `ia-mqtt-publisher`
  container per stream** (`ia-mqtt-publisher-1`, `-2`, ... with
  `INSTANCE_ID=$i`), each independently replaying the app's simulation CSV.
- For the OPC-UA path, `ia-opcua-server` itself is scaled
  (`--scale ia-opcua-server={{NUM_STREAMS}}`) rather than launching separate
  named containers.
- Each stream's data must be distinguishable in InfluxDB (via a tag such as
  `INSTANCE_ID` or the OPC-UA node's own per-instance namespace) — verify
  this distinguishing tag exists before claiming multi-stream ingestion
  works, otherwise all streams silently collapse into one InfluxDB series.

## Enabling point-count benchmarking (optional, separate knob)

Independent of stream count, set `number_of_data_points_per_stream=<N>` on
the `make` invocation to also flip on `ENABLE_BENCHMARKING=true` +
`BENCHMARK_TOTAL_PTS=<N>` — this caps ingestion at a fixed total point count
per stream (useful for a repeatable throughput benchmark run) rather than
continuous ingestion:

```bash
make up_opcua_ingestion app={{APP_NAME}} num_of_streams={{NUM_STREAMS}} number_of_data_points_per_stream=10000
```

## Verifying multi-stream ingestion

```bash
docker exec -it ia-influxdb influx -username <user> -password <pass> \
  -execute 'use datain; select count(*) from "{{SENSOR_MEASUREMENT}}" group by *'
```

Confirm the `group by *` output shows `{{NUM_STREAMS}}` distinct tag
combinations, each with a non-zero count — one combined series instead of
`{{NUM_STREAMS}}` separate ones means the multi-stream config did not
actually differentiate the streams.
