#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# bag_replay_run.sh  —  Replay a ROS 2 bag through the monitoring stack and
#                        collect Level 1 / Level 2 KPIs.
#
# Produces deterministic, reproducible benchmark runs from recorded bag data
# without requiring a live robot or simulator.
#
# Usage:
#   bash src/bag_replay_run.sh --bag PATH [OPTIONS]
#
#   --bag  PATH          Path to the bag directory (containing metadata.yaml)
#                        OR a glob pattern – the first match is used
#   --rate R             Replay rate multiplier (default: 1.0, e.g. 2.0 = 2x)
#   --loop N             Replay the bag N times (default: 1; 0 = infinite until Ctrl-C)
#   --plot               Save trigger-timeline PNG plots after analysis
#   --output-parent DIR  Store session under DIR (default: monitoring_sessions/bag_replay)
#
#   GPU and NPU monitoring are enabled automatically when the appropriate
#   hardware and drivers are detected (xe/i915 + qmassa; Intel NPU sysfs).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

REPLAY_PID=0
MONITOR_PID=0

_cleanup() {
  echo ""
  echo "Shutting down..."

  # Bag player
  if [[ "$REPLAY_PID" -gt 0 ]]; then
    kill -SIGINT  "$REPLAY_PID" 2>/dev/null || true
    sleep 1
    kill -SIGKILL "$REPLAY_PID" 2>/dev/null || true
  fi

  # Monitor stack
  if [[ "$MONITOR_PID" -gt 0 ]]; then
    kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  fi

  sleep 1
  # Sweep any leftover ros2 processes (excluding benchmarking scripts)
  pkill -SIGINT  -f "ros2 bag play" 2>/dev/null || true
  sleep 1
  pkill -SIGKILL -f "ros2 bag play" 2>/dev/null || true
  echo "  Done."
}
trap _cleanup EXIT

# ── Argument parsing ──────────────────────────────────────────────────────────
BAG_PATH=""
REPLAY_RATE="1.0"
LOOP_COUNT=1
PLOT_MODE=0
OUTPUT_PARENT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bag)           BAG_PATH="$2";       shift 2 ;;
    --rate)          REPLAY_RATE="$2";    shift 2 ;;
    --loop)          LOOP_COUNT="$2";     shift 2 ;;
    --plot)          PLOT_MODE=1;         shift ;;
    --output-parent) OUTPUT_PARENT="$2";  shift 2 ;;
    -h|--help)
      sed -n '10,24p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      trap - EXIT; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$BAG_PATH" ]]; then
  echo "Error: --bag PATH is required." >&2
  echo "Usage: bash src/bag_replay_run.sh --bag <bag_dir> [--rate 1.0] [--loop 1] [--plot]" >&2
  trap - EXIT; exit 1
fi

# Resolve glob / relative path
if [[ ! -d "$BAG_PATH" ]]; then
  # Try expanding as a glob (e.g. monitoring_sessions/wandering/*/bag)
  _EXPANDED=$(compgen -G "$BAG_PATH" | head -1 || true)
  if [[ -d "${_EXPANDED:-}" ]]; then
    BAG_PATH="$_EXPANDED"
  else
    echo "Error: bag directory not found: $BAG_PATH" >&2
    trap - EXIT; exit 1
  fi
fi

if [[ ! -f "$BAG_PATH/metadata.yaml" ]]; then
  echo "Error: $BAG_PATH does not contain metadata.yaml — is this a valid bag directory?" >&2
  trap - EXIT; exit 1
fi

