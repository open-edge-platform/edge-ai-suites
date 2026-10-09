# Test contracts (per mode)

Only load/author this file when `{{GENERATE_TESTS}}=yes` (asked explicitly
per mode in SKILL.md's *Questions*) — skip the `tests/` folder and its
pytest completion criteria entirely otherwise.

`pytest --collect-only -q tests/ | tail -1` should report at least the
counts noted per section below (no stubs). Mirror `metro-ai-app-recipe`'s
pytest layout (`conftest.py` with `NO_PROXY=*` + `--cacert`/`-k` handling for
the self-signed Nginx cert).

## `conftest.py` (all production modes)

- Fixtures: `host_ip`, `base_url` (`https://{host_ip}:{grafana_port}` for
  `multimodal`/`vllm`/`agentic`, `https://{host_ip}:{grafana_port}/ts-api` for
  `ts`), `mqtt_client`, `influx_client`.
- Set `NO_PROXY=*`/`no_proxy=*` for all in-process HTTP calls — same
  corporate-proxy caveat as `metro-ai-app-recipe`.

## `ts` mode (≥ 6 tests collected)

### `test_app_registration.py`

- `test_app_in_sample_app_list` — parse the Makefile, assert `{{APP_NAME}}`
  appears in `SAMPLE_APP_LIST`.
- `test_app_folder_complete` — assert all required subpaths from
  [`APPS_CONVENTION.md`](APPS_CONVENTION.md) exist under
  `apps/{{APP_NAME}}/`.

### `test_ingestion.py`

- `test_correct_simulator_running` — `docker compose ps` shows the
  `{{INGEST_TRANSPORT}}` simulator running and the other one absent
  (scaled to `0`, not merely stopped).
- `test_raw_measurement_populated` — query InfluxDB
  `{{SENSOR_MEASUREMENT}}`, assert row count increases after a known wait
  window.

### `test_analytics.py`

- `test_config_posted` — `POST /ts-api/config` (or the batch/opcua variant
  actually in use) returns 200; quote the response body.
- `test_udf_flags_known_anomaly` — feed/await a known-anomalous row, grep
  the microservice log for `Flagged anomalous point`, quote the exact line.
- `test_no_false_flag_on_normal_row` — feed a known-normal row, confirm no
  flagged line appears afterward within a bounded wait window.
- `test_single_alert_channel_only` — assert the TICKscript contains exactly
  one of `.mqtt(...)` or `.post('http://localhost:5000/opcua_alerts')`, never
  both.

### `test_alerting.py`

- If `{{ALERT_CHANNEL}}=mqtt`: subscribe `{{ALERT_TOPIC}}` on the broker
  container itself (`docker exec ia-mqtt-broker mosquitto_sub ...`), capture
  and quote the real message; assert no message for the non-triggering row.
- If `{{ALERT_CHANNEL}}=opcua`: confirm the microservice log shows a
  successful POST to `/opcua_alerts` for the triggering row.

### `test_dashboard.py`

- `test_grafana_reachable` — `GET /` (proxied Grafana) returns 200.
- `test_dashboard_matches_app` — the provisioned dashboard's title/UID
  matches `apps/{{APP_NAME}}/grafana-dashboard.json`, not a stale previous
  app's dashboard left over from `provisioning/`.

## `multimodal`/`vllm`/`agentic` modes (≥ 9 tests collected)

### `test_vision_pipeline.py`

- `test_dlsps_pipeline_running` — `GET /dsps-api/pipelines/status` shows the
  pipeline `RUNNING` within the startup timeout.
- `test_vision_mqtt_metadata` — subscribe `{{VISION_TOPIC}}`, assert a
  message with `metadata.objects` (or classification result) arrives within
  30 s of pipeline start.
- `test_vision_rtp_timestamp_present` — assert
  `metadata.rtp.sender_ntp_unix_timestamp_ns` is present **after** the
  ~300-packet warm-up window (see `PIPELINE.md`); this is the precondition
  for multimodal working at all, so test it explicitly rather than assuming.
- `test_webrtc_stream_reachable` — WHEP endpoint returns 200 once the
  pipeline is running (reuse `metro-ai-app-recipe`'s
  `test_webrtc_stream.py` assertion contract).

### `test_sensor_pipeline.py`

- `test_telegraf_ingest_influxdb` — query InfluxDB
  `{{SENSOR_MEASUREMENT}}`, assert row count increases after feeding a known
  number of simulator/test points.
- `test_ts_topic_every_point` — subscribe `{{TS_TOPIC}}`, assert a message
  arrives for **every** ingested sensor point, not just anomalies (validates
  the "always-crit" alert block in the TICKscript — see `TIMESERIES.md`).
- `test_sensor_alert_topic_anomalies_only` — feed one known-anomalous row and
  one known-normal row; assert `{{SENSOR_ALERT_TOPIC}}` receives exactly one
  message (for the anomalous row) and none for the normal row within a
  bounded wait window.

### `test_fusion_pipeline.py` (the most important file)

- `test_fusion_topic_receives_verdict` — after both a vision anomaly and a
  matching sensor anomaly are injected within `{{TOLERANCE_NS}}`, assert
  `{{FUSION_TOPIC}}` receives exactly one fused message and its
  `fused_decision` matches `{{FUSION_MODE}}` semantics.
- `test_fusion_mode_and_requires_both` (only if `{{FUSION_MODE}}=AND`) —
  inject a vision-only anomaly with no matching sensor anomaly; assert
  **no** fused-anomaly message is published (or `fused_decision=0`).
- `test_fusion_mode_or_either_suffices` (only if `{{FUSION_MODE}}=OR`) —
  inject a sensor-only anomaly with no matching vision anomaly; assert a
  fused-anomaly message **is** published.
- `test_fusion_tolerance_boundary` — inject two anomalies with a timestamp
  delta just inside `{{TOLERANCE_NS}}` (fuses) and just outside it (does not
  fuse) — this is the test most likely to catch a timestamp-parsing
  regression (see the `parse_ts_string_to_ns` caveat in `FUSION.md`).
- `test_fusion_influxdb_measurement_populated` — after a fused event, query
  the multimodal InfluxDB measurement and assert the row's `mode`/`fused_decision`
  fields match what was published on `{{FUSION_TOPIC}}`.
- `test_vision_only_measurement_always_populated` — assert the raw vision
  InfluxDB measurement receives a row for every vision message, independent
  of whether multimodal found a sensor match (validates the "write vision data
  regardless of multimodal outcome" behavior in `FUSION.md`).

### `test_dashboard.py`

- `test_grafana_reachable` — `GET /` (proxied Grafana) returns 200.
- `test_grafana_influxdb_datasource_health` — datasource health endpoint
  returns healthy.
- `test_dashboard_provisioned` — the `{{DASHBOARD_SLUG}}` dashboard exists via
  Grafana's search API.

## `vllm`/`agentic` modes — additional tests (on top of `multimodal`'s, ≥ 2 more)

### `test_explanation.py`

- `test_llm_health` — `GET /v3/config` on `apm-llm` returns 200.
- `test_batch_complete_produces_explanation` — publish a synthetic
  batch-complete MQTT event, assert one explanation output appears in the
  explainer's (`vllm-explainer` or `apm-agent`'s) `OUTPUT_DIR`, quote it
  verbatim.
- `test_fallback_mode` (only if `LLM_MODE=fallback` was selected) — assert a
  structured explanation is still produced with `apm-llm` absent/stopped.
- `agentic` mode only: `test_agent_metrics_reported` (only if
  `{{AGENT_METRICS}}=yes`) — assert `metrics-manager`/Prometheus reports at
  least one LLM-latency metric after one explanation round-trip.
