#!/usr/bin/env bash
# =============================================================================
# run_eval.sh — End-to-end prefilter evaluation across all phase-2 scenarios.
#
# Background
#   Design doc lists 3 use cases: child_safety, elder_wakeup, refrigerator_monitor
#   (smartbuilding-video-design-2026.2.md §1).
#   In test-videostream-analytics.sh these expand to 4 scenarios because
#   elder_wakeup has 2 input videos (day1 punctual + day2 late). fridge has no
#   ground-truth SRT for the demo video and runs prefilter=disabled, so its
#   "evaluation" is a smoke test only (motion events arrive → PASS).
#
# Scenarios (matching scripts/test-videostream-analytics.sh)
#   child       cam_child            child_safety_demo.mp4              ss=40 prefilter=on  GT yes
#   fridge      cam_fridge           demo006-2_expanded_20min_v2.mp4    ss=0  prefilter=off GT yes (1200s, 4 [TAKE] cues)
#   elder_day1  cam_elder_bedroom    day1_elder_wakeup.mp4              ss=0  prefilter=on  GT yes (excl [EMPTY])
#   elder_day2  cam_elder_bedroom_2  day2_elder_wakeup.mp4              ss=0  prefilter=on  GT yes (excl [EMPTY])
#
# Usage
#   bash tools/run_eval.sh                       # all 4 scenarios sequentially
#   bash tools/run_eval.sh --scenario child      # one scenario
#   bash tools/run_eval.sh --scenario elder_day1
#   bash tools/run_eval.sh --wait-mode short     # use shorter waits for smoke test
#   bash tools/run_eval.sh --keep                # leave services running
#
# Env overrides
#   VIDEOS_DIR  — root of the phase-2 video corpus.
#                 Default: <repo>/demo/videos (the MP4 binaries are .gitignore'd;
#                 GT SRT files live alongside and stay tracked).
#   MEDIAMTX_CONFIG — defaults to tools/mediamtx.yml in this repo.
#   MEDIAMTX_BIN, RTSP_PORT, WEBHOOK_PORT, ANALYTICS_PORT — see code below.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="$(dirname "$PROJECT_DIR")"
PYTHON="${PROJECT_DIR}/.venv/bin/python"

VIDEOS_DIR="${VIDEOS_DIR:-$REPO_DIR/demo/videos}"

MEDIAMTX_BIN="${MEDIAMTX_BIN:-$HOME/.local/bin/mediamtx}"
MEDIAMTX_CONFIG="${MEDIAMTX_CONFIG:-$SCRIPT_DIR/mediamtx.yml}"
RTSP_PORT="${RTSP_PORT:-8554}"
WEBHOOK_PORT="${WEBHOOK_PORT:-9999}"
ANALYTICS_PORT="${ANALYTICS_PORT:-8999}"

VIDEO_CHILD="$VIDEOS_DIR/cam_child/child_safety_demo.mp4"
GT_CHILD="$VIDEOS_DIR/cam_child/child_safety_demo_groundtruth.srt"

VIDEO_FRIDGE="$VIDEOS_DIR/cam_fridge/demo006-2_expanded_20min_v2.mp4"
GT_FRIDGE="$VIDEOS_DIR/cam_fridge/demo006-2_expanded_20min_v2_groundtruth.srt"

VIDEO_ELDER_DAY1="$VIDEOS_DIR/cam_elder_bedroom/day1_elder_wakeup.mp4"
GT_ELDER_DAY1="$VIDEOS_DIR/cam_elder_bedroom/day1_elder_wakeup_groundtruth.srt"

VIDEO_ELDER_DAY2="$VIDEOS_DIR/cam_elder_bedroom_2/day2_elder_wakeup.mp4"
GT_ELDER_DAY2="$VIDEOS_DIR/cam_elder_bedroom_2/day2_elder_wakeup_groundtruth.srt"

SCENARIOS=("child" "fridge" "elder_day1" "elder_day2")
WAIT_MODE="full"
KEEP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scenario)
            case "$2" in
                child|fridge|elder_day1|elder_day2|all) ;;
                *) echo "Unknown scenario: $2 (valid: child|fridge|elder_day1|elder_day2|all)"; exit 1 ;;
            esac
            if [[ "$2" != "all" ]]; then SCENARIOS=("$2"); fi
            shift 2 ;;
        --wait-mode)
            case "$2" in full|short) WAIT_MODE="$2"; shift 2 ;;
                *) echo "wait-mode must be full|short"; exit 1 ;;
            esac ;;
        --keep) KEEP=true; shift ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
hdr()   { echo -e "\n${BOLD}${CYAN}══ $* ══${NC}\n"; }

# --- Cleanup ---
MEDIAMTX_PID=""; MOCK_PID=""; ANALYTICS_PID=""; FFMPEG_PID=""
MEDIAMTX_OWNED=false
ACTIVE_SOURCES=()

