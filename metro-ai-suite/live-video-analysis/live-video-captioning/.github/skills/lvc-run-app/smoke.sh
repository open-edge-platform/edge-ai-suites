#!/usr/bin/env bash
# Agent driver for Live Video Captioning.
# Launches the stack, feeds it a simulated RTSP stream, starts a captioning
# run, waits for real captions on MQTT, verifies the dashboard with curl, and
# cleans up. Every step is also usable on its own — run `./smoke.sh help`.
#
# All commands assume the compose stack of this project (container names
# video-caption-service, dlstreamer-pipeline-server, mqtt-broker, mediamtx).

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UI="http://localhost:${DASHBOARD_PORT:-4173}"
API="$UI/api"
RUN_ID="${LVC_RUN_ID:-lvc-smoke}"
SIM_VIDEO="/tmp/lvc-smoke.mp4"
SAMPLE_VIDEO_URL="https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/worker-zone-detection.mp4"
SIM_CONTAINER="mediamtx-server"   # same name scripts/setup_proxy_rtsp.sh uses
HOST_IP="$(ip route get 1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
HOST_IP="${HOST_IP:-127.0.0.1}"
RTSP_URL="rtsp://${HOST_IP}:8554/stream1"

# All API calls bypass any corporate proxy: the services are on localhost.
CURL=(curl -s --noproxy '*')

die() { echo "ERROR: $*" >&2; exit 1; }

cmd_up() {
    cd "$ROOT_DIR" || die "cannot cd to $ROOT_DIR"
    [ -f .env ] || bash scripts/setup_env.sh
    if [ ! -d ov_models ] || [ -z "$(ls -A ov_models 2>/dev/null)" ]; then
        die "ov_models/ is empty - download a model first, e.g.
  ./model_download_scripts/download_models.sh --model OpenGVLab/InternVL2-1B --type vlm --weight-format int8"
    fi
    docker compose up -d 2>&1 | grep -v 'variable is not set' || true
    echo "waiting for video-caption-service health..."
    for _ in $(seq 1 30); do
        "${CURL[@]}" "$API/health" | grep -q healthy && { echo "healthy"; return 0; }
        sleep 5
    done
    die "service did not become healthy; check: docker logs video-caption-service"
}

cmd_status() {
    docker ps --format '{{.Names}}\t{{.Status}}' \
        | grep -E 'video-caption|dlstreamer|mqtt|mediamtx|metrics|coturn' || true
    echo "health:    $("${CURL[@]}" "$API/health")"
    echo "models:    $("${CURL[@]}" "$API/vlm-models")"
    echo "runs:      $("${CURL[@]}" "$API/generate_captions_alerts")"
}

cmd_start_sim() {
    local video="${1:-}"
    if [ ! -f "$SIM_VIDEO" ]; then
        if [ -n "$video" ] && [ -f "$video" ]; then
            cp "$video" "$SIM_VIDEO"
        else
            # No local sample given: fetch the Intel sample video. Plain curl
            # (not $CURL) so the corporate proxy from the environment applies.
            echo "downloading sample video: $SAMPLE_VIDEO_URL"
            curl -fsSL -o "$SIM_VIDEO" "$SAMPLE_VIDEO_URL" \
                || { rm -f "$SIM_VIDEO"; die "sample download failed; stage one manually: ./smoke.sh start-sim /path/to/video.mp4"; }
        fi
    fi
    # Standalone mediamtx with RTSP enabled (the stack's own mediamtx has MTX_RTSP=no).
    docker ps --format '{{.Names}}' | grep -qx "$SIM_CONTAINER" || {
        docker rm -f "$SIM_CONTAINER" >/dev/null 2>&1
        docker run -d --name "$SIM_CONTAINER" -p 8554:8554 bluenviron/mediamtx:1.11.3 >/dev/null || die "mediamtx start failed"
        sleep 2
    }
    # Host ffmpeg may be broken (libva mismatch); the dlstreamer container ships
    # a working ffmpeg and mounts /tmp, so publish from inside it.
    docker exec dlstreamer-pipeline-server pgrep -f "ffmpeg.*$SIM_VIDEO" >/dev/null 2>&1 || {
        docker exec -d dlstreamer-pipeline-server ffmpeg -re -stream_loop -1 -i "$SIM_VIDEO" \
            -c:v libx264 -preset ultrafast -tune zerolatency -profile:v baseline -an \
            -r 30 -g 60 -rtsp_transport tcp -f rtsp "rtsp://host.docker.internal:8554/stream1" \
            || die "ffmpeg publish failed"
        sleep 3
    }
    if docker logs "$SIM_CONTAINER" 2>&1 | grep -q "publishing to path 'stream1'"; then
        echo "simulator publishing: $RTSP_URL"
    else
        die "publisher did not register; check: docker logs $SIM_CONTAINER"
    fi
}

