# Nginx + Grafana reference

## Nginx (single TLS entrypoint)

- HTTP :80 → 301 to HTTPS :443.
- Self-signed cert MUST include SAN `IP:127.0.0.1,IP:${HOST_IP},DNS:localhost` — browsers reject certs without SAN.
- Upstreams: `dlstreamer-pipeline-server:8080`, `grafana:3000`, `node-red:1880`, `mediamtx-server:8889` (WHEP/WHIP + player), `mediamtx-server:8189` (WebRTC ICE local TCP).
- Locations:
  - `/api/` → DLSPS
  - `/grafana/` → Grafana (headers `X-Frame-Options ALLOWALL`, `Content-Security-Policy "frame-ancestors *"`, WS upgrade)
  - `/grafana/api/live/ws` → Grafana WS
  - `/nodered/` → Node-RED (WS upgrade)
  - `/mediamtx/` → MediaMTX `:8889` (WHEP player page for iframes)
  - `/webrtc/` → MediaMTX `:8189` (WebRTC ICE over TCP)
  - `~ ^/({{DETECTIONS_TOPIC_PREFIX}}_[^/]+)/(whep|whip)(/.*)?$` → MediaMTX `:8889` WHEP/WHIP signalling (with CORS + OPTIONS preflight)
- Grafana env: `GF_SERVER_ROOT_URL=https://localhost/grafana/`, `GF_SERVER_SERVE_FROM_SUB_PATH=true`, **`GF_SECURITY_ALLOW_EMBEDDING=true`** (WebRTC iframes).
- **With `SERVE_FROM_SUB_PATH=true`, `/grafana/` `proxy_pass` MUST NOT end in `/`.** Trailing slash strips Grafana prefix → 301 loop → blank spinner. Correct:
  ```nginx
  location /grafana/ { proxy_pass http://grafana:3000; ... }   # NO trailing slash
  ```

WebRTC blocks (WS upgrade on all three; CORS on WHEP/WHIP regex):
```nginx
upstream mediamtx        { server mediamtx-server:8889; }
upstream mediamtx-webrtc { server mediamtx-server:8189; }

# WHEP player page embedded by Grafana iframes
location /mediamtx/ {
    proxy_pass http://mediamtx/;
    proxy_set_header Host $host;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

# WebRTC ICE over local TCP (MediaMTX 8189)
location /webrtc/ {
    proxy_pass http://mediamtx-webrtc/;
    proxy_set_header Host $host;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

# WHEP/WHIP signalling per stream path
location ~ ^/({{DETECTIONS_TOPIC_PREFIX}}_[^/]+)/(whep|whip)(/.*)?$ {
    proxy_pass http://mediamtx/$1/$2$3;
    proxy_set_header Host $host;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
    add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    if ($request_method = OPTIONS) {
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
        return 204;
    }
}
```

## Grafana video panels (WebRTC iframe)

Text panel, HTML mode, one per source. Embed MediaMTX WHEP player; `${WEBRTC_URL}` resolves to `https://<HOST>/mediamtx/` (set by `update_dashboard.sh`):
```html
<iframe
  src="${WEBRTC_URL}{{DETECTIONS_TOPIC_PREFIX}}_1/"
  style="width:100%;height:100%;border:0"
  allow="autoplay; encrypted-media">
</iframe>
```
- Requires `GF_PANELS_DISABLE_SANITIZE_HTML=true` (HTML panel) AND `GF_SECURITY_ALLOW_EMBEDDING=true` (iframe embedding).
- Trailing slash on `.../{{DETECTIONS_TOPIC_PREFIX}}_1/` is required; MediaMTX serves reader page at path root.
- Stream appears only after `sample_start.sh` launches pipelines (DLSPS is WHIP publisher); before then: "waiting".

## Grafana provisioning

- `src/grafana/datasources.yml`:
  - `grafana-mqtt-datasource` → broker URI in **`jsonData.uri`** (default `tcp://broker:1883`)
  - `yesoreyeram-infinity-datasource` (arbitrary REST/JSON panels)
- **CRITICAL — MQTT datasource address goes in `jsonData.uri` ONLY** (plugin v1.3.3 reads `Options.URI` from json key `uri`). Top-level `url:` and `jsonData.host`/`jsonData.port` are IGNORED. Wrong key provisions green but health says **"Error connecting to MQTT broker. Network error dial tcp: missing address"**; panels stay empty. Correct:
  ```yaml
  apiVersion: 1
  datasources:
    - name: MQTT
      uid: mqtt_ds
      type: grafana-mqtt-datasource
      access: proxy
      isDefault: true
      jsonData:
        uri: tcp://broker:1883
      editable: true
  ```
  Provisioning applies only at startup; `docker compose restart grafana` after edits. Verify with `curl --cacert src/nginx/ssl/server.crt --noproxy '*' -s -u admin:admin https://localhost/grafana/api/datasources/uid/mqtt_ds/health` → `"status":"OK","message":"MQTT Connected"`.
- **grafana-mqtt-datasource v1.3.3 caveat:** target must be exact scalar topic; wildcards silently drop. Node-RED MUST publish `{{COUNT_TOPIC}}`, `{{COUNT_TOPIC}}/<sourceId>`, `stats/alert_active`, `stats/alert_total` as plain numbers (NOT JSON). Older versions broken — do NOT downgrade.
- `src/grafana/dashboards.yml` → `/var/lib/grafana/dashboards`; write `{{DASHBOARD_SLUG}}.json`. Rows:
  1. Numeric MQTT panels: `{{COUNT_TOPIC}}`, `stats/alert_active`, `stats/alert_total`.
  2. Alert log (MQTT topic `{{ALERT_TOPIC}}`, JSON payload → table panel).
  3. {{NUM_SOURCES}} Text/HTML panels, each `<iframe>` WebRTC player `${WEBRTC_URL}{{DETECTIONS_TOPIC_PREFIX}}_X/`. Define hidden constant `WEBRTC_URL` with `HOST_IP_PLACEHOLDER`; `update_dashboard.sh` rewrites to `https://<HOST>/mediamtx/`.
- Grafana `environment:` MUST include:
  ```yaml
  GF_INSTALL_PLUGINS: "grafana-mqtt-datasource 1.3.3,yesoreyeram-infinity-datasource 3.11.1"
  GF_SERVER_ROOT_URL: "https://localhost/grafana/"
  GF_SERVER_SERVE_FROM_SUB_PATH: "true"
  GF_PANELS_DISABLE_SANITIZE_HTML: "true"
  GF_SECURITY_ALLOW_EMBEDDING: "true"
  ```

## Mosquitto

`src/mosquitto/config/mosquitto.conf`:
```
allow_anonymous true
listener 1883
```
Only reachable on `app_network`; NOT published to host.