cleanup() {
    if $KEEP; then
        warn "--keep set; leaving services running. PIDs:"
        warn "  mock=$MOCK_PID analytics=$ANALYTICS_PID ffmpeg=$FFMPEG_PID"
        $MEDIAMTX_OWNED && warn "  mediamtx=$MEDIAMTX_PID"
        return
    fi
    info "Cleaning up..."
    [[ -n "$FFMPEG_PID" ]] && kill "$FFMPEG_PID" 2>/dev/null || true
    pkill -f "ffmpeg.*live/" 2>/dev/null || true
    # Stop any source we registered (best effort)
    for sid in "${ACTIVE_SOURCES[@]}"; do
        curl -sf -X POST "http://localhost:$ANALYTICS_PORT/sources/$sid/stop" >/dev/null 2>&1 || true
    done
    [[ -n "$ANALYTICS_PID" ]] && kill "$ANALYTICS_PID" 2>/dev/null || true
    [[ -n "$MOCK_PID" ]] && kill "$MOCK_PID" 2>/dev/null || true
    if $MEDIAMTX_OWNED && [[ -n "$MEDIAMTX_PID" ]]; then
        kill "$MEDIAMTX_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    info "Cleanup done."
}
trap cleanup EXIT INT TERM

# --- Pre-flight ---
[[ -x "$PYTHON" ]] || { fail "venv not found at $PYTHON"; exit 1; }
[[ -x "$MEDIAMTX_BIN" ]] || { fail "mediamtx not found at $MEDIAMTX_BIN"; exit 1; }
command -v ffmpeg >/dev/null || { fail "ffmpeg not in PATH"; exit 1; }

for port in "$WEBHOOK_PORT" "$ANALYTICS_PORT"; do
    if lsof -i:"$port" -sTCP:LISTEN -t &>/dev/null; then
        fail "Port $port already in use. Run: kill \$(lsof -i:$port -sTCP:LISTEN -t)"
        exit 1
    fi
done

# --- Boot shared infra (mediamtx + mock webhook + analytics) once ---
hdr "Booting shared infrastructure"

if lsof -i:"$RTSP_PORT" -sTCP:LISTEN -t &>/dev/null; then
    info "MediaMTX already on :$RTSP_PORT (reusing)"
    MEDIAMTX_OWNED=false
else
    info "Starting MediaMTX..."
    "$MEDIAMTX_BIN" "$MEDIAMTX_CONFIG" &>/dev/null &
    MEDIAMTX_PID=$!
    MEDIAMTX_OWNED=true
    sleep 2
    lsof -i:"$RTSP_PORT" -sTCP:LISTEN -t &>/dev/null || { fail "MediaMTX failed"; exit 1; }
    ok "MediaMTX up on :$RTSP_PORT (pid $MEDIAMTX_PID)"
fi

info "Starting mock webhook on :$WEBHOOK_PORT..."
cd "$PROJECT_DIR"
$PYTHON -m uvicorn tests.integration.mock_webhook_server:app \
    --host 0.0.0.0 --port "$WEBHOOK_PORT" --log-level warning &
MOCK_PID=$!
sleep 2
curl -sf "http://localhost:$WEBHOOK_PORT/health" >/dev/null \
    || { fail "mock webhook failed"; exit 1; }
ok "Mock webhook up (pid $MOCK_PID)"

info "Starting analytics on :$ANALYTICS_PORT..."
WEBHOOK_URL="http://localhost:$WEBHOOK_PORT/events" \
    $PYTHON __main__.py --host 0.0.0.0 --port "$ANALYTICS_PORT" --config config/config.yaml &
ANALYTICS_PID=$!
for _ in {1..15}; do
    curl -sf "http://localhost:$ANALYTICS_PORT/health" >/dev/null 2>&1 && break
    sleep 1
done
curl -sf "http://localhost:$ANALYTICS_PORT/health" >/dev/null \
    || { fail "Analytics did not become healthy"; exit 1; }
ok "Analytics up (pid $ANALYTICS_PID)"

# --- Helpers ---
push_rtsp() {
    local video="$1" path="$2" ss="$3"
    pkill -f "ffmpeg.*${path}" 2>/dev/null || true
    sleep 1
    ffmpeg -re -stream_loop -1 -ss "$ss" -i "$video" \
        -c copy -f rtsp "rtsp://localhost:$RTSP_PORT/$path" \
        </dev/null &>/dev/null &
    FFMPEG_PID=$!
    sleep 3
}

register_source() {
    local sid="$1" path="$2" use_case="$3" prefilter_enabled="$4"
    local body
    if [[ "$prefilter_enabled" == "false" ]]; then
        body="{\"source_id\":\"$sid\",\"source_url\":\"rtsp://localhost:$RTSP_PORT/$path\",\"pipeline\":{\"prefilter\":{\"enabled\":false}}}"
    else
        body="{\"source_id\":\"$sid\",\"source_url\":\"rtsp://localhost:$RTSP_PORT/$path\"}"
    fi
    curl -sf -X POST "http://localhost:$ANALYTICS_PORT/register_source" \
        -H 'Content-Type: application/json' -d "$body" || return 1
    echo
    ACTIVE_SOURCES+=("$sid")
}

