# Nginx + Grafana reference

## Nginx (single TLS entrypoint)

- HTTP :80 → 301 to HTTPS :443.
- Self-signed cert MUST include SAN
  `IP:127.0.0.1,IP:${HOST_IP},DNS:localhost` — modern browsers reject
  certs without SAN.
- Upstreams: `dlstreamer-pipeline-server:8080`, `grafana:3000`,
  `node-red:1880`.
- Locations:
  - `/api/` → DLSPS
  - `/grafana/` → Grafana (headers `X-Frame-Options ALLOWALL`,
    `Content-Security-Policy "frame-ancestors *"`, WS upgrade)
  - `/grafana/api/live/ws` → Grafana WS
  - `/nodered/` → Node-RED (WS upgrade)
  - `/frames/` → static files from `/usr/share/nginx/html/frames/`
    (bind-mount of shared `frames` volume)
- Grafana env: `GF_SERVER_ROOT_URL=https://localhost/grafana/`,
  `GF_SERVER_SERVE_FROM_SUB_PATH=true`.
- **With `SERVE_FROM_SUB_PATH=true`, `proxy_pass` for `/grafana/` MUST NOT
  end in `/`.** Trailing slash strips the prefix Grafana expects → 301
  loop → blank spinner. Correct:
  ```nginx
  location /grafana/ { proxy_pass http://grafana:3000; ... }   # NO trailing slash
  ```

Frames block:
```nginx
location /frames/ {
    alias /usr/share/nginx/html/frames/;
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header Access-Control-Allow-Origin "*" always;
    expires -1;
    try_files $uri =404;
}
```

## Grafana video panels (MJPEG polling)

Text panel, HTML mode, one per source:
```html
<div style="background:#000;width:100%;height:100%">
  <img id="cam1" style="width:100%;height:100%;object-fit:contain"
       src="/frames/{{DETECTIONS_TOPIC_PREFIX}}_1.jpg?t=0">
</div>
<script>
(function(){
  const img = document.getElementById('cam1');
  const url = '/frames/{{DETECTIONS_TOPIC_PREFIX}}_1.jpg';
  const period = Math.round(1000 / {{MJPEG_FPS}});
  function tick(){ img.src = url + '?t=' + Date.now(); }
  img.onload  = () => setTimeout(tick, period);
  img.onerror = () => setTimeout(tick, 1000);
  tick();
})();
</script>
```
- Requires `GF_PANELS_DISABLE_SANITIZE_HTML=true`.
- No iframe → do NOT need `GF_SECURITY_ALLOW_EMBEDDING`.
- Poll rate must match pipeline `videorate` cap.

## Grafana provisioning

- `src/grafana/datasources.yml`:
  - `grafana-mqtt-datasource` → `tcp://broker:1883` (default)
  - `yesoreyeram-infinity-datasource` (arbitrary REST/JSON panels)
- **grafana-mqtt-datasource v1.3.3 caveat:** panel target must be an
  exact scalar topic; wildcards silently drop. So Node-RED MUST publish
  `{{COUNT_TOPIC}}`, `{{COUNT_TOPIC}}/<sourceId>`, `stats/alert_active`,
  `stats/alert_total` as plain numbers (NOT JSON). Older versions broken
  — do NOT downgrade.
- `src/grafana/dashboards.yml` → `/var/lib/grafana/dashboards`; write
  `{{DASHBOARD_SLUG}}.json` there. Dashboard rows:
  1. Numeric MQTT panels: `{{COUNT_TOPIC}}`, `stats/alert_active`, `stats/alert_total`.
  2. Alert log (MQTT topic `{{ALERT_TOPIC}}`, JSON payload → table panel).
  3. {{NUM_SOURCES}} Text/HTML panels with `<img>` from `/frames/{{DETECTIONS_TOPIC_PREFIX}}_X.jpg`.
- Grafana `environment:` MUST include:
  ```yaml
  GF_INSTALL_PLUGINS: "grafana-mqtt-datasource 1.3.3,yesoreyeram-infinity-datasource 3.11.1"
  GF_SERVER_ROOT_URL: "https://localhost/grafana/"
  GF_SERVER_SERVE_FROM_SUB_PATH: "true"
  GF_PANELS_DISABLE_SANITIZE_HTML: "true"
  ```

## Mosquitto

`src/mosquitto/config/mosquitto.conf`:
```
allow_anonymous true
listener 1883
```
Only reachable on `app_network`; NOT published to the host.
