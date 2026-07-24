#!/usr/bin/env bash
# =============================================================================
# videostream-analytics 完整测试脚本
#
# 支持三种测试模式:
#   1. Unit Tests       — 纯 Python, 无需外部依赖 (除了测试视频文件)
#   2. Integration Tests — Docker 容器 + MediaMTX + RTSP 推流 + mock webhook
#   3. Multi-Video Tests — 逐个测试 4 个视频场景, 验证各 use case clip 产出
#
# 用法:
#   bash scripts/test-videostream-analytics.sh              # 运行全部测试
#   bash scripts/test-videostream-analytics.sh --unit-only  # 仅单元测试
#   bash scripts/test-videostream-analytics.sh --integration-only  # 仅集成测试
#   bash scripts/test-videostream-analytics.sh --multi-video       # 多视频场景测试
#   bash scripts/test-videostream-analytics.sh --local             # 本地 (无 Docker) 集成测试
#   bash scripts/test-videostream-analytics.sh -v           # 详细输出
#
# 环境变量:
#   HTTP_PROXY / HTTPS_PROXY  — Docker build 代理
#   MODEL_DIR                 — YOLO 模型目录 (默认 ~/models)
#   DATA_DIR                  — clip 输出目录 (默认 /tmp/smartbuilding-clips)
#   VIDEOS_DIR                — 测试视频根目录 (默认 <repo>/demo/videos)
#   MEDIAMTX_BIN              — MediaMTX 可执行文件 (默认 ~/.local/bin/mediamtx)
#   MEDIAMTX_CONFIG           — MediaMTX 配置 (默认 tools/mediamtx.yml)
#   DOCKER_IMAGE              — VSA 容器镜像名 (默认 videostream-analytics:latest)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="$(dirname "$PROJECT_DIR")"
PYTHON="${PROJECT_DIR}/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Virtual env not found at ${PROJECT_DIR}/.venv"
    echo "Run: cd $PROJECT_DIR && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

# --- Configuration ---
MEDIAMTX_BIN="${MEDIAMTX_BIN:-$HOME/.local/bin/mediamtx}"
MEDIAMTX_CONFIG="${MEDIAMTX_CONFIG:-${PROJECT_DIR}/tools/mediamtx.yml}"
DOCKER_IMAGE="${DOCKER_IMAGE:-videostream-analytics:latest}"
RTSP_PORT=8554
WEBHOOK_PORT=9999
ANALYTICS_PORT=8999
DATA_DIR="${DATA_DIR:-/tmp/smartbuilding-clips}"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"

# --- Test Videos ---
VIDEOS_DIR="${VIDEOS_DIR:-${REPO_DIR}/demo/videos}"
VIDEO_CHILD="${VIDEOS_DIR}/cam_child/child_safety_demo.mp4"
VIDEO_FRIDGE="${VIDEOS_DIR}/cam_fridge/demo006-2_expanded_20min_v2.mp4"
VIDEO_ELDER_DAY1="${VIDEOS_DIR}/cam_elder_bedroom/day1_elder_wakeup.mp4"
VIDEO_ELDER_DAY2="${VIDEOS_DIR}/cam_elder_bedroom_2/day2_elder_wakeup.mp4"

# --- Parse Arguments ---
RUN_UNIT=true
RUN_INTEGRATION=true
RUN_MULTIVIDEO=false
USE_LOCAL=false
VERBOSE=""
PYTEST_ARGS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --unit-only) RUN_INTEGRATION=false; RUN_MULTIVIDEO=false; shift ;;
        --integration-only) RUN_UNIT=false; shift ;;
        --multi-video) RUN_UNIT=false; RUN_INTEGRATION=false; RUN_MULTIVIDEO=true; shift ;;
        --local) USE_LOCAL=true; shift ;;
        -v|--verbose) VERBOSE="-v"; PYTEST_ARGS="-v"; shift ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[PASS]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
header(){ echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"; echo -e "  ${CYAN}$*${NC}"; echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"; }

# --- Cleanup function ---
PIDS_TO_KILL=()
CONTAINER_NAME=""
LOCAL_SERVER_PID=""

cleanup() {
    info "Cleaning up..."
    if [[ -n "$CONTAINER_NAME" ]]; then
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
    fi
    pkill -f "ffmpeg.*live/" 2>/dev/null || true
    if [[ -n "$LOCAL_SERVER_PID" ]]; then
        kill "$LOCAL_SERVER_PID" 2>/dev/null || true
        wait "$LOCAL_SERVER_PID" 2>/dev/null || true
    fi
    for pid in "${PIDS_TO_KILL[@]}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    if [[ "${MEDIAMTX_STARTED:-false}" == "true" ]]; then
        pkill -f "mediamtx" 2>/dev/null || true
    fi
    info "Cleanup complete."
}
trap cleanup EXIT

