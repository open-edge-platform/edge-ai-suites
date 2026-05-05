#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# picknplace_run.sh  —  Launch the pick-n-place AMR simulation alongside the
#                       graph monitor, then print a trigger-latency analysis.
#
# Usage:
#   bash src/picknplace_run.sh [--timeout SECS] [--record] [--plot]
#                              [--output-parent DIR]
#
#   --timeout N          Hard stop after N seconds (default: 300)
#                        Normal completed run = ~157s from launch.
#                        300s gives ~2× safety margin for sim variance / cube spawn delays.
#   --record             Record KPI topics to an MCAP bag
#   --plot               Also save trigger-timeline PNG plots after analysis
#   --output-parent DIR  Store session under DIR instead of monitoring_sessions/picknplace/

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
  _SWEEP="ros2 |gz sim|gz_server|gz server|/opt/ros/[a-z]*/lib/|gazebo|rtabmap|nav2|turtlebot|warehouse.launch|rviz2"
  pkill -SIGINT  -f "$_SWEEP" 2>/dev/null || true
  sleep 2
  pkill -SIGKILL -f "$_SWEEP" 2>/dev/null || true
  echo "  Done."
}
trap _cleanup EXIT

MAX_TIMEOUT=300   # measured: demo completes ~157s from launch; 300s = ~2× safety margin
RECORD_MODE=0
PLOT_MODE=0
OUTPUT_PARENT=""
SESSION_DIR=""
LAUNCH_LOG=""   # set after SESSION_DIR is created

while [[ $# -gt 0 ]]; do
  case "$1" in
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
echo "  PicknPlace AMR simulation"
echo "    Stop on      : 'ARM2 at standby. Demo complete.' OR ${MAX_TIMEOUT}s timeout"
[[ "$RECORD_MODE" -eq 1 ]] && echo "    Recording     : KPI topics → session bag"
[[ "$PLOT_MODE"   -eq 1 ]] && echo "    Plots         : trigger-timeline PNGs"
[[ -n "$OUTPUT_PARENT" ]] && echo "    Output parent : $OUTPUT_PARENT"
echo "============================================================"
echo ""

# ── Session directory ─────────────────────────────────────────────────────────
_PARENT="${OUTPUT_PARENT:-$REPO_ROOT/monitoring_sessions/picknplace}"
SESSION_DIR="$_PARENT/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$SESSION_DIR"
LAUNCH_LOG="$SESSION_DIR/picknplace_launch.log"
echo "  Session dir: $SESSION_DIR"
echo ""

# ── Pre-run cleanup: kill any leftover processes from a previous run ──────────
echo "Killing any leftover simulation processes before starting..."
# Same pattern rationale as _cleanup above.
_SWEEP="ros2 |gz sim|gz_server|gz server|/opt/ros/[a-z]*/lib/|gazebo|rtabmap|nav2|turtlebot|warehouse.launch|rviz2"
pkill -SIGINT  -f "$_SWEEP" 2>/dev/null || true
sleep 2
pkill -SIGKILL -f "$_SWEEP" 2>/dev/null || true
echo "  Pre-run cleanup done."
echo ""

# ── Process 1: picknplace launch ──────────────────────────────────────────────
echo "Starting AMR simulation..."
setsid nohup ros2 launch picknplace warehouse.launch.py \
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
    /task_status /pick_result /place_result \
    > /tmp/picknplace_record.log 2>&1 &
  RECORD_PID=$!
  echo "  Recording  : $SESSION_DIR/bag  (PID: $RECORD_PID)"
fi

echo ""
echo "Waiting 20s for simulation to initialise..."
sleep 20

# ── Press Gazebo play button ──────────────────────────────────────────────────
echo "Pressing Gazebo play button..."
gz service -s /world/default/control \
  --reqtype gz.msgs.WorldControl \
  --reptype gz.msgs.Boolean \
  --req 'pause: false' \
  --timeout 2000 2>/dev/null || echo "  (gz play button: service call failed — sim may already be running)"

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

# ── Main loop — wait for "ARM2 at standby. Demo complete." or timeout ─────────
echo "Waiting for 'ARM2 at standby. Demo complete.' (timeout: ${MAX_TIMEOUT}s)..."
START=$(date +%s)
DEMO_COMPLETE=0
TASK_COUNT=0

while true; do
  sleep 1
  ELAPSED=$(( $(date +%s) - START ))

  # Count task completions in log
  CURRENT_TASKS=$(grep -c 'ARM2 at standby\. Demo complete\|GRASP SUCCESS\|Placed successfully\|CYCLE COMPLETE' \
                  "$LAUNCH_LOG" 2>/dev/null || true)
  CURRENT_TASKS=$(( ${CURRENT_TASKS:-0} + 0 ))

  while [[ "$TASK_COUNT" -lt "$CURRENT_TASKS" ]]; do
    TASK_COUNT=$(( TASK_COUNT + 1 ))
    echo "  ✔ Task #${TASK_COUNT} complete at $(date '+%H:%M:%S')"
  done

  # Check for full demo completion — actual string from arm2_controller.py
  if grep -q 'ARM2 at standby. Demo complete.' "$LAUNCH_LOG" 2>/dev/null; then
    DEMO_COMPLETE=1
    echo "  ✅ AMR DEMO COMPLETE at $(date '+%H:%M:%S') (${ELAPSED}s)"
    break
  fi

  [[ "$MAX_TIMEOUT" -gt 0 && "$ELAPSED" -ge "$MAX_TIMEOUT" ]] \
    && { echo "  Timeout: ${MAX_TIMEOUT}s elapsed. Stopping."; break; }
done

echo ""
echo "--- Summary ---"
echo "  Tasks completed : $TASK_COUNT"
echo "  Demo complete   : $([ $DEMO_COMPLETE -eq 1 ] && echo yes || echo no)"
echo "  Elapsed         : $(( $(date +%s) - START ))s"

# ── Bag reindex safety-net ────────────────────────────────────────────────────
if [[ "$RECORD_MODE" -eq 1 && -d "$SESSION_DIR/bag" && ! -f "$SESSION_DIR/bag/metadata.yaml" ]]; then
  echo ""
  echo "  ⚠ Bag metadata missing — reindexing..."
  ros2 bag reindex "$SESSION_DIR/bag" 2>&1 | grep -v '^\[INFO\]' || true
fi

# ── Trigger-latency analysis ──────────────────────────────────────────────────
echo ""
echo "━━━━ Trigger-Latency Analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Stop graph monitor so it flushes CSV + topology before we read them
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