cmd_start_run() {
    # GPU pipeline is the product default, but errors with 'no element
    # "vah264dec"' when VA-API is unavailable in the container - CPU always works.
    local pipeline="${1:-GenAI_Pipeline_on_CPU}"
    local rtsp="${2:-$RTSP_URL}"
    local model
    model=$("${CURL[@]}" "$API/vlm-models" | python3 -c 'import sys,json;print(json.load(sys.stdin)["models"][0])') \
        || die "no VLM models available"
    "${CURL[@]}" -X POST "$API/generate_captions_alerts" -H 'Content-Type: application/json' \
        -d "{\"rtspUrl\":\"$rtsp\",\"modelName\":\"$model\",\"runName\":\"$RUN_ID\",\"pipelineName\":\"$pipeline\"}" \
        | python3 -m json.tool
    sleep 3
    local ready
    ready=$("${CURL[@]}" "$API/generate_captions_alerts/$RUN_ID/stream-ready")
    echo "stream-ready: $ready"
    echo "$ready" | grep -q '"error":true' \
        && die "pipeline went to error state; check: docker logs dlstreamer-pipeline-server | tail -30"
    return 0
}

cmd_wait_captions() {
    # First caption on CPU takes ~5-6 min (model load + first inference);
    # afterwards one arrives every ~20 s.
    local timeout="${1:-420}"
    echo "waiting up to ${timeout}s for a caption on MQTT topic live-video-captioning/#..."
    local msg
    msg=$(docker exec mqtt-broker timeout "$timeout" \
        mosquitto_sub -t 'live-video-captioning/#' -v -C 1 2>/dev/null)
    [ -n "$msg" ] || die "no caption within ${timeout}s"
    echo "$msg" | head -c 400; echo
    echo "$msg" | grep -o '"result": "[^"]*"' | head -1
}

cmd_check_ui() {
    # Curl-only dashboard verification, no browser: the served page, its
    # assets, and the SSE stream the dashboard renders captions from.
    # Caption events carry a "runId" envelope; heartbeats are "type":"status".
    local watch="${1:-25}"
    "${CURL[@]}" -m 10 "$UI/" | grep -q 'Live Video Captioning' \
        || die "dashboard HTML missing app title"
    local asset code
    for asset in /js/app.js /css/styles.css; do
        code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$UI$asset")
        [ "$code" = 200 ] || die "asset $asset returned HTTP $code"
    done
    echo "dashboard HTML + assets OK; watching SSE for ${watch}s..."
    local events
    events=$("${CURL[@]}" -N -m "$watch" "$API/generate_captions_alerts/metadata-stream" | grep '^data:')
    [ -n "$events" ] || die "no SSE events from metadata-stream in ${watch}s"
    if echo "$events" | grep -q '"runId"'; then
        echo "caption event reached UI stream:"
        echo "$events" | grep '"runId"' | head -1 | head -c 400; echo
    else
        echo "SSE heartbeats only (no caption event in ${watch}s window):"
        echo "$events" | head -1
    fi
}

cmd_stop_run() {
    "${CURL[@]}" -X DELETE "$API/generate_captions_alerts/$RUN_ID"; echo
}

cmd_stop_sim() {
    docker exec dlstreamer-pipeline-server pkill -f "ffmpeg.*$SIM_VIDEO" 2>/dev/null
    docker rm -f "$SIM_CONTAINER" >/dev/null 2>&1
    echo "simulator stopped"
}

cmd_all() {
    cmd_up
    cmd_start_sim "$@"
    cmd_start_run
    cmd_wait_captions 420
    cmd_check_ui
    cmd_stop_run
    cmd_stop_sim
    echo "SMOKE PASSED"
}

case "${1:-help}" in
    up)            cmd_up ;;
    status)        cmd_status ;;
    start-sim)     shift; cmd_start_sim "$@" ;;
    start-run)     shift; cmd_start_run "$@" ;;
    wait-captions) shift; cmd_wait_captions "$@" ;;
    check-ui)      shift; cmd_check_ui "$@" ;;
    stop-run)      cmd_stop_run ;;
    stop-sim)      cmd_stop_sim ;;
    all)           shift; cmd_all "$@" ;;
    *) cat <<EOF
Usage: smoke.sh <command>
  up                       setup .env if missing, docker compose up -d, wait healthy
  status                   container + API status, active runs
  start-sim [video.mp4]    looped RTSP simulator at $RTSP_URL (downloads Intel sample if no file given)
  start-run [pipeline] [rtsp_url]   POST a captioning run (default: CPU pipeline, simulator URL)
  wait-captions [secs]     block until a caption arrives on MQTT (default 420s)
  check-ui [secs]          curl-only dashboard check: HTML, assets, SSE caption events (default 25s)
  stop-run                 DELETE the smoke run
  stop-sim                 stop simulator + ffmpeg publisher
  all [video.mp4]          full end-to-end smoke, then clean up
EOF
    ;;
esac
