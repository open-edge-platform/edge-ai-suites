#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# wandering_run.sh  —  Launch the wandering simulation alongside the graph
#                       monitor, then print a trigger-latency analysis at the end.
#
# Usage:
#   bash src/wandering_run.sh [--goals N] [--timeout SECS] [--record] [--plot]
#                              [--output-parent DIR]
#
#   --goals  N           Stop after N 'Goal was reached' events (0 = ignore, default: Ctrl-C)
#   --timeout N          Hard stop after N seconds (default: 0 = off)
#   --record             Record KPI topics to an MCAP bag
#   --plot               Also save trigger-timeline PNG plots after analysis
#   --output-parent DIR  Store session under DIR instead of monitoring_sessions/wandering/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

LAUNCH_PID=0
MONITOR_PID=0
RECORD_PID=0

_cleanup() {
  echo ""
  echo "Shutting down..."

  # Bag recorder — send SIGINT first so it can flush metadata
  if [[ "$RECORD_PID" -gt 0 ]]; then
    kill -SIGINT "$RECORD_PID" 2>/dev/null || true
    echo "  Waiting for bag recorder to flush (max 15s)..."
    for _i in $(seq 1 15); do
      kill -0 "$RECORD_PID" 2>/dev/null || break
      sleep 1
    done
    kill -SIGKILL "$RECORD_PID" 2>/dev/null || true
  fi

  # Graph monitor
  if [[ "$MONITOR_PID" -gt 0 ]]; then
    kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  fi

  # Launch process group (setsid makes it a session leader)
  if [[ "$LAUNCH_PID" -gt 0 ]]; then
    kill -SIGINT  -- -"$LAUNCH_PID" 2>/dev/null || true
    kill -SIGINT         "$LAUNCH_PID" 2>/dev/null || true
    sleep 2
    kill -SIGKILL -- -"$LAUNCH_PID" 2>/dev/null || true
    kill -SIGKILL        "$LAUNCH_PID" 2>/dev/null || true
  fi

  sleep 1
  # Sweep any survivors.
  # "ros2 " (trailing space) avoids matching repo paths containing "ros2-kpi".
  # "/opt/ros/[a-z]*/lib/" matches installed node executables but not scripts
  # under /opt/ros/<distro>/benchmarking/.
  _SWEEP="ros2 |gz sim|gz_server|gz server|/opt/ros/[a-z]*/lib/|gazebo|rtabmap|nav2|turtlebot|wandering_gazebo|rviz2"
  pkill -SIGINT  -f "$_SWEEP" 2>/dev/null || true
  sleep 2
  pkill -SIGKILL -f "$_SWEEP" 2>/dev/null || true
  echo "  Done."
}
trap _cleanup EXIT

GOAL_TARGET=0
MAX_TIMEOUT=0
RECORD_MODE=0
PLOT_MODE=0
SESSION_DIR=""
OUTPUT_PARENT=""
LAUNCH_LOG=""   # set after SESSION_DIR is created

while [[ $# -gt 0 ]]; do
  case "$1" in
    --goals)          GOAL_TARGET="$2"; shift 2 ;;
    --timeout)        MAX_TIMEOUT="$2"; shift 2 ;;
    --record)         RECORD_MODE=1; shift ;;
    --plot)           PLOT_MODE=1; shift ;;
    --output-parent)  OUTPUT_PARENT="$2"; shift 2 ;;
    -h|--help)
      sed -n '10,18p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      trap - EXIT; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

echo "============================================================"
echo "  Wandering simulation"
if   [[ "$GOAL_TARGET" -gt 0 ]]; then
  echo "    Stop after goals : $GOAL_TARGET"
elif [[ "$MAX_TIMEOUT" -gt 0 ]]; then
  echo "    Stop after       : ${MAX_TIMEOUT}s (goals ignored)"
else
  echo "    Stop with        : Ctrl-C"
fi
[[ "$MAX_TIMEOUT"  -gt 0 ]] && [[ "$GOAL_TARGET" -gt 0 ]] && \
  echo "    Hard timeout     : ${MAX_TIMEOUT}s"
