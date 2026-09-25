# Test contracts

Mirror `metro-ai-app-recipe`'s pytest layout (`conftest.py` with
`NO_PROXY=*` + `--cacert`/`-k` handling for the self-signed Nginx cert) and
add fusion-specific assertions. `pytest --collect-only -q tests/ | tail -1`
should report at least the tests below (≥ 9 collected total, no stubs).

## `conftest.py`

- Fixtures: `host_ip`, `base_url` (`https://{host_ip}:{grafana_port}`),
  `mqtt_client` (connects to the broker via the exposed/compose network),
  `influx_client`.
- Set `NO_PROXY=*`/`no_proxy=*` for all in-process HTTP calls — same
  corporate-proxy caveat as `metro-ai-app-recipe`.

## `test_vision_pipeline.py`

- `test_dlsps_pipeline_running` — `GET /dsps-api/pipelines/status` shows the
  pipeline `RUNNING` within the startup timeout.
- `test_vision_mqtt_metadata` — subscribe `{{VISION_TOPIC}}`, assert a
  message with `metadata.objects` (or classification result) arrives within
  30 s of pipeline start.
- `test_vision_rtp_timestamp_present` — assert
  `metadata.rtp.sender_ntp_unix_timestamp_ns` is present **after** the
  ~300-packet warm-up window (see `PIPELINE.md`); this is the precondition
  for fusion working at all, so test it explicitly rather than assuming.
- `test_webrtc_stream_reachable` — WHEP endpoint returns 200 once the
  pipeline is running (reuse `metro-ai-app-recipe`'s
  `test_webrtc_stream.py` assertion contract).

## `test_sensor_pipeline.py`

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

## `test_fusion_pipeline.py` (the most important file)

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
  the fusion InfluxDB measurement and assert the row's `mode`/`fused_decision`
  fields match what was published on `{{FUSION_TOPIC}}`.
- `test_vision_only_measurement_always_populated` — assert the raw vision
  InfluxDB measurement receives a row for every vision message, independent
  of whether fusion found a sensor match (validates the "write vision data
  regardless of fusion outcome" behavior in `FUSION.md`).

## `test_dashboard.py`

- `test_grafana_reachable` — `GET /` (proxied Grafana) returns 200.
- `test_grafana_influxdb_datasource_health` — datasource health endpoint
  returns healthy.
- `test_dashboard_provisioned` — the `{{DASHBOARD_SLUG}}` dashboard exists via
  Grafana's search API.
