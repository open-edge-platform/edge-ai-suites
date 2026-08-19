# Nginx + Grafana reference

## Nginx (single TLS entrypoint)

- HTTP :80 → 301 to HTTPS :443.
- Self-signed cert MUST include SAN
  `IP:127.0.0.1,IP:${HOST_IP},DNS:localhost` — modern browsers reject
  certs without SAN.
- Upstreams: `dlstreamer-pipeline-server:8080`, `grafana:3000`,
  `node-red:1880`, `mediamtx-server:8889` (WHEP/WHIP + player),
  `mediamtx-server:8189` (WebRTC ICE local TCP).
- Locations:
  - `/api/` → DLSPS
  - `/grafana/` → Grafana (headers `X-Frame-Options ALLOWALL`,
    `Content-Security-Policy "frame-ancestors *"`, WS upgrade)
  - `/grafana/api/live/ws` → Grafana WS
  - `/nodered/` → Node-RED (WS upgrade)
  - `/mediamtx/` → MediaMTX `:8889` (WHEP player page for iframes)
  - `/webrtc/` → MediaMTX `:8189` (WebRTC ICE over TCP)
  - `~ ^/({{DETECTIONS_TOPIC_PREFIX}}_[^/]+)/(whep|whip)(/.*)?$` →
    MediaMTX `:8889` WHEP/WHIP signalling (with CORS + OPTIONS preflight)
- Grafana env: `GF_SERVER_ROOT_URL=https://localhost/grafana/`,
  `GF_SERVER_SERVE_FROM_SUB_PATH=true`, and **`GF_SECURITY_ALLOW_EMBEDDING=true`**
  (WebRTC panels are iframes → without this Grafana refuses to embed them).
- **With `SERVE_FROM_SUB_PATH=true`, `proxy_pass` for `/grafana/` MUST NOT
  end in `/`.** Trailing slash strips the prefix Grafana expects → 301
  loop → blank spinner. Correct:
  ```nginx
  location /grafana/ { proxy_pass http://grafana:3000; ... }   # NO trailing slash
  ```

WebRTC blocks (WS upgrade on all three; CORS on the WHEP/WHIP regex):
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

Text panel, HTML mode, one per source. Embed MediaMTX's built-in WHEP
player via an iframe; `${WEBRTC_URL}` is a dashboard variable resolving to
`https://<HOST>/mediamtx/` (set by `update_dashboard.sh`):
```html
<iframe
  src="${WEBRTC_URL}{{DETECTIONS_TOPIC_PREFIX}}_1/"
  style="width:100%;height:100%;border:0"
  allow="autoplay; encrypted-media">
</iframe>
```
- Requires `GF_PANELS_DISABLE_SANITIZE_HTML=true` (HTML panel) AND
  `GF_SECURITY_ALLOW_EMBEDDING=true` (iframe embedding).
- The trailing slash on `.../{{DETECTIONS_TOPIC_PREFIX}}_1/` is required —
  MediaMTX serves the reader page at the path root.
- The stream only appears after `sample_start.sh` launches the pipelines
  (DLSPS is the WHIP publisher); before that the player shows "waiting".

## Grafana provisioning

- `src/grafana/datasources.yml`:
  - `grafana-mqtt-datasource` → broker URI in **`jsonData.uri`** (default
    `tcp://broker:1883`)
  - `yesoreyeram-infinity-datasource` (arbitrary REST/JSON panels)
- **CRITICAL — MQTT datasource address goes in `jsonData.uri` ONLY**
  (verified plugin v1.3.3, backend reads `Options.URI` from json key
  `uri`). The top-level `url:` field and `jsonData.host`/`jsonData.port`
  are IGNORED by this plugin. Getting this wrong yields a green-looking
  provision but **"Error connecting to MQTT broker. Network error dial
  tcp: missing address"** and every MQTT panel stays empty. Correct block:
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
  Datasource provisioning is applied only at Grafana startup, so
  `docker compose restart grafana` after editing. Verify with
  `curl --cacert src/nginx/ssl/server.crt --noproxy '*' -s -u admin:admin
  https://localhost/grafana/api/datasources/uid/mqtt_ds/health` → expect
  `"status":"OK","message":"MQTT Connected"`.
- **grafana-mqtt-datasource v1.3.3 caveat:** panel target must be an
  exact scalar topic; wildcards silently drop. So Node-RED MUST publish
  `{{COUNT_TOPIC}}`, `{{COUNT_TOPIC}}/<sourceId>`, `stats/alert_active`,
  `stats/alert_total` as plain numbers (NOT JSON). Older versions broken
  — do NOT downgrade.
- `src/grafana/dashboards.yml` → `/var/lib/grafana/dashboards`; write
  `{{DASHBOARD_SLUG}}.json` there. Dashboard rows:
  1. Numeric MQTT panels: `{{COUNT_TOPIC}}`, `stats/alert_active`, `stats/alert_total`.
  2. Alert log (MQTT topic `{{ALERT_TOPIC}}`, JSON payload → table panel).
  3. {{NUM_SOURCES}} Text/HTML panels, each an `<iframe>` WebRTC player
     `${WEBRTC_URL}{{DETECTIONS_TOPIC_PREFIX}}_X/`. Define a dashboard
     `templating` variable `WEBRTC_URL` (constant, hidden) with a
     `HOST_IP_PLACEHOLDER`-based default that `update_dashboard.sh`
     rewrites to `https://<HOST>/mediamtx/`.
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
Only reachable on `app_network`; NOT published to the host.