[[ "$RECORD_MODE"  -eq 1 ]] && echo "    Recording        : KPI topics → session bag"
[[ "$PLOT_MODE"    -eq 1 ]] && echo "    Plots            : trigger-timeline PNGs"
[[ -n "$OUTPUT_PARENT" ]]   && echo "    Output parent    : $OUTPUT_PARENT"
echo "============================================================"
echo ""

# ── Session directory (shared by bag recorder + graph monitor) ───────────────
_PARENT="${OUTPUT_PARENT:-$REPO_ROOT/monitoring_sessions/wandering}"
SESSION_DIR="$_PARENT/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$SESSION_DIR"
LAUNCH_LOG="$SESSION_DIR/wandering_launch.log"
echo "  Session dir: $SESSION_DIR"
echo ""

# ── Pre-run cleanup: kill any leftover processes from a previous run ──────────
echo "Killing any leftover simulation processes before starting..."
# Same pattern rationale as _cleanup above.
_SWEEP="ros2 |gz sim|gz_server|gz server|/opt/ros/[a-z]*/lib/|gazebo|rtabmap|nav2|turtlebot|wandering_gazebo|rviz2"
pkill -SIGINT  -f "$_SWEEP" 2>/dev/null || true
sleep 2
pkill -SIGKILL -f "$_SWEEP" 2>/dev/null || true
echo "  Pre-run cleanup done."
echo ""

# ── Process 1: wandering launch ───────────────────────────────────────────────
echo "Starting wandering simulation..."
setsid nohup ros2 launch wandering_gazebo_tutorial wandering_gazebo.launch.py \
  > "$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!
echo "  Launch PID : $LAUNCH_PID  (log: $LAUNCH_LOG)"

# ── Optional bag recorder ─────────────────────────────────────────────────────
if [[ "$RECORD_MODE" -eq 1 ]]; then
  ros2 bag record -o "$SESSION_DIR/bag" \
    /scan /imu /odom /tf /tf_static /map /map_updates \
    /local_costmap/costmap_raw \
    /local_costmap/published_footprint \
    /global_costmap/costmap_raw \
    /global_costmap/published_footprint \
    /cmd_vel_nav /cmd_vel_smoothed /cmd_vel /plan /plan_smoothed \
    /optimal_trajectory /transformed_global_plan \
    /localization_pose \
    /goal_pose /goal_reached \
    /speed_limit \
    /collision_monitor_state \
    /behavior_tree_log \
    /joint_states \
    > /tmp/wandering_record.log 2>&1 &
  RECORD_PID=$!
  echo "  Recording  : $SESSION_DIR/bag  (PID: $RECORD_PID)"
fi

echo ""
echo "Waiting 12s for simulation to initialise..."
sleep 12

# ── Process 2: graph monitor ──────────────────────────────────────────────────
echo "Starting graph monitor..."
python3 "$SCRIPT_DIR/monitor_stack.py" \
  --graph-only \
  --interval 0.5 \
  --output-dir "$SESSION_DIR" \
  --use-sim-time \
  > "$SESSION_DIR/monitor_stack.log" 2>&1 &
MONITOR_PID=$!
echo "  Monitor PID : $MONITOR_PID"
echo ""

# ── Main loop ─────────────────────────────────────────────────────────────────
if [[ "$GOAL_TARGET" -gt 0 ]]; then
  echo "Watching for goals (stop at $GOAL_TARGET)..."
elif [[ "$MAX_TIMEOUT" -gt 0 ]]; then
  echo "Running for ${MAX_TIMEOUT}s (goals tracked but not used to stop)..."
else
  echo "Running until Ctrl-C..."
fi
START=$(date +%s)
GOAL_ARRIVALS=0

