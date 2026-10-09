# Fusion Analytics reference (the correlator — core of `multimodal`/`vllm`/`agentic` modes)

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
6. (`vllm`/`agentic` modes only) Accumulate fused verdicts in a batch and
   publish a **batch-complete** MQTT event on `{{MQTT_BATCH_TOPIC}}` (e.g.
   `vllm/batch-complete` or `apm/batch-complete`) once the configured trigger
   fires — this is Fusion Analytics' own responsibility, not a separate
   service: no extra "batching shim" container exists in the generated
   layout. See *Batching for the explanation layer* below.

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

# vllm/agentic modes only — batch-complete trigger (see "Batching for the
# explanation layer" below); omit entirely for plain multimodal mode
MQTT_BATCH_TOPIC={{MQTT_BATCH_TOPIC}}    # vllm/batch-complete (vllm) or apm/batch-complete (agentic)
BATCH_TRIGGER_MODE={{BATCH_TRIGGER_MODE}} # "size" or "time" — validate at startup
BATCH_SIZE={{BATCH_SIZE}}                # fused verdicts per batch, when BATCH_TRIGGER_MODE=size (e.g. 10)
BATCH_INTERVAL_S={{BATCH_INTERVAL_S}}    # seconds between flushes, when BATCH_TRIGGER_MODE=time (e.g. 30)
```

## Timestamp handling — the trickiest part

- **Vision side:** timestamp comes from
  `payload["metadata"]["rtp"]["sender_ntp_unix_timestamp_ns"]` — only present
  when the DLSPS pipeline set `add-reference-timestamp-meta=true` on
  `rtspsrc` **and** `add-rtp-timestamp=true` on `gvametaconvert` (see
  [PIPELINE.md](PIPELINE.md)). If that key is missing, log a warning and skip
  multimodal for that frame rather than crashing — DLSPS may omit it for the
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

## Multimodal algorithm — first-come-first-served pairing

Do not naively fuse "latest vision + latest sensor" — messages arrive at
different rates and out of lockstep. Use first-come-first-served pairing:

1. Peek the oldest message in each queue.
2. Whichever queue's oldest message has the smaller timestamp is the
   **source**; pop it.
3. Search the **other** queue for the entry with the nearest timestamp
   (`find_nearest`); if the nearest diff exceeds `{{TOLERANCE_NS}}`, there is
   no match — do not block waiting for one. What happens next depends on
   `{{FUSION_MODE}}`:
   - `AND`: an unmatched source can never satisfy `AND` on its own, so emit
     no fused alert (both per-modality anomaly flags recorded as `0`).
   - `OR`: an unmatched source's own anomaly flag is already sufficient to
     satisfy `OR`, so if the source message is itself anomalous, still
     publish a fused verdict using only the source's flag (the missing
     modality's flag recorded as `0`, its timestamp/delta fields omitted);
     if the source message is not anomalous, emit no fused alert.
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
  of multimodal outcome, tagged with `label`/`confidence`/`search_time`, so
  Grafana can show a vision-only trend even when no sensor match was found.
  This happens in the MQTT `on_message` callback, not in the multimodal step.
- **Fused verdict** — write only on an actual successful pairing, to a
  separate `FUSION_MEASUREMENT` (e.g. `multimodal-anomaly-detection-results`),
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
can hit, and (optionally) a query endpoint the `vllm`/`agentic` layer's
`STORAGE_SERVICE_URL` can call to retrieve a recent fused-event batch — this
is the integration point [`references/VLM.md`](VLM.md) depends on when
`{{DEPLOYMENT}}` is `vllm` or `agentic`.

**InfluxQL injection warning — do not copy the reference's query-building
verbatim.** The reference `api.py`'s `/detections?label=...` endpoint
interpolates the `label` query parameter directly into an InfluxQL string
(`f"fusion_classification = '{label}'"`) — it defines a `_SAFE_LABEL_RE`
allowlist regex but never actually applies it, so a crafted `label` value
breaks out of the string literal and injects arbitrary InfluxQL. Any query
endpoint built from this template **must** validate/allowlist every
user-supplied filter value (e.g. `_SAFE_LABEL_RE.fullmatch(label)`, rejecting
with 400 on failure) before interpolating it into a query string — never
trust `_SAFE_LABEL_RE` being merely *defined* as evidence it's *enforced*.

## Batching for the explanation layer (`vllm`/`agentic` modes only)

Fusion Analytics itself maintains the batch, in addition to its per-event
fused-verdict write/publish above — there is no separate batching
microservice in the generated layout:

- Append every fused verdict (step 4/5 above) to an in-memory batch list.
- When `BATCH_TRIGGER_MODE=size`, flush once the list reaches `BATCH_SIZE`
  entries; when `=time`, flush every `BATCH_INTERVAL_S` seconds regardless
  of size (use a background timer/thread, not a blocking sleep in the MQTT
  callback).
- On flush: publish an empty-payload (or `{"count": N}`) MQTT message to
  `{{MQTT_BATCH_TOPIC}}`, then clear the batch. The accumulated batch itself
  is retrieved by `vllm-explainer`/`apm-agent` via the `/health` surface's
  query endpoint above, keyed by `STORAGE_SERVICE_URL`, **not** carried in
  the MQTT payload.
- Ask the user for `{{BATCH_TRIGGER_MODE}}`/`{{BATCH_SIZE}}`/
  `{{BATCH_INTERVAL_S}}` explicitly during planning (see SKILL.md's `vllm`
  mode questions) — do not silently default this, an unset trigger means
  the explanation layer never receives any input.

## Verifying multimodal end-to-end

```bash
docker exec -ti ia-mqtt-broker mosquitto_sub -h localhost -v -t '{{FUSION_TOPIC}}' -p 1883
docker exec -it ia-influxdb influx -username <user> -password <pass> \
  -execute 'use datain; select * from "<multimodal-measurement>"'
```

Confirm a fused message appears **only** after both a vision anomaly and a
sensor anomaly (for `AND`) or either one, matched **or unmatched** (for
`OR`) land within/without `{{TOLERANCE_NS}}` — inject one modality's anomaly
without the other and confirm the multimodal behavior matches `{{FUSION_MODE}}`
exactly (if `{{GENERATE_TESTS}}=yes`, this is the single most important test
in [`TESTS.md`](TESTS.md); otherwise verify it manually).
