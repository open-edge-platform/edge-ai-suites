#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# fastmapping_run.sh  —  Launch fast_mapping_node with a ROS 2 bag replay and
#                        collect Level 1 / Level 2 KPIs via the monitor stack.
#
# Usage:
#   bash src/fastmapping_run.sh [--bag PATH] [--rate R] [--loop N] [--plot]
#                               [--output-parent DIR]
#
#   --bag  PATH          Bag directory to replay (default: bundled spinning bag
#                        at /opt/ros/<distro>/share/bagfiles/spinning)
#   --rate R             Replay rate multiplier (default: 1.0)
#   --loop N             Number of replay passes (default: 1; 0 = until Ctrl-C)
#   --plot               Save trigger-timeline PNG plots after analysis
#   --output-parent DIR  Store session under DIR instead of
#                        monitoring_sessions/fastmapping
#
#   GPU and NPU monitoring are enabled automatically when the appropriate
#   hardware and drivers are detected (xe/i915 + qmassa; Intel NPU sysfs).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

NODE_PID=0
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

  # fast_mapping_node
  if [[ "$NODE_PID" -gt 0 ]]; then
    kill -SIGINT  "$NODE_PID" 2>/dev/null || true
    sleep 1
    kill -SIGKILL "$NODE_PID" 2>/dev/null || true
  fi

  # Monitor stack
  if [[ "$MONITOR_PID" -gt 0 ]]; then
    kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  fi

  sleep 1
  pkill -SIGINT  -f "fast_mapping_node|ros2 bag play|fastmapping_run" 2>/dev/null || true
  sleep 1
  pkill -SIGKILL -f "fast_mapping_node|ros2 bag play" 2>/dev/null || true
  echo "  Done."
}
trap _cleanup EXIT

# ── Defaults ──────────────────────────────────────────────────────────────────
# Auto-detect ROS distro: prefer env var, then probe installed distros
if [[ -z "${ROS_DISTRO:-}" ]]; then
  for _d in jazzy humble iron; do
    [[ -d "/opt/ros/$_d" ]] && ROS_DISTRO="$_d" && break
  done
  ROS_DISTRO="${ROS_DISTRO:-jazzy}"
fi
DEFAULT_BAG="/opt/ros/${ROS_DISTRO}/share/bagfiles/spinning"
BAG_PATH=""
REPLAY_RATE="1.0"
LOOP_COUNT=1
PLOT_MODE=0
OUTPUT_PARENT=""

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bag)           BAG_PATH="$2";       shift 2 ;;
    --rate)          REPLAY_RATE="$2";    shift 2 ;;
    --loop)          LOOP_COUNT="$2";     shift 2 ;;
    --plot)          PLOT_MODE=1;         shift ;;
    --output-parent) OUTPUT_PARENT="$2";  shift 2 ;;
    -h|--help)
      sed -n '10,23p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      trap - EXIT; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Resolve bag path
BAG_PATH="${BAG_PATH:-$DEFAULT_BAG}"
if [[ ! -d "$BAG_PATH" ]]; then
  echo "Error: bag directory not found: $BAG_PATH" >&2
  trap - EXIT; exit 1
fi
if [[ ! -f "$BAG_PATH/metadata.yaml" ]]; then
  echo "Error: $BAG_PATH does not contain metadata.yaml — is this a valid bag directory?" >&2
  trap - EXIT; exit 1
fi

# Infer bag duration for display
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
echo "  Fast Mapping Benchmark"
echo "    Bag            : $BAG_PATH"
echo "    Rate           : ${REPLAY_RATE}x"
echo "    Loop           : $( [[ "$LOOP_COUNT" -eq 0 ]] && echo 'infinite' || echo "${LOOP_COUNT}×" )"
[[ -n "$BAG_DURATION_S" ]] && echo "    Duration       : ~${BAG_DURATION_S}s per pass"
[[ "$PLOT_MODE"  -eq 1 ]]  && echo "    Plots          : trigger-timeline PNGs"
[[ -n "$OUTPUT_PARENT" ]]  && echo "    Output parent  : $OUTPUT_PARENT"
echo "    HW monitoring  : auto-detect (GPU/NPU enabled if valid drivers present)"
echo "============================================================"
echo ""

# ── Session directory ─────────────────────────────────────────────────────────
_PARENT="${OUTPUT_PARENT:-$REPO_ROOT/monitoring_sessions/fastmapping}"
SESSION_DIR="$_PARENT/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$SESSION_DIR"
NODE_LOG="$SESSION_DIR/fast_mapping_node.log"
echo "  Session dir: $SESSION_DIR"
echo ""