while true; do
  sleep 1
  ELAPSED=$(( $(date +%s) - START ))

  CURRENT_GOALS=$(grep -c 'Goal was reached' "$LAUNCH_LOG" 2>/dev/null || true)
  CURRENT_GOALS=$(( ${CURRENT_GOALS:-0} + 0 ))

  while [[ "$GOAL_ARRIVALS" -lt "$CURRENT_GOALS" ]]; do
    GOAL_ARRIVALS=$(( GOAL_ARRIVALS + 1 ))
    RAW_TS=$(grep 'Goal was reached' "$LAUNCH_LOG" 2>/dev/null \
             | sed -n "${GOAL_ARRIVALS}p" \
             | grep -oP '\[\K[0-9]+(?=\.[0-9]+\])')
    if [[ -n "${RAW_TS:-}" ]]; then
      ARRIVAL_TS=$(date -d "@${RAW_TS}" '+%H:%M:%S')
    else
      ARRIVAL_TS=$(date '+%H:%M:%S')
    fi
    echo "  ✔ Goal #${GOAL_ARRIVALS} at ${ARRIVAL_TS}"
  done

  [[ "$GOAL_TARGET" -gt 0 && "$GOAL_ARRIVALS" -ge "$GOAL_TARGET" ]] \
    && { echo "All ${GOAL_TARGET} goal(s) reached — stopping."; break; }

  [[ "$MAX_TIMEOUT" -gt 0 && "$ELAPSED" -ge "$MAX_TIMEOUT" ]] \
    && { echo "Timeout: ${MAX_TIMEOUT}s elapsed (goals: ${GOAL_ARRIVALS})."; break; }
done

echo ""
echo "--- Summary ---"
echo "  Goals reached : $GOAL_ARRIVALS"
echo "  Elapsed       : $(( $(date +%s) - START ))s"

# ── Bag reindex safety-net ────────────────────────────────────────────────────
if [[ "$RECORD_MODE" -eq 1 && -d "$SESSION_DIR/bag" && ! -f "$SESSION_DIR/bag/metadata.yaml" ]]; then
  echo ""
  echo "  ⚠ Bag metadata missing — reindexing..."
  ros2 bag reindex "$SESSION_DIR/bag" 2>&1 | grep -v '^\[INFO\]' || true
fi

# ── Trigger-latency analysis ──────────────────────────────────────────────────
echo ""
echo "━━━━ Trigger-Latency Analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Stop the graph monitor so it flushes CSV + topology before we read them
if [[ "$MONITOR_PID" -gt 0 ]]; then
  kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  sleep 2
  MONITOR_PID=0
fi

TIMING_CSV="$SESSION_DIR/graph_timing.csv"
TOPO_JSON="$SESSION_DIR/graph_topology.json"

if [[ -f "$TIMING_CSV" && -f "$TOPO_JSON" ]]; then
  PLOT_ARGS=()
  [[ "$PLOT_MODE" -eq 1 ]] && PLOT_ARGS+=("--plot" "--no-show")
  python3 "$SCRIPT_DIR/analyze_trigger_latency.py" \
    --session "$SESSION_DIR" \
    --summary-only \
    "${PLOT_ARGS[@]}"
  echo ""
  echo "  Full detail:"
  echo "    python3 src/analyze_trigger_latency.py --session $SESSION_DIR"

  # Copy topology into bag/ subdir so --bag analysis works without --topology
  if [[ "$RECORD_MODE" -eq 1 && -d "$SESSION_DIR/bag" ]]; then
    cp "$TOPO_JSON" "$SESSION_DIR/bag/graph_topology.json"
    echo ""
    echo "  Bag analysis:"
    echo "    python3 src/analyze_trigger_latency.py --bag $SESSION_DIR/bag"
    echo ""
    echo "  Running bag-based KPI analysis (for benchmark aggregation)..."
    python3 "$SCRIPT_DIR/analyze_trigger_latency.py" \
      --bag "$SESSION_DIR/bag" \
      --summary-only \
      --json-out "$SESSION_DIR/kpi.json" \
      "${PLOT_ARGS[@]}" 2>/dev/null || \
      echo "  ⚠ Bag analysis failed (bag may still be flushing)"
  fi
else
  echo "  ⚠ Monitor data missing (graph_timing.csv or graph_topology.json not found)"
  echo "    Session dir: $SESSION_DIR"
fi
