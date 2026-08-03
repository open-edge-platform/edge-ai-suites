# Install + Compose reference

## `.env`

```
HOST_IP=<host-lan-ip>              # auto-detected by install.sh
SAMPLE_APP={{STACK_DIR}}
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24
VIDEO_GID=<gid of `video`>
RENDER_GID=<gid of `render`>
```

**Quote every value containing space/comma.** `sample_start.sh` does
`source .env`; `KEY=val with x` becomes `KEY=val` plus command `with`.

## `validate_env.sh` (step 0 of install.sh)

```sh
#!/bin/bash
set -e
err() { echo "ERROR: $*" >&2; exit 1; }
[ -f .env ] && . ./.env
[[ "$HOST_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || err "HOST_IP invalid: '$HOST_IP'"
[[ "$HOST_IP" != "0.0.0.0" && "$HOST_IP" != "127.0.0.1" ]] || err "HOST_IP must be LAN"
: "${NUM_SOURCES:=4}"; : "${MJPEG_FPS:=5}"
[[ "$NUM_SOURCES" =~ ^[0-9]+$ ]] && (( NUM_SOURCES>=1 && NUM_SOURCES<=16 )) || err "NUM_SOURCES 1..16 (got '$NUM_SOURCES')"
[[ "$MJPEG_FPS"   =~ ^[0-9]+$ ]] && (( MJPEG_FPS>=1   && MJPEG_FPS<=15   )) || err "MJPEG_FPS 1..15 (got '$MJPEG_FPS')"
DEV="${1:-cpu}"; DEV="${DEV,,}"
case "$DEV" in cpu|gpu|npu|auto) ;; *) err "DEVICE cpu|gpu|npu|auto (got '$1')";; esac
[[ "$VIDEO_GID"  =~ ^[0-9]+$ ]] || err "VIDEO_GID not numeric"
[[ "$RENDER_GID" =~ ^[0-9]+$ ]] || err "RENDER_GID not numeric"
ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq ':(80|443)$' && err "port 80/443 in use"
echo "validate_env: OK (device=$DEV, sources=$NUM_SOURCES, mjpeg_fps=$MJPEG_FPS)"
```

## `install.sh`

```sh
#!/bin/bash -e
HOST_IP="${1:-$(hostname -I | cut -f1 -d' ')}"

# 0. Preflight
./validate_env.sh "${2:-cpu}"

# 1. .env: HOST_IP + GIDs
touch .env
grep -q '^HOST_IP=' .env || echo "HOST_IP=$HOST_IP" >> .env
sed -i "s|^HOST_IP=.*|HOST_IP=$HOST_IP|" .env
VIDEO_GID=$(getent group video  | cut -d: -f3 || echo 44)
RENDER_GID=$(getent group render | cut -d: -f3 || echo 109)
grep -q '^VIDEO_GID='  .env || echo "VIDEO_GID=$VIDEO_GID"   >> .env
grep -q '^RENDER_GID=' .env || echo "RENDER_GID=$RENDER_GID" >> .env

# 2. Model dl + INT8 (+ optional classifier)
docker run --rm --user root -e http_proxy -e https_proxy -e no_proxy \
  -v "$PWD:/opt/project" intel/dlstreamer:2026.1.0-ubuntu24 bash -c '
    cd /opt/project
    export MODELS_PATH=/opt/project/src/dlstreamer-pipeline-server/models
    mkdir -p "$MODELS_PATH"/public
    if [ ! -f "$MODELS_PATH/public/{{PIPELINE_NAME}}/INT8/{{PIPELINE_NAME}}.xml" ]; then
      /home/dlstreamer/dlstreamer/samples/download_public_models.sh {{PIPELINE_NAME}} coco128
    fi
    if [ "{{CLASSIFIER}}" != "none" ] && [ ! -f "$MODELS_PATH/{{CLASSIFIER_XML}}" ]; then
      mkdir -p "$MODELS_PATH/{{CLASSIFIER}}"
      curl -L -o "$MODELS_PATH/{{CLASSIFIER_XML}}"           "{{CLASSIFIER_URL}}.xml"
      curl -L -o "$MODELS_PATH/{{CLASSIFIER_XML%.xml}}.bin"  "{{CLASSIFIER_URL}}.bin"
    fi
    chown -R '"$(id -u):$(id -g)"' "$MODELS_PATH"
  '

# 3. Sample videos
mkdir -p src/dlstreamer-pipeline-server/videos
VIDEO_URL="https://github.com/open-edge-platform/edge-ai-resources/raw/0d39322d6c6c578413cdf2a3d48c4e0978531e10/videos/smart_parking_720p_30fps.mp4"
for i in $(seq 1 {{NUM_SOURCES}}); do
  f=src/dlstreamer-pipeline-server/videos/new_video_$i.mp4
  [ -f "$f" ] || curl -L -o "$f" "$VIDEO_URL"
done

# 4. TLS cert with SAN
mkdir -p src/nginx/ssl
if [ ! -f src/nginx/ssl/server.crt ]; then
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout src/nginx/ssl/server.key -out src/nginx/ssl/server.crt \
    -subj "/CN=localhost" \
    -addext "subjectAltName=IP:127.0.0.1,IP:$HOST_IP,DNS:localhost"
fi
```

## `update_dashboard.sh` (optional)

MJPEG `<img>` URLs are relative (`/frames/…`) so they follow origin — no
HOST_IP rewrite needed. Provide for symmetry:
```sh
#!/bin/bash -e
HOST_IP="${1:?Usage: update_dashboard.sh <HOST_IP>}"
DASH=src/grafana/dashboards/{{DASHBOARD_SLUG}}.json
[ -f "$DASH" ] || { echo "Dashboard $DASH not found"; exit 1; }
sed -i "s|HOST_IP_PLACEHOLDER|$HOST_IP|g" "$DASH"
```

## `docker-compose.yml` — volumes

```yaml
volumes:
  dlstreamer-pipeline-server-pipeline-root:
    driver: local
    driver_opts: { type: tmpfs, device: tmpfs }
  frames:
    driver: local
    driver_opts: { type: tmpfs, device: tmpfs }
  node-red-node-modules: {}
```
DLSPS mounts `frames:/tmp/frames`; Nginx mounts
`frames:/usr/share/nginx/html/frames:ro`.

Services: `nginx`, `dlstreamer-pipeline-server`, `broker` (mosquitto),
`node-red`, `grafana`. No Prometheus, no OTel, no metrics-manager.