# Save provenance
{
  echo "algorithm=fastmapping"
  echo "bag_path=$BAG_PATH"
  echo "replay_rate=$REPLAY_RATE"
  echo "loop_count=$LOOP_COUNT"
  echo "started=$(date --iso-8601=seconds)"
} > "$SESSION_DIR/session_info.txt"

# ── Pre-run cleanup ───────────────────────────────────────────────────────────
echo "Killing any leftover fast_mapping processes..."
pkill -SIGKILL -f "fast_mapping_node|ros2 bag play" 2>/dev/null || true
sleep 1
echo "  Pre-run cleanup done."
echo ""

# ── Process 1: fast_mapping_node ──────────────────────────────────────────────
echo "Starting fast_mapping_node..."
ros2 run fast_mapping fast_mapping_node \
  > "$NODE_LOG" 2>&1 &
NODE_PID=$!
echo "  Node PID   : $NODE_PID  (log: $NODE_LOG)"

# Give the node time to initialise before data arrives
echo "Waiting 5s for fast_mapping_node to initialise..."
sleep 5

# ── Process 2: monitor stack ──────────────────────────────────────────────────
echo "Starting monitor stack..."
python3 "$SCRIPT_DIR/monitor_stack.py" \
  --interval 0.5 \
  --output-dir "$SESSION_DIR" \
  > "$SESSION_DIR/monitor_stack.log" 2>&1 &
MONITOR_PID=$!
echo "  Monitor PID : $MONITOR_PID"
echo ""

sleep 1

# ── Replay loop ───────────────────────────────────────────────────────────────
START=$(date +%s)
PASS=0

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

# ── Trigger node shutdown now so it starts flushing while we stop the monitor ─
# The node blocks on wait_for_frame up to ~30s after the bag ends.  Sending
# SIGINT here gives it maximum time to unblock and print its procedure table.
if [[ "$NODE_PID" -gt 0 ]]; then
  kill -SIGINT "$NODE_PID" 2>/dev/null || true
fi

# ── Stop monitor and flush data ───────────────────────────────────────────────
if [[ "$MONITOR_PID" -gt 0 ]]; then
  kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  sleep 2
  MONITOR_PID=0
fi

# ── Wait for fast_mapping_node to finish its procedure table ──────────────────
if [[ "$NODE_PID" -gt 0 ]]; then
  echo "Waiting for fast_mapping_node procedure table (up to 60s)..."
  _FLUSH_TIMEOUT=60
  for _i in $(seq 1 "$_FLUSH_TIMEOUT"); do
    kill -0 "$NODE_PID" 2>/dev/null || break           # exited cleanly
    grep -q "Total elapsed time" "$NODE_LOG" 2>/dev/null && break  # table ready
    sleep 1
  done
  kill -SIGKILL "$NODE_PID" 2>/dev/null || true
  NODE_PID=0
  echo "  Node stopped."
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
  echo "    The graph monitor may not have observed any fast_mapping_node activity."
  echo "    Ensure fast_mapping_node published on monitored topics during replay."
  echo "    Session dir: $SESSION_DIR"
fi

# ── fast_mapping_node log analysis (patch kpi.json with real node metrics) ────
echo ""
echo "━━━━ fast_mapping_node Log Analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ -f "$NODE_LOG" ]]; then
  python3 "$SCRIPT_DIR/analyze_fastmapping_log.py" \
    --session "$SESSION_DIR" \
    --log "$NODE_LOG" || \
    echo "  ⚠ fast_mapping_node log analysis failed"
else
  echo "  ⚠ fast_mapping_node.log not found — node may not have started"
fi

# ── Level 2 KPI analysis (chained) ───────────────────────────────────────────
if [[ -f "$SESSION_DIR/kpi.json" ]]; then
  echo ""
  echo "━━━━ Level 2 KPI Analysis (chained) ━━━━━━━━━━━━━━━━━━━━━━━━━"
  python3 "$SCRIPT_DIR/analyze_pipeline_latency.py" \
    --kpi "$SESSION_DIR/kpi.json" \
    --json-out "$SESSION_DIR/kpi_level2.json" 2>/dev/null && \
    echo "  KPI L2 written to : $SESSION_DIR/kpi_level2.json" || \
    echo "  ⚠ Level 2 chained analysis failed"
fi

echo ""
echo "  Fast Mapping benchmark complete → $SESSION_DIR"
echo ""
echo "  Re-run analysis:"
echo "    python3 src/analyze_trigger_latency.py --session $SESSION_DIR"
echo "    python3 src/analyze_pipeline_latency.py --kpi $SESSION_DIR/kpi.json"