# --- Helper: ensure MediaMTX ---
ensure_mediamtx() {
    if lsof -i:$RTSP_PORT -t &>/dev/null; then
        info "MediaMTX already running on port $RTSP_PORT"
        MEDIAMTX_STARTED=false
    else
        info "Starting MediaMTX..."
        if [[ -f "$MEDIAMTX_CONFIG" ]]; then
            "$MEDIAMTX_BIN" "$MEDIAMTX_CONFIG" &>/dev/null &
        else
            "$MEDIAMTX_BIN" &>/dev/null &
        fi
        PIDS_TO_KILL+=($!)
        MEDIAMTX_STARTED=true
        sleep 2
        if ! lsof -i:$RTSP_PORT -t &>/dev/null; then
            fail "MediaMTX failed to start on port $RTSP_PORT"
            exit 1
        fi
        ok "MediaMTX started on :$RTSP_PORT"
    fi
}

# --- Helper: push RTSP stream ---
push_rtsp() {
    local video_path="$1"
    local rtsp_path="$2"
    local seek="${3:-0}"  # optional seek position in seconds

    pkill -f "ffmpeg.*${rtsp_path}" 2>/dev/null || true
    sleep 1

    local seek_args=""
    if [[ "$seek" -gt 0 ]]; then
        seek_args="-ss $seek"
    fi

    ffmpeg -re -stream_loop -1 $seek_args -i "$video_path" \
        -c copy -f rtsp \
        "rtsp://localhost:$RTSP_PORT/$rtsp_path" \
        </dev/null &>/dev/null &
    PIDS_TO_KILL+=($!)
    sleep 2
    ok "RTSP push: $(basename "$video_path") → rtsp://localhost:$RTSP_PORT/$rtsp_path"
}

# --- Helper: start mock webhook ---
start_mock_webhook() {
    if curl -sf "http://localhost:$WEBHOOK_PORT/health" >/dev/null 2>&1; then
        info "Mock webhook already running on :$WEBHOOK_PORT"
        return
    fi
    info "Starting mock webhook server on :$WEBHOOK_PORT..."
    $PYTHON -m uvicorn tests.integration.mock_webhook_server:app \
        --host 0.0.0.0 --port $WEBHOOK_PORT --log-level warning &
    PIDS_TO_KILL+=($!)
    sleep 2
    if curl -sf "http://localhost:$WEBHOOK_PORT/health" >/dev/null; then
        ok "Mock webhook server running on :$WEBHOOK_PORT"
    else
        fail "Mock webhook server failed to start"
        exit 1
    fi
}

# --- Helper: start analytics (Docker or Local) ---
start_analytics_docker() {
    CONTAINER_NAME="videostream-analytics-test-$$"
    info "Starting Docker container: $DOCKER_IMAGE"

    docker run -d --rm \
        --name "$CONTAINER_NAME" \
        --network host \
        -e WEBHOOK_URL="http://localhost:$WEBHOOK_PORT/events" \
        -e no_proxy="localhost,127.0.0.1" \
        -e http_proxy="" \
        -e https_proxy="" \
        -v "$MODEL_DIR:/models:ro" \
        -v "/tmp:/tmp" \
        -v "$DATA_DIR:/root/.mcp-smartbuilding/segments" \
        "$DOCKER_IMAGE"
    sleep 3
    wait_for_analytics
}

start_analytics_local() {
    info "Starting local videostream-analytics on :$ANALYTICS_PORT..."
    cd "$PROJECT_DIR"
    WEBHOOK_URL="http://localhost:$WEBHOOK_PORT/events" \
    $PYTHON __main__.py --host 0.0.0.0 --port $ANALYTICS_PORT --config config/config.yaml &
    LOCAL_SERVER_PID=$!
    PIDS_TO_KILL+=($LOCAL_SERVER_PID)
    sleep 3
    wait_for_analytics
}

wait_for_analytics() {
    local retries=15
    while [[ $retries -gt 0 ]]; do
        if curl -sf "http://localhost:$ANALYTICS_PORT/health" >/dev/null 2>&1; then
            ok "Analytics service healthy on :$ANALYTICS_PORT"
            return
        fi
        retries=$((retries - 1))
        sleep 1
    done
    fail "Analytics service failed to become healthy on :$ANALYTICS_PORT"
    if [[ -n "$CONTAINER_NAME" ]]; then
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
    fi
    exit 1
}

