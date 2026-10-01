# Nginx + Grafana + Mosquitto + SeaweedFS reference

## Nginx — single TLS entrypoint, path-based routing

One `server { listen ${GRAFANA_PORT_INTERNAL} ssl; }` block (reference uses
`15443` internally, mapped to host `${GRAFANA_PORT}` e.g. `3000`), self-signed
cert generated at container start (`nginx-cert-gen.sh`, mounted to a tmpfs
volume so the cert regenerates fresh each deploy). Routes:

| Path | Proxies to | Notes |
|---|---|---|
| `/ts-api` | `ia-time-series-analytics-microservice:5000` | `rewrite ^/ts-api/(.*)$ /$1 break` — strips prefix |
| `/dsps-api/` | `dlstreamer-pipeline-server:8080` | trailing slash on both sides — no rewrite needed |
| `/image-store` | `seaweedfs-filer:8888` | needs `sub_filter` rewrites on `href=`/`action=`/`fetch(`/`location.href=` so the filer's browser UI's absolute links stay under `/image-store/` |
| `/{{peer-id}}/whip\|whep` | `${MEDIAMTX_SERVER}:${WHIP_SERVER_PORT}` (regex match) | WebRTC signalling; needs `Upgrade`/`Connection: upgrade` headers + long timeouts (300s) for long-lived WebRTC negotiation |
| `/{{peer-id}}/` (prefix, non-signalling) | MediaMTX WHEP/HLS asset paths | separate `location ^~` block below the exact regex match so static asset requests don't fall through to `/` |
| `/` | `ia-grafana` | default catch-all; Grafana behind `GF_SERVER_SERVE_FROM_SUB_PATH` if you additionally proxy other UIs at non-root paths |

Reuse `metro-ai-app-recipe`'s WHIP/WHEP + `--noproxy '*'` guidance from
[`PROXY_UI.md`](../metro-ai-app-recipe/references/PROXY_UI.md) verbatim for
the MediaMTX signalling block; the only difference here is the additional
`/ts-api`, `/dsps-api/`, and `/image-store` proxies this stack needs that
`metro-ai-app-recipe` doesn't.

## Grafana — InfluxDB datasource + MQTT (optional) + WebRTC iframe

`configs/grafana/provisioning/datasources.yml` — one InfluxDB datasource is
**required** (fusion/vision/sensor measurements all live there); an MQTT
datasource (`grafana-mqtt-datasource` plugin, same caveat as
`metro-ai-app-recipe`: pin to a Grafana version the plugin supports) is
**optional**, only add it if the dashboard needs a live low-latency panel on
`{{FUSION_TOPIC}}` in addition to the InfluxDB-backed historical panels:

```yaml
datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://$INFLUX_SERVER:8086
    user: $INFLUXDB_USERNAME
    password: $INFLUXDB_PASSWORD
    database: $INFLUXDB_DB
    basicAuth: true
    basicAuthUser: $INFLUXDB_USERNAME
    isDefault: true
    jsonData: { graphiteVersion: "1.1" }
    secureJsonData:
      basicAuthPassword: $INFLUXDB_PASSWORD
      password: $INFLUXDB_PASSWORD
```

Dashboard JSON (`configs/grafana/dashboards_jsons/{{DASHBOARD_SLUG}}.json`,
copied into `provisioning/` at install time — see `INSTALL.md`) needs at
minimum:

- **WebRTC `<iframe>` panel** — `src="/<peer-id>/whep"` or whatever exact
  path your Nginx WHEP route resolves to; requires
  `GF_SECURITY_ALLOW_EMBEDDING=true` + `GF_PANELS_DISABLE_SANITIZE_HTML=true`
  env vars on the Grafana container, otherwise the iframe is stripped.
- **Sensor trend panel** — InfluxDB query against
  `{{SENSOR_MEASUREMENT}}-anomaly-data`.
- **Fusion verdict table/stat panel** — InfluxDB query against the fusion
  measurement, or an MQTT panel on `{{FUSION_TOPIC}}` if the MQTT datasource
  is configured.
- Grafana's minimum refresh interval is 5 s — tell the user in the README
  that graph/video sync may lag by a few seconds; this is expected, not a
  bug.

## Mosquitto

Minimal `mosquitto.conf` is sufficient for this stack (no TLS/ACL needed
inside the Compose network):

```
allow_anonymous true
listener 1883
```

Tighten this (ACLs, TLS listener, auth) only if a real (non-simulator) sensor
device connects over the network rather than from inside the Compose
network.

## SeaweedFS — S3-compatible stored-frame storage

Four services: `seaweedfs-master` (metadata), `seaweedfs-volume` (blob
storage), `seaweedfs-filer` (POSIX-like directory view + the `/image-store`
UI proxied above), `seaweedfs-s3` (S3 gateway DLSPS's `s3_write` destination
talks to). Bring them up in that dependency order
(`master → volume → filer → s3`, each with a `depends_on` + healthcheck gate).

`seaweedfs-s3` needs `DEFAULT_S3_BUCKETS=dlstreamer-pipeline-results` (or
whatever bucket name `PIPELINE.md`'s `s3_write.bucket` uses) baked into its
init script so the bucket exists before DLSPS's first frame write; also set
`S3_BUCKET_TTL` (e.g. `30m`) so stored frames don't grow the disk unbounded —
this is a demo/production-lite retention knob, not meant for long-term
archival.