# Infer bag duration from metadata for progress display
BAG_DURATION_S=""
if command -v python3 &>/dev/null; then
  BAG_DURATION_S=$(python3 -c "
import yaml, sys
try:
    with open('$BAG_PATH/metadata.yaml') as f:
        m = yaml.safe_load(f)
    dur_ns = m.get('rosbag2_bagfile_information', m).get('duration', {}).get('nanoseconds', 0)
    print(f'{dur_ns / 1e9:.0f}')
except Exception:
    pass
" 2>/dev/null || true)
fi

echo "============================================================"
echo "  Bag Replay Benchmark"
echo "    Bag            : $BAG_PATH"
echo "    Rate           : ${REPLAY_RATE}x"
echo "    Loop           : $( [[ "$LOOP_COUNT" -eq 0 ]] && echo 'infinite' || echo "${LOOP_COUNT}×" )"
[[ -n "$BAG_DURATION_S" ]] && echo "    Duration       : ~${BAG_DURATION_S}s per pass"
[[ "$PLOT_MODE"  -eq 1 ]]  && echo "    Plots          : trigger-timeline PNGs"
[[ -n "$OUTPUT_PARENT" ]]   && echo "    Output parent  : $OUTPUT_PARENT"
echo "    HW monitoring  : auto-detect (GPU/NPU enabled if valid drivers present)"
echo "============================================================"
echo ""

# ── Session directory ─────────────────────────────────────────────────────────
_PARENT="${OUTPUT_PARENT:-$REPO_ROOT/monitoring_sessions/bag_replay}"
SESSION_DIR="$_PARENT/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$SESSION_DIR"
echo "  Session dir: $SESSION_DIR"
echo ""

# ── Store provenance ──────────────────────────────────────────────────────────
{
  echo "bag_path=$BAG_PATH"
  echo "replay_rate=$REPLAY_RATE"
  echo "loop_count=$LOOP_COUNT"
  echo "started=$(date --iso-8601=seconds)"
} > "$SESSION_DIR/session_info.txt"

# ── Start monitor stack ───────────────────────────────────────────────────────
echo "Starting monitor stack..."
python3 "$SCRIPT_DIR/monitor_stack.py" \
  --interval 0.5 \
  --output-dir "$SESSION_DIR" \
  --use-sim-time \
  > "$SESSION_DIR/monitor_stack.log" 2>&1 &
MONITOR_PID=$!
echo "  Monitor PID : $MONITOR_PID"
echo ""

# Give the monitor a moment to initialise before data starts arriving
sleep 2

# ── Replay loop ───────────────────────────────────────────────────────────────
START=$(date +%s)
PASS=0
LOOP_ARGS=()
[[ "$LOOP_COUNT" -eq 0 ]] && LOOP_ARGS+=("--loop")

replay_once() {
  PASS=$(( PASS + 1 ))
  echo "--- Pass $PASS / $( [[ "$LOOP_COUNT" -eq 0 ]] && echo '∞' || echo "$LOOP_COUNT" ) ---"
  echo "  Replaying at ${REPLAY_RATE}x …"
  ros2 bag play "$BAG_PATH" \
    --rate "$REPLAY_RATE" \
    --read-ahead-queue-size 1000 \
    2>&1 | tee -a "$SESSION_DIR/replay_$PASS.log" &
  REPLAY_PID=$!
  wait "$REPLAY_PID" || true
  REPLAY_PID=0
  echo "  Pass $PASS complete (elapsed: $(( $(date +%s) - START ))s)"
}

if [[ "$LOOP_COUNT" -eq 0 ]]; then
  # Infinite loop — run until Ctrl-C
  echo "Running in infinite loop until Ctrl-C..."
  while true; do
    replay_once
    sleep 1
  done
else
  for _i in $(seq 1 "$LOOP_COUNT"); do
    replay_once
    [[ "$_i" -lt "$LOOP_COUNT" ]] && sleep 1
  done
fi

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "--- Summary ---"
echo "  Passes completed : $PASS"
echo "  Total elapsed    : ${ELAPSED}s"

# ── Stop monitor and flush data ───────────────────────────────────────────────
if [[ "$MONITOR_PID" -gt 0 ]]; then
  kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  sleep 2
  MONITOR_PID=0
fi

# ── Level 1 KPI analysis ──────────────────────────────────────────────────────
echo ""
echo "━━━━ Level 1 KPI Analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TIMING_CSV="$SESSION_DIR/graph_timing.csv"
TOPO_JSON="$SESSION_DIR/graph_topology.json"

if [[ -f "$TIMING_CSV" && -f "$TOPO_JSON" ]]; then
  PLOT_ARGS=()
  [[ "$PLOT_MODE" -eq 1 ]] && PLOT_ARGS+=("--plot" "--no-show")
  python3 "$SCRIPT_DIR/analyze_trigger_latency.py" \
    --session "$SESSION_DIR" \
    --summary-only \
    --json-out "$SESSION_DIR/kpi.json" \
    "${PLOT_ARGS[@]}"
  echo ""
  echo "  KPI written to : $SESSION_DIR/kpi.json"
else
  echo "  ⚠ Monitor data missing (graph_timing.csv or graph_topology.json not found)"
  echo "    The monitor may not have received any graph data during replay."
  echo "    Ensure the bag contains ROS 2 messages on graph-monitored topics."
  echo "    Session dir: $SESSION_DIR"
fi

# ── Level 2 KPI analysis (chained from Level 1) ───────────────────────────────
if [[ -f "$SESSION_DIR/kpi.json" ]]; then
  echo ""
  echo "━━━━ Level 2 KPI Analysis (chained) ━━━━━━━━━━━━━━━━━━━━━━━━━"
  python3 "$SCRIPT_DIR/analyze_pipeline_latency.py" \
    --kpi "$SESSION_DIR/kpi.json" \
    --json-out "$SESSION_DIR/kpi_level2.json" 2>/dev/null && \
    echo "  KPI L2 written to : $SESSION_DIR/kpi_level2.json" || \
    echo "  ⚠ Level 2 chained analysis failed (check Level 1 KPI has Sensor + Control stages)"
fi

# ── Level 2 traced from original bag (if analyze_bag_e2e.py is available) ────
# Use the original bag to compute traced e2e latency (no re-recording needed).
if [[ -f "$SCRIPT_DIR/analyze_bag_e2e.py" && -f "$SESSION_DIR/kpi.json" && -f "$BAG_PATH/metadata.yaml" ]]; then
  echo ""
  echo "━━━━ Level 2 KPI Analysis (traced from bag) ━━━━━━━━━━━━━━━━━"
  python3 "$SCRIPT_DIR/analyze_bag_e2e.py" \
    --bag "$BAG_PATH" \
    --kpi "$SESSION_DIR/kpi.json" \
    --json-out "$SESSION_DIR/kpi_level2_traced.json" 2>/dev/null && \
    echo "  KPI L2 traced written to : $SESSION_DIR/kpi_level2_traced.json" || \
    echo "  ⚠ Traced e2e analysis failed (bag may lack required Sensor/Control topics)"
fi

echo ""
echo "  Replay benchmark complete → $SESSION_DIR"
echo ""
echo "  Re-run analysis:"
echo "    python3 src/analyze_trigger_latency.py --session $SESSION_DIR"
echo "    python3 src/analyze_pipeline_latency.py --kpi $SESSION_DIR/kpi.json"