# --- Helper: register source and wait for events ---
test_video_scenario() {
    local source_id="$1"
    local rtsp_path="$2"
    local use_case="$3"
    local prefilter_enabled="${4:-true}"
    local wait_time="${5:-60}"

    info "Testing scenario: source_id=$source_id, use_case=$use_case, prefilter=$prefilter_enabled"

    # Clear previous events
    curl -sf -X DELETE "http://localhost:$WEBHOOK_PORT/recorded_events" >/dev/null

    # Register source
    local body
    if [[ "$prefilter_enabled" == "false" ]]; then
        body="{\"source_id\":\"$source_id\",\"rtsp_url\":\"rtsp://localhost:$RTSP_PORT/$rtsp_path\",\"use_case\":\"$use_case\",\"prefilter\":{\"enabled\":false}}"
    else
        body="{\"source_id\":\"$source_id\",\"rtsp_url\":\"rtsp://localhost:$RTSP_PORT/$rtsp_path\",\"use_case\":\"$use_case\"}"
    fi

    local resp
    resp=$(curl -sf -X POST "http://localhost:$ANALYTICS_PORT/register_source" \
        -H "Content-Type: application/json" -d "$body")
    local reg_status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

    if [[ "$reg_status" == "started" || "$reg_status" == "already_running" ]]; then
        ok "Source registered: $source_id ($reg_status)"
    else
        fail "Failed to register source $source_id: $resp"
        return 1
    fi

    # Wait for motion events
    info "Waiting ${wait_time}s for motion events..."
    local deadline=$((SECONDS + wait_time))
    local event_count=0
    while [[ $SECONDS -lt $deadline ]]; do
        event_count=$(curl -sf "http://localhost:$WEBHOOK_PORT/recorded_events/motion" | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
        if [[ "$event_count" -ge 1 ]]; then
            break
        fi
        sleep 3
    done

    # Check results
    if [[ "$event_count" -ge 1 ]]; then
        ok "$source_id: received $event_count motion event(s)"
    else
        fail "$source_id: no motion events received in ${wait_time}s"
        # Show status events for debugging
        info "Status events:"
        curl -sf "http://localhost:$WEBHOOK_PORT/recorded_events/status" | python3 -m json.tool 2>/dev/null || true
        return 1
    fi

    # Check clip files
    local clip_dir="$DATA_DIR/$source_id/motion_events"
    local clip_count=0
    if [[ -d "$clip_dir" ]]; then
        clip_count=$(find "$clip_dir" -name "*.mp4" | wc -l)
    fi
    if [[ "$clip_count" -ge 1 ]]; then
        ok "$source_id: $clip_count clip file(s) in $clip_dir"
    else
        warn "$source_id: no clip files found in $clip_dir (may be in container path)"
    fi

    # Stop source
    curl -sf -X POST "http://localhost:$ANALYTICS_PORT/sources/$source_id/stop" >/dev/null 2>&1 || true
    return 0
}

# =============================================================================
# UNIT TESTS
# =============================================================================
if $RUN_UNIT; then
    header "UNIT TESTS"
    cd "$PROJECT_DIR"

    if [[ ! -f "$VIDEO_CHILD" ]]; then
        fail "Test video not found: $VIDEO_CHILD"
        exit 1
    fi
    info "Test video: $VIDEO_CHILD"

    if ! $PYTHON -c "import pytest" 2>/dev/null; then
        info "Installing dev dependencies..."
        "${PROJECT_DIR}/.venv/bin/pip" install -e ".[dev]" --quiet --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>/dev/null
    fi

    info "Running unit tests (97 tests)..."
    $PYTHON -m pytest tests/unit/ $PYTEST_ARGS --tb=short -q --timeout=60
    UNIT_EXIT=$?

    if [[ $UNIT_EXIT -eq 0 ]]; then
        ok "Unit tests PASSED"
    else
        fail "Unit tests FAILED (exit code: $UNIT_EXIT)"
        exit $UNIT_EXIT
    fi
fi

# =============================================================================
# INTEGRATION TESTS (Docker + pytest)
# =============================================================================
if $RUN_INTEGRATION && ! $RUN_MULTIVIDEO; then
    header "INTEGRATION TESTS"
    cd "$PROJECT_DIR"

    # Check prerequisites
    if [[ ! -f "$VIDEO_CHILD" ]]; then
        fail "Test video not found: $VIDEO_CHILD"
        exit 1
    fi

    if $USE_LOCAL; then
        info "Mode: LOCAL (no Docker)"
    else
        if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
            info "Docker image not found, building..."
            docker build -t "$DOCKER_IMAGE" \
                --build-arg HTTP_PROXY="${HTTP_PROXY:-}" \
                --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
                -f docker/Dockerfile . 2>&1 | tail -5
        fi
    fi

    # Start infrastructure
    ensure_mediamtx
    push_rtsp "$VIDEO_CHILD" "live/child" 40
    start_mock_webhook

    if $USE_LOCAL; then
        start_analytics_local
    else
        start_analytics_docker
    fi

    # Run pytest integration suite
    info "Running integration tests..."
    $PYTHON -m pytest tests/integration/ $PYTEST_ARGS --tb=short -q -m integration --timeout=360
    INTEG_EXIT=$?

    if [[ $INTEG_EXIT -eq 0 ]]; then
        ok "Integration tests PASSED"
    else
        fail "Integration tests FAILED (exit code: $INTEG_EXIT)"
        if [[ -n "$CONTAINER_NAME" ]]; then
            info "Container logs (last 30 lines):"
            docker logs "$CONTAINER_NAME" 2>&1 | tail -30
        fi
        exit $INTEG_EXIT
    fi
fi

# =============================================================================
# MULTI-VIDEO SCENARIO TESTS
# =============================================================================
if $RUN_MULTIVIDEO; then
    header "MULTI-VIDEO SCENARIO TESTS"
    cd "$PROJECT_DIR"

    # Check videos exist
    MISSING=false
    for v in "$VIDEO_CHILD" "$VIDEO_FRIDGE" "$VIDEO_ELDER_DAY1" "$VIDEO_ELDER_DAY2"; do
        if [[ ! -f "$v" ]]; then
            fail "Video not found: $v"
            MISSING=true
        fi
    done
    if $MISSING; then exit 1; fi

    # Start infrastructure
    ensure_mediamtx
    start_mock_webhook

    if $USE_LOCAL; then
        start_analytics_local
    else
        if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
            info "Docker image not found, building..."
            docker build -t "$DOCKER_IMAGE" \
                --build-arg HTTP_PROXY="${HTTP_PROXY:-}" \
                --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
                -f docker/Dockerfile . 2>&1 | tail -5
        fi
        start_analytics_docker
    fi

    # Clean data dir (Docker writes as root → use container to clean)
    if [[ -d "$DATA_DIR" ]] && [[ -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
        if ! rm -rf "$DATA_DIR"/* 2>/dev/null; then
            info "Cleaning $DATA_DIR via container (need root for files written by container)"
            docker run --rm -v "$DATA_DIR":/data alpine sh -c 'rm -rf /data/*' 2>/dev/null || true
        fi
    fi
    RESULTS=()

    # --- Scenario 1: Child Safety ---
    echo ""
    info "━━━ Scenario 1/4: Child Safety (cam_child) ━━━"
    push_rtsp "$VIDEO_CHILD" "live/child" 40
    if test_video_scenario "cam_child" "live/child" "child_safety" "true" 60; then
        RESULTS+=("child_safety:PASS")
    else
        RESULTS+=("child_safety:FAIL")
    fi
    pkill -f "ffmpeg.*live/child" 2>/dev/null || true
    sleep 2

    # --- Scenario 2: Refrigerator ---
    echo ""
    info "━━━ Scenario 2/4: Refrigerator (cam_fridge) ━━━"
    push_rtsp "$VIDEO_FRIDGE" "live/fridge" 0
    if test_video_scenario "cam_fridge" "live/fridge" "fridge" "false" 60; then
        RESULTS+=("fridge:PASS")
    else
        RESULTS+=("fridge:FAIL")
    fi
    pkill -f "ffmpeg.*live/fridge" 2>/dev/null || true
    sleep 2

    # --- Scenario 3: Elder Wakeup Day1 ---
    echo ""
    info "━━━ Scenario 3/4: Elder Wakeup Day1 (cam_elder_bedroom) ━━━"
    push_rtsp "$VIDEO_ELDER_DAY1" "live/elder" 0
    if test_video_scenario "cam_elder_bedroom" "live/elder" "elder_wakeup" "true" 90; then
        RESULTS+=("elder_day1:PASS")
    else
        RESULTS+=("elder_day1:FAIL")
    fi
    pkill -f "ffmpeg.*live/elder" 2>/dev/null || true
    sleep 2

    # --- Scenario 4: Elder Wakeup Day2 ---
    echo ""
    info "━━━ Scenario 4/4: Elder Wakeup Day2 (cam_elder_bedroom_2) ━━━"
    push_rtsp "$VIDEO_ELDER_DAY2" "live/elder2" 0
    if test_video_scenario "cam_elder_bedroom_2" "live/elder2" "elder_wakeup" "true" 90; then
        RESULTS+=("elder_day2:PASS")
    else
        RESULTS+=("elder_day2:FAIL")
    fi

    # --- Summary ---
    echo ""
    header "MULTI-VIDEO RESULTS"
    PASS_COUNT=0
    FAIL_COUNT=0
    for r in "${RESULTS[@]}"; do
        scenario="${r%%:*}"
        status="${r##*:}"
        if [[ "$status" == "PASS" ]]; then
            ok "  $scenario"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            fail "  $scenario"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    done
    echo ""
    info "Results: $PASS_COUNT passed, $FAIL_COUNT failed out of ${#RESULTS[@]} scenarios"

    if [[ $FAIL_COUNT -gt 0 ]]; then
        exit 1
    fi
fi

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}ALL TESTS PASSED${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""
