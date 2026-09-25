# Nginx + Grafana reference

## Nginx — single TLS entrypoint

One `server { listen 15443 ssl; }` block (mapped to host `${GRAFANA_PORT}`),
self-signed cert generated at container start (`nginx-cert-gen.sh`, mounted
to a tmpfs volume). Routes:

| Path | Proxies to | Notes |
|---|---|---|
| `/ts-api/` | `ia-time-series-analytics-microservice:5000` | rewrite strips the `/ts-api` prefix, same as `manufacturing-multimodal-app-recipe` |
| `/` | `ia-grafana` | default catch-all |

Optionally uncomment the `stream { ... }` block at the top of `nginx.conf`
to also TLS-proxy raw MQTT on port `1883` for external (non-Compose-network)
MQTT clients — most deployments don't need this since MQTT stays internal to
`timeseries_network`; only enable it if a real external device/consumer must
reach the broker directly.

## Grafana — one dashboard file per app

Unlike `manufacturing-multimodal-app-recipe`'s `dashboards_jsons/` directory
convention, this repo mounts a **single file directly**:

```yaml
volumes:
  - ./apps/${SAMPLE_APP}/grafana-dashboard.json:/etc/grafana/provisioning/dashboards/grafana-dashboard.json
```

Which means switching `SAMPLE_APP` (via `app=` on `make up_*`) automatically
swaps the provisioned dashboard on the next `docker compose up` — no
copy-into-provisioning step is needed here (contrast with the multimodal
recipe's `Makefile`, which must `rm`+`cp` because it uses a directory of
JSON files instead).

Dashboard JSON needs at minimum:

- **Sensor trend panel(s)** — InfluxDB query against
  `{{SENSOR_MEASUREMENT}}` (raw) and `{{SENSOR_MEASUREMENT}}-anomaly-data` or
  equivalent (UDF output), so both raw and flagged data are visible together.
- **Alert/anomaly indicator** — a stat/table panel highlighting rows where
  `anomaly_status > 0`.
- No WebRTC/video panel needed — this stack has no vision component.
- Grafana's minimum refresh interval is 5 s — note this in any generated
  README so users don't mistake a few seconds of lag for a bug.

`configs/grafana/dashboards/datasources.yml` (repo-root, shared across all
apps) provisions the InfluxDB datasource — do not duplicate it per app;
only `grafana-dashboard.json` is per-app.