stop_source() {
    local sid="$1" path="$2"
    pkill -f "ffmpeg.*${path}" 2>/dev/null || true
    curl -sf -X POST "http://localhost:$ANALYTICS_PORT/sources/$sid/stop" >/dev/null 2>&1 || true
    sleep 2
    # Drop from ACTIVE_SOURCES so cleanup() doesn't double-stop and 404.
    local new=()
    for s in "${ACTIVE_SOURCES[@]}"; do
        [[ "$s" != "$sid" ]] && new+=("$s")
    done
    ACTIVE_SOURCES=("${new[@]}")
}

clear_webhook_events() {
    curl -sf -X DELETE "http://localhost:$WEBHOOK_PORT/recorded_events" >/dev/null
}

run_scenario() {
    local name="$1" sid="$2" path="$3" video="$4" ss="$5" use_case="$6"
    local prefilter="$7" wait_full="$8" wait_short="$9" gt="${10}" excl="${11}"
    local wait_s
    [[ "$WAIT_MODE" == "short" ]] && wait_s="$wait_short" || wait_s="$wait_full"

    hdr "Scenario: $name (use_case=$use_case, prefilter=$prefilter)"

    [[ -f "$video" ]] || { fail "video missing: $video"; return 1; }

    clear_webhook_events
    push_rtsp "$video" "$path" "$ss"
    ok "RTSP push started (ss=$ss)"

    register_source "$sid" "$path" "$use_case" "$prefilter"
    ok "Source registered: $sid"

    info "Waiting ${wait_s}s for video playback..."
    sleep "$wait_s"

    info "Snapshotting events + status..."
    local evt_dump="/tmp/${name}_events_$$.json"
    local stat_dump="/tmp/${name}_status_$$.json"
    curl -sf "http://localhost:$WEBHOOK_PORT/recorded_events" > "$evt_dump"
    curl -sf "http://localhost:$ANALYTICS_PORT/sources/$sid" > "$stat_dump" || true
    local evt_count
    evt_count=$($PYTHON -c "import json; print(json.load(open('$evt_dump')).get('count',0))" 2>/dev/null || echo 0)
    ok "Dumped $evt_count events → $evt_dump"
    ok "Dumped status → $stat_dump"

    if [[ -z "$gt" ]]; then
        # No GT — smoke test only (events arrived)
        local motion_count
        motion_count=$($PYTHON -c "import json; d=json.load(open('$evt_dump')); print(sum(1 for e in d.get('events',[]) if e.get('event_type')=='motion'))" 2>/dev/null || echo 0)
        if [[ "$motion_count" -ge 1 ]]; then
            ok "Smoke: $motion_count motion event(s) — PASS"
        else
            fail "Smoke: 0 motion events — FAIL"
        fi
    else
        [[ -f "$gt" ]] || { fail "GT SRT missing: $gt"; return 1; }
        echo
        info "Running prefilter evaluation..."
        echo
        local args=(
            --srt "$gt"
            --source-id "$sid"
            --analytics-url "http://localhost:$ANALYTICS_PORT"
            --ss "$ss"
        )
        [[ -n "$excl" ]] && args+=(--exclude-label-pattern "$excl")
        $PYTHON tools/eval_prefilter_from_webhook.py "${args[@]}"
    fi

    stop_source "$sid" "$path"
    FFMPEG_PID=""
    echo
}

# --- Run selected scenarios ---
for scen in "${SCENARIOS[@]}"; do
    case "$scen" in
        child)
            #              name    sid        path       video         ss  use_case      pref  full short gt           excl
            run_scenario   child   cam_child  live/child "$VIDEO_CHILD" 40 child_safety  true  540  120   "$GT_CHILD"  ""
            ;;
        fridge)
            # Fridge GT cues are [TAKE] hand-grab events (2.5-4s each over a 20-min video).
            # prefilter=off because target_classes=person would filter out hand-only motion.
            # Last cue is at 15:12, so wait ~16 min to cover all cues with margin.
            run_scenario   fridge  cam_fridge live/fridge "$VIDEO_FRIDGE" 0 fridge       false 960  120   "$GT_FRIDGE" ""
            ;;
        elder_day1)
            # Elder GT cue 3 is [EMPTY] — empty room, prefilter is *expected* to skip.
            # Excluding it keeps Recall meaningful (only [SLEEPING]/[WAKEUP] cues count).
            # full wait=90s: SLEEPING+WAKEUP cues end at ~40s; no point waiting out 7+ min
            # of empty-room footage just to compute the same Recall.
            run_scenario   elder_day1 cam_elder_bedroom   live/elder  "$VIDEO_ELDER_DAY1" 0 elder_wakeup true 90  60 "$GT_ELDER_DAY1" "\\[EMPTY\\]"
            ;;
        elder_day2)
            run_scenario   elder_day2 cam_elder_bedroom_2 live/elder2 "$VIDEO_ELDER_DAY2" 0 elder_wakeup true 90  60 "$GT_ELDER_DAY2" "\\[EMPTY\\]"
            ;;
    esac
done

hdr "All scenarios done"
