# Test contracts

Mirror `time-series-analytics-user`'s evidence bar (quote REST/log/MQTT
proof verbatim, don't just assert success) plus these scaffold-level checks.
`pytest --collect-only -q tests/ | tail -1` should report at least 6
collected tests (no stubs).

## `conftest.py`

- Fixtures: `host_ip`, `base_url` (`https://{host_ip}:{grafana_port}/ts-api`),
  `mqtt_client`, `influx_client`. Use `-k`/`--cacert` for the self-signed
  Nginx cert, `NO_PROXY=*` for all in-process HTTP calls.

## `test_app_registration.py`

- `test_app_in_sample_app_list` — parse the Makefile, assert `{{APP_NAME}}`
  appears in `SAMPLE_APP_LIST`.
- `test_app_folder_complete` — assert all required subpaths from the Layout
  section in `SKILL.md` exist under `apps/{{APP_NAME}}/`.

## `test_ingestion.py`

- `test_correct_simulator_running` — `docker compose ps` shows the
  `{{INGEST_TRANSPORT}}` simulator running and the other one absent
  (scaled to `0`, not merely stopped).
- `test_raw_measurement_populated` — query InfluxDB
  `{{SENSOR_MEASUREMENT}}`, assert row count increases after a known wait
  window.

## `test_analytics.py`

- `test_config_posted` — `POST /ts-api/config` (or the batch/opcua variant
  actually in use) returns 200; quote the response body.
- `test_udf_flags_known_anomaly` — feed/await a known-anomalous row, grep
  the microservice log for `Flagged anomalous point`, quote the exact line.
- `test_no_false_flag_on_normal_row` — feed a known-normal row, confirm no
  flagged line appears afterward within a bounded wait window.
- `test_single_alert_channel_only` — assert the TICKscript contains exactly
  one of `.mqtt(...)` or `.post('http://localhost:5000/opcua_alerts')`, never
  both.

## `test_alerting.py`

- If `{{ALERT_CHANNEL}}=mqtt`: subscribe `{{ALERT_TOPIC}}` on the broker
  container itself (`docker exec ia-mqtt-broker mosquitto_sub ...`), capture
  and quote the real message; assert no message for the non-triggering row.
- If `{{ALERT_CHANNEL}}=opcua`: confirm the microservice log shows a
  successful POST to `/opcua_alerts` for the triggering row.

## `test_dashboard.py`

- `test_grafana_reachable` — `GET /` (proxied Grafana) returns 200.
- `test_dashboard_matches_app` — the provisioned dashboard's title/UID
  matches `apps/{{APP_NAME}}/grafana-dashboard.json`, not a stale previous
  app's dashboard left over from `provisioning/`.

## `test_benchmark.py` (only when `{{NUM_STREAMS}}>1`)

- `test_multi_stream_config_generated` — `Telegraf_multi_stream.conf` exists
  and contains `{{NUM_STREAMS}}` input blocks.
- `test_streams_distinguishable_in_influxdb` — `group by *` query returns
  `{{NUM_STREAMS}}` distinct series, each with non-zero row count.
