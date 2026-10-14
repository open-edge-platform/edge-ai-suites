#!/bin/bash

docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$(dirname "$(readlink -f "$0")"):/opt/project" \
  intel/dlstreamer:2026.2.0-ubuntu24 bash -c "$(cat <<EOF

cd /opt/project
export HOST_IP="${1:-$(hostname -I | cut -f1 -d' ')}"
echo "Configuring application to use \$HOST_IP"

# shellcheck disable=SC1091
. ./update_dashboard.sh \$HOST_IP

##############################################################################
# Download OMZ models
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/models/intel
OMZ_MODELS=(pedestrian-and-vehicle-detector-adas-0001)
for model in "\${OMZ_MODELS[@]}"; do
  if [ ! -e "src/dlstreamer-pipeline-server/models/intel/\$model/\$model.json" ]; then
    echo "Download \$model..." && \
    mkdir -p src/dlstreamer-pipeline-server/models/intel/\${model}/FP16/ && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/FP16/\${model}.xml" "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/\${model}/FP16/\${model}.xml?raw=true" && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/FP16/\${model}.bin" "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/\${model}/FP16/\${model}.bin?raw=true" && \
    echo "Download \$model proc file..." && \
    curl -L -o "src/dlstreamer-pipeline-server/models/intel/\${model}/\${model}.json" "https://github.com/dlstreamer/dlstreamer/blob/master/samples/gstreamer/model_proc/intel/\${model}.json?raw=true"

  fi
done

##############################################################################
# Download and setup videos
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/videos
declare -A video_urls=(
    ["VIRAT_S_000101.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000101.mp4"
    ["VIRAT_S_000102.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000102.mp4"
    ["VIRAT_S_000103.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000103.mp4"
    ["VIRAT_S_000104.mp4"]="https://github.com/open-edge-platform/edge-ai-resources/raw/0e0a8e62c1f397412528fb63391632c6b903650b/videos/VIRAT_S_000104.mp4"
)
for video_name in "\${!video_urls[@]}"; do
    if [ ! -f src/dlstreamer-pipeline-server/videos/\${video_name} ]; then
        echo "Download \${video_name}..."
        curl -L -o "src/dlstreamer-pipeline-server/videos/\${video_name}" "\${video_urls[\$video_name]}"
    fi
done

echo "Fix ownership..."
chown -R "$(id -u):$(id -g)" src/dlstreamer-pipeline-server/models src/dlstreamer-pipeline-server/videos 2>/dev/null || true


mkdir -p src/nginx/ssl
cd src/nginx/ssl
if [ ! -f server.key ] || [ ! -f server.crt ]; then
    echo "Generate self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
    chown -R "$(id -u):$(id -g)" server.key server.crt 2>/dev/null || true

fi

EOF

)"

##############################################################################
# This app no longer uses Node-RED (zone/dwell logic now runs in gvaanalytics).
# Strip the node-red service from the generated docker-compose.yml (one level
# up, shared with sibling apps) rather than editing the shared compose source,
# so smart-parking/smart-intersection are unaffected.
##############################################################################
if [ -f ../docker-compose.yml ]; then
  awk '
    /^  node-red:/ { skip=1; next }
    skip && /^  [^ ]/ { skip=0 }
    skip && /^[^ ]/ { skip=0 }
    !skip { print }
  ' ../docker-compose.yml > ../docker-compose.yml.tmp && mv ../docker-compose.yml.tmp ../docker-compose.yml
  sed -i '/^      - node-red$/d' ../docker-compose.yml
  sed -i '/^  node-red-node-modules:$/d' ../docker-compose.yml
fi

##############################################################################
# This app's MQTT topic prefixes are not part of the shared .env (they're
# loitering-detection-specific); set them here, idempotently, in a clearly
# commented section rather than leaving them permanently defined for
# sibling apps that don't use them.
##############################################################################
if [ -f ../.env ]; then
  sed -i \
    -e '/^# loitering-detection: MQTT topic prefixes/d' \
    -e '/^# SOURCE_TOPIC_PREFIX -/d' \
    -e '/^#   publishes to/d' \
    -e '/^# DEST_TOPIC_PREFIX -/d' \
    -e '/^#   to for the Grafana/d' \
    -e '/^SOURCE_TOPIC_PREFIX=/d' \
    -e '/^DEST_TOPIC_PREFIX=/d' \
    ../.env
  cat >> ../.env <<'EOF'

# loitering-detection: MQTT topic prefixes used by the mqtt-table-flattener sidecar.
# SOURCE_TOPIC_PREFIX - prefix of the raw per-frame metadata topic gvametaconvert
#   publishes to (<prefix>/<stream-id>); must match sample_start.sh's launch topics.
# DEST_TOPIC_PREFIX - prefix the flattener republishes one-row-per-object summaries
#   to for the Grafana MQTT table panel (<prefix>/<stream-id>).
SOURCE_TOPIC_PREFIX=object_tracking
DEST_TOPIC_PREFIX=loiter_status
EOF
fi

##############################################################################
# Add the mqtt-table-flattener service: reshapes the raw object_tracking/<N>
# metadata (published as-is by DLSPS/gvametaconvert, unmodified) into
# loiter_status/<N> messages Grafana's MQTT table panel can render as rows
# (one MQTT message = one table row). Reuses the dlstreamer-pipeline-server
# image (already pulled, already has paho-mqtt) instead of adding a new one.
# Loitering-detection-specific, so this is inserted only into the generated
# compose file (before the top-level "networks:" key, since "services:" is
# not the last section), not the shared template.
##############################################################################
if [ -f ../docker-compose.yml ] && ! grep -q '^  mqtt-table-flattener:' ../docker-compose.yml; then
  awk '
    /^networks:/ && !inserted {
      print "  mqtt-table-flattener:"
      print "    image: ${DLSTREAMER_PIPELINE_SERVER_IMAGE}"
      print "    container_name: mqtt-table-flattener"
      print "    environment:"
      print "      - MQTT_HOST=broker"
      print "      - MQTT_PORT=1883"
      print "      - SOURCE_TOPIC_PREFIX=${SOURCE_TOPIC_PREFIX}"
      print "      - DEST_TOPIC_PREFIX=${DEST_TOPIC_PREFIX}"
      print "    volumes:"
      print "      - \"./${SAMPLE_APP}/src/mqtt-table-flattener:/app:ro\""
      print "    entrypoint: [\"python3\", \"/app/flatten.py\"]"
      print "    depends_on:"
      print "      - broker"
      print "    networks:"
      print "      - app_network"
      print "    restart: on-failure:5"
      print ""
      inserted=1
    }
    { print }
  ' ../docker-compose.yml > ../docker-compose.yml.tmp && mv ../docker-compose.yml.tmp ../docker-compose.yml
fi

##############################################################################
# Console UI service: operator UI to start/stop streams, draw a zone and view
# live loitering analytics. Only for the "loitering-detection-ui" install
# variant (ENABLE_UI=true, set by the top-level install.sh) - this is inserted
# into the generated compose file only, same as mqtt-table-flattener,
# so a plain "loitering-detection" install never see this service at all.
# Reuses the dlstreamer-pipeline-server image (already pulled, already has
# Flask, requests and paho-mqtt instead of building one.
##############################################################################
if [ "${ENABLE_UI:-false}" = "true" ] && [ -f ../docker-compose.yml ] && ! grep -q '^  console:' ../docker-compose.yml; then
  awk '
    /^networks:/ && !inserted {
      print "  console:"
      print "    image: ${DLSTREAMER_PIPELINE_SERVER_IMAGE}"
      print "    container_name: ui-console"
      print "    restart: unless-stopped"
      print "    env_file:"
      print "      - ./console-addon/.env"
      print "    environment:"
      print "      - UI_PORT=8091"
      print "      - HOST_IP=${HOST_IP}"
      print "      - PIPELINE_SERVER_URL=http://dlstreamer-pipeline-server:8080"
      print "      - MQTT_HOST=broker"
      print "      - MQTT_PORT=1883"
      print "      - MEDIAMTX_URL=http://mediamtx-server:8889"
      print "      - PROMETHEUS_URL=http://prometheus:9090/prometheus"
      print "      - MODEL_ROOT=/home/pipeline-server/models"
      print "      - http_proxy=${http_proxy}"
      print "      - https_proxy=${https_proxy}"
      print "      - HTTP_PROXY=${http_proxy}"
      print "      - HTTPS_PROXY=${https_proxy}"
      print "      - no_proxy=${HOST_IP},dlstreamer-pipeline-server,mediamtx-server,prometheus,${no_proxy}"
      print "      - NO_PROXY=${HOST_IP},dlstreamer-pipeline-server,mediamtx-server,prometheus,${no_proxy}"
      print "    volumes:"
      print "      - ./console-addon/console:/app:ro"
      print "      - \"./${SAMPLE_APP}/src/dlstreamer-pipeline-server/models:/home/pipeline-server/models:ro\""
      print "      - \"./${SAMPLE_APP}/src/dlstreamer-pipeline-server/zones:/home/pipeline-server/zones:ro\""
      print "      - \"/dev:/dev:ro\""
      print "    working_dir: /app"
      print "    entrypoint: [\"/bin/sh\", \"./entrypoint.sh\"]"
      print "    healthcheck:"
      print "      test: [\"CMD\", \"python3\", \"-c\", \"import urllib.request; urllib.request.urlopen('"'"'http://localhost:8091/'"'"')\"]"
      print "      interval: 10s"
      print "      timeout: 5s"
      print "      retries: 3"
      print "      start_period: 10s"
      print "    networks:"
      print "      - app_network"
      print "    depends_on:"
      print "      - dlstreamer-pipeline-server"
      print "      - broker"
      print ""
      inserted=1
    }
    { print }
  ' ../docker-compose.yml > ../docker-compose.yml.tmp && mv ../docker-compose.yml.tmp ../docker-compose.yml
fi

##############################################################################
# Add (or remove) the Console UI's link on nginx's default landing page -
# only present when the service itself was just added above, so the link
# is never shown (and never 404/502s) for a plain "loitering-detection"
# install. Patches src/nginx/nginx.conf directly (bind-mounted as-is, not
# copied/generated like docker-compose.yml), idempotently in both
# directions - switching between install variants does not leave it stale.
##############################################################################
NGINX_CONF="src/nginx/nginx.conf"
if [ -f "$NGINX_CONF" ]; then
  if [ "${ENABLE_UI:-false}" = "true" ] && ! grep -q '<h3><a href="/console/">' "$NGINX_CONF"; then
    awk '
      /<h3><a href="\/grafana\/">/ && !inserted {
        print "    <div class=\"service\">"
        print "        <h3><a href=\"/console/\">UI Console</a></h3>"
        print "        <p>Start/stop streams, draw a zone, and view live loitering analytics</p>"
        print "    </div>"
        inserted=1
      }
      { print }
    ' "$NGINX_CONF" > "$NGINX_CONF.tmp" && mv "$NGINX_CONF.tmp" "$NGINX_CONF"
  elif [ "${ENABLE_UI:-false}" != "true" ] && grep -q '<h3><a href="/console/">' "$NGINX_CONF"; then
    awk '
      /<div class="service">/ { buf = $0; next }
      buf && /<h3><a href="\/console\/">/ { buf = ""; skip = 1; next }
      skip && /<\/div>/ { skip = 0; next }
      buf { print buf; buf = "" }
      !skip { print }
    ' "$NGINX_CONF" > "$NGINX_CONF.tmp" && mv "$NGINX_CONF.tmp" "$NGINX_CONF"
  fi
fi

