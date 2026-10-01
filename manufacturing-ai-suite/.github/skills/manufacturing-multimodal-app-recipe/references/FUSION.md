# Fusion Analytics reference (the correlator — this skill's core)

No delegate skill exists for this component yet — author it from these
templates directly (Python, `paho-mqtt` + `influxdb` client + a small FastAPI
health/API app), matching the reference `fusion-analytics/` service
(`Dockerfile`, `fusion.py`, `api.py`, `requirements.txt`).

## Responsibilities

1. Subscribe to **both** MQTT topics: `{{VISION_TOPIC}}` (DLSPS) and
   `{{TS_TOPIC}}` (Time Series Analytics Microservice, *every* processed
   point — not just the alert-only topic).
2. Buffer each stream in a bounded rolling deque (`BUFFER_SIZE`, default
   `100`–`1000`).
3. Match one vision message with one sensor message whose timestamps are
   within `{{TOLERANCE_NS}}` of each other.
4. Apply `{{FUSION_MODE}}` (`AND`/`OR`) to the two per-modality anomaly
   flags to produce one fused decision.
5. Write the fused verdict + raw vision metadata to InfluxDB, and publish
   the fused verdict on `{{FUSION_TOPIC}}`.

## Required env

```
MQTT_BROKER=ia-mqtt-broker
MQTT_PORT=1883
VISION_TOPIC={{VISION_TOPIC}}
TS_TOPIC={{TS_TOPIC}}
FUSION_TOPIC={{FUSION_TOPIC}}
BUFFER_SIZE=100
TOLERANCE_NS={{TOLERANCE_NS}}            # e.g. 50e6 = 50 ms
FUSION_MODE={{FUSION_MODE}}              # "AND" or "OR" — validate at startup, raise on anything else
INFLUXDB_HOST=ia-influxdb
INFLUXDB_PORT=8086
INFLUXDB_DB=datain
INFLUXDB_USERNAME=${INFLUXDB_USERNAME}
INFLUXDB_PASSWORD=${INFLUXDB_PASSWORD}
```

## Timestamp handling — the trickiest part

- **Vision side:** timestamp comes from
  `payload["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]` — only present
  when the DLSPS pipeline set `add-reference-timestamp-meta=true` on
  `rtspsrc` **and** `add-rtp-timestamp=true` on `gvametaconvert` (see
  [PIPELINE.md](PIPELINE.md)). If that key is missing, log a warning and skip
  fusion for that frame rather than crashing — DLSPS may omit it for the
  first ~300 packets after a (re)start.
- **Sensor side:** timestamp comes from the TICKscript alert's
  `{{ index .Time }}` field, formatted like
  `"YYYY-MM-DD HH:MM:SS.fffffffff +0000 UTC"`. Parse it defensively — accept
  a space or `T` separator, optional fractional seconds up to 9 digits, and
  an optional (sometimes duplicated) timezone offset suffix. See the
  reference `parse_ts_string_to_ns()` for the exact regex-based parser; reuse
  it verbatim rather than a naive `datetime.strptime` (the reference
  implementation exists specifically because Kapacitor's raw timestamp
  string format is inconsistent across builds).
- Convert **both** sides to epoch nanoseconds on ingest so
  `find_nearest()`/tolerance comparisons are a plain integer `abs(diff)`
  check against `{{TOLERANCE_NS}}`.

## Fusion algorithm — first-come-first-served pairing

Do not naively fuse "latest vision + latest sensor" — messages arrive at
different rates and out of lockstep. Use first-come-first-served pairing:

1. Peek the oldest message in each queue.
2. Whichever queue's oldest message has the smaller timestamp is the
   **source**; pop it.
3. Search the **other** queue for the entry with the nearest timestamp
   (`find_nearest`); if the nearest diff exceeds `{{TOLERANCE_NS}}`, there is
   no match — emit a partial/no-fusion result (both per-modality anomaly
   flags recorded as `0`, no fused alert) rather than blocking.
4. If a match is found, pop it from the target queue too and combine the two
   per-modality anomaly flags with `{{FUSION_MODE}}`:
   - `AND`: fused anomaly = `vision_anomaly AND timeseries_anomaly`
   - `OR`: fused anomaly = `vision_anomaly OR timeseries_anomaly`
5. When labels disagree between modalities, resolve one human-readable label
   by taking whichever side has higher confidence (see
   `combine_classifications()` in the reference implementation) — do not
   just report both labels unresolved, downstream Grafana panels expect one
   `predicted_category` string.

## InfluxDB writes — two separate concerns

- **Raw vision metadata** — write every vision message to a
  `VISION_MEASUREMENT` (e.g. `vision-weld-classification-results`) regardless
  of fusion outcome, tagged with `label`/`confidence`/`search_time`, so
  Grafana can show a vision-only trend even when no sensor match was found.
  This happens in the MQTT `on_message` callback, not in the fusion step.
- **Fused verdict** — write only on an actual successful pairing, to a
  separate `FUSION_MEASUREMENT` (e.g. `fusion-anomaly-detection-results`),
  including both source timestamps, the timestamp delta, `{{FUSION_MODE}}`,
  and the fused decision.

## MQTT publish — the fused verdict

```json
{
  "fused_decision": 1,
  "mode": "{{FUSION_MODE}}",
  "vision_anomaly": 1,
  "timeseries_anomaly": 0,
  "predicted_category": "Porosity with Excessive Penetration",
  "vision_time": "2026-09-08T12:00:00.123Z",
  "timeseries_time": "2026-09-08T12:00:00.150Z",
  "delta_ms": 27.0
}
```

Publish this to `{{FUSION_TOPIC}}` with QoS 1. Keep the payload **flat JSON
with scalar `fused_decision`**, not a nested object — Grafana's MQTT
datasource plots scalars directly; a nested/array payload breaks the panel
(same caveat as `metro-ai-app-recipe`'s count-topic rule).

## Health/API surface

Expose a small FastAPI app (`api.py` in the reference) on a fixed port
(e.g. `8080`) with at minimum a `/health` endpoint the container healthcheck
can hit, and (optionally) a query endpoint the Agentic layer's
`STORAGE_SERVICE_URL` can call to retrieve a recent fused-event batch — this
is the integration point `references/AGENTIC.md` depends on when
`{{AGENTIC}}=yes`.

## Verifying fusion end-to-end

```bash
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '{{FUSION_TOPIC}}' -p 1883
docker exec -it ia-influxdb influx -username <user> -password <pass> \
  -execute 'use datain; select * from "<fusion-measurement>"'
```

Confirm a fused message appears **only** after both a vision anomaly and a
sensor anomaly (for `AND`) or either one (for `OR`) land within
`{{TOLERANCE_NS}}` — inject one modality's anomaly without the other and
confirm the fusion behavior matches `{{FUSION_MODE}}` exactly (this is the
single most important test in [`TESTS.md`](TESTS.md)).
