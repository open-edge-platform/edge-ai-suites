#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# benchmark_runner.sh — Generic ROS 2 benchmark orchestrator driven by a YAML run profile.
#
# Usage:
#   bash src/benchmark_runner.sh --run-config <config.yaml> [OPTIONS]
#
#   --run-config FILE    Path to run profile YAML (required — see config/)
#   --goals N            Stop after N goal events (overrides yaml stop.goal_count)
#   --timeout SECS       Hard stop in seconds (overrides yaml stop.timeout; 0=off)
#   --record             Record KPI topics to an MCAP bag
#   --plot               Save trigger-timeline PNGs after analysis
#   --show               Plot and display trigger timeline window after analysis
#   --output-parent DIR  Session parent directory (overrides yaml session.output_subdir)
#   --side-terminals     Open htop + qmassa in Terminator windows
#   --no-prompt          Export default KPI outputs and skip interactive menus
#
#   All scenario behavior (launch command, bag topics, stop condition, sweep
#   pattern, Gazebo play button, etc.) is controlled by the YAML run profile.
#   GPU/NPU monitoring is auto-detected; no flag needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Prefer uv when available (dev machines); fall back to plain python3 on
# deployed boxes where uv isn't installed.
_PYTHON=$(command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python3")

# shellcheck source=./_session_menu.sh disable=SC1091
source "$SCRIPT_DIR/_session_menu.sh"

# ── ROS 2 environment check ───────────────────────────────────────────────────
if ! command -v ros2 &>/dev/null; then
  echo "ERROR: 'ros2' not found in PATH — ROS 2 environment is not sourced." >&2
  echo ""
  echo "  Run one of:" >&2
  echo "    source /opt/ros/jazzy/setup.bash" >&2
  echo "    source /opt/ros/humble/setup.bash" >&2
  echo "    source ./setup_ros2_env.sh" >&2
  echo ""
  exit 1
fi

LAUNCH_PID=0
MONITOR_PID=0
RECORD_PID=0

# _pkill_sweep <signal> — kill processes matching CONF_SWEEP that are NOT in
# our own process group.  Launched processes are started with 'setsid', giving
# them a new session/PGID, so they will be killed.  make's recipe shell and
# benchmark_runner.sh share our PGID and are therefore excluded automatically.
_pkill_sweep() {
  local _sig="${1:--SIGINT}"
  local _my_pgid _pid _pgid
  _my_pgid=$(ps -o pgid= -p $$ | tr -d ' ')
  while IFS= read -r _pid; do
    _pgid=$(ps -o pgid= -p "$_pid" 2>/dev/null | tr -d ' ')
    if [[ -n "$_pgid" && "$_pgid" != "$_my_pgid" ]]; then
      kill "$_sig" "$_pid" 2>/dev/null || true
    fi
  done < <(pgrep -f "${CONF_SWEEP:-ros2 }" 2>/dev/null)
}

# _cleanup is defined after CONF_SWEEP is set, so use a variable reference.
_cleanup() {
  echo ""
  echo "Shutting down..."

  # Bag recorder — SIGINT first so it can flush MCAP metadata, then SIGKILL
  if [[ "$RECORD_PID" -gt 0 ]]; then
    kill -SIGINT "$RECORD_PID" 2>/dev/null || true
    echo "  Waiting for bag recorder to flush (max 15s)..."
    for _i in $(seq 1 15); do
      kill -0 "$RECORD_PID" 2>/dev/null || break
      sleep 1
    done
    kill -SIGKILL "$RECORD_PID" 2>/dev/null || true
  fi

  # Stack monitor
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
  # Sweep any survivors using the scenario-specific pattern from YAML.
  _pkill_sweep -SIGINT
  sleep 2
  _pkill_sweep -SIGKILL
  echo "  Done."
}
trap _cleanup EXIT

# ── Locate --run-config before full arg parsing so we can load YAML first ────
# Scenario wrappers (e.g. wandering_run.sh) prepend their own default
# --run-config before forwarding "$@"; take the LAST occurrence so a
# caller-supplied --run-config overrides the wrapper's default.
RUN_CONFIG=""
for (( _i=1; _i<=$#; _i++ )); do
  if [[ "${!_i}" == "--run-config" ]]; then
    _next=$(( _i + 1 ))
    RUN_CONFIG="${!_next:-}"
  fi
done

if [[ -z "$RUN_CONFIG" ]]; then
  echo "ERROR: --run-config <file> is required" >&2
  echo "       e.g.  bash src/benchmark_runner.sh --run-config config/wandering_run.yaml" >&2
  exit 1
fi
if [[ ! -f "$RUN_CONFIG" ]]; then
  echo "ERROR: Run config not found: $RUN_CONFIG" >&2
  exit 1
fi

# ── Load all YAML config values into CONF_* shell variables ──────────────────
eval "$($_PYTHON "$SCRIPT_DIR/benchmark_profiler.py" --config "$RUN_CONFIG" --export-bash)"

# ── CLI defaults from YAML (CLI flags below may override) ─────────────────────
GOAL_TARGET=$CONF_GOAL_COUNT
MAX_TIMEOUT=$CONF_TIMEOUT
RECORD_MODE=0
PLOT_MODE=0
SHOW_MODE=0
SIDE_TERMINALS=0
NO_PROMPT=0
OUTPUT_PARENT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-config)      shift 2 ;;            # already consumed above
    --goals)           GOAL_TARGET="$2"; shift 2 ;;
    --timeout)         MAX_TIMEOUT="$2"; shift 2 ;;
    --record)          RECORD_MODE=1; shift ;;
    --plot)            PLOT_MODE=1; shift ;;
    --show)            SHOW_MODE=1; RECORD_MODE=1; PLOT_MODE=1; shift ;;
    --output-parent)   OUTPUT_PARENT="$2"; shift 2 ;;
    --side-terminals)  SIDE_TERMINALS=1; shift ;;
    --no-prompt)       NO_PROMPT=1; shift ;;
    -h|--help)
      sed -n '10,23p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      trap - EXIT; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Banner ────────────────────────────────────────────────────────────────────
echo "============================================================"
echo "  ${CONF_SCENARIO} benchmark"
if [[ -n "$CONF_DONE_PATTERN" ]]; then
  echo "    Stop on      : '${CONF_DONE_PATTERN}' OR ${MAX_TIMEOUT}s timeout"
elif [[ "$GOAL_TARGET" -gt 0 ]]; then
  echo "    Stop after goals : $GOAL_TARGET"
elif [[ "$MAX_TIMEOUT" -gt 0 ]]; then
  echo "    Stop after   : ${MAX_TIMEOUT}s (goals tracked but not used to stop)"
else
  echo "    Stop with    : Ctrl-C"
fi
[[ "$MAX_TIMEOUT"  -gt 0 && "$GOAL_TARGET" -gt 0 ]] && \
  echo "    Hard timeout : ${MAX_TIMEOUT}s"
[[ "$RECORD_MODE"  -eq 1 ]] && echo "    Recording    : KPI topics → session bag"
[[ "$PLOT_MODE"    -eq 1 ]] && echo "    Plots        : trigger-timeline PNGs"
[[ -n "$OUTPUT_PARENT" ]]   && echo "    Output parent: $OUTPUT_PARENT"
echo "    HW monitoring: auto-detect (GPU/NPU enabled if valid drivers present)"
echo "============================================================"
echo ""

# ── Session directory (shared by bag recorder + monitor) ─────────────────────
if [[ -n "$OUTPUT_PARENT" ]]; then
  _PARENT="$OUTPUT_PARENT"
else
  _PARENT="$REPO_ROOT/monitoring_sessions/$CONF_OUTPUT_SUBDIR"
fi
SESSION_DIR="$_PARENT/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$SESSION_DIR"
LAUNCH_LOG="$SESSION_DIR/${CONF_LOG_PREFIX}_launch.log"
echo "  Session dir: $SESSION_DIR"
echo ""

# ── Pre-run cleanup: kill any leftover processes from a previous run ──────────
echo "[1/6] Pre-run cleanup..."
_pkill_sweep -SIGINT
sleep 2
_pkill_sweep -SIGKILL
echo "  Pre-run cleanup done."
echo ""

# ── Process 1: application launch ────────────────────────────────────────────
echo "[2/6] Launching ${CONF_SCENARIO} simulation..."
# shellcheck disable=SC2086
setsid nohup env ${CONF_LAUNCH_ENV} ${CONF_LAUNCH_CMD} > "$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!
echo "  Launch PID : $LAUNCH_PID  (log: $LAUNCH_LOG)"

# ── Optional bag recorder ─────────────────────────────────────────────────────
if [[ "$RECORD_MODE" -eq 1 ]]; then
  # shellcheck disable=SC2086
  ros2 bag record -o "$SESSION_DIR/bag" $CONF_TOPICS \
    > "$CONF_RECORD_LOG" 2>&1 &
  RECORD_PID=$!
  echo "  Recording  : $SESSION_DIR/bag  (PID: $RECORD_PID)"
fi

echo ""
echo "Waiting ${CONF_INIT_SLEEP}s for simulation to initialize..."
sleep "$CONF_INIT_SLEEP"

# ── Optional: press Gazebo play button ───────────────────────────────────────
if [[ "$CONF_PRESS_PLAY" -eq 1 ]]; then
  echo "Pressing Gazebo play button..."
  gz service -s /world/default/control \
    --reqtype gz.msgs.WorldControl \
    --reptype gz.msgs.Boolean \
    --req 'pause: false' \
    --timeout 2000 2>/dev/null \
    || echo "  (gz play button: service call failed — sim may already be running)"
fi

# ── Process 2: stack monitor (graph + resources + auto-detected GPU/NPU) ─────
# GPU and NPU are enabled automatically by monitor_stack.py when the correct
# drivers and tools are present (xe/qmassa, i915/qmassa, Intel NPU sysfs).
echo "[3/6] Starting monitor stack..."
MONITOR_ARGS=("--interval" "0.5" "--output-dir" "$SESSION_DIR" "--use-sim-time")
[[ "$CONF_GRAPH_ONLY" -eq 1 ]] && MONITOR_ARGS+=("--graph-only")
[[ "$LAUNCH_PID" -gt 0 ]] && MONITOR_ARGS+=("--root-pid" "$LAUNCH_PID")
$_PYTHON "$SCRIPT_DIR/monitor_stack.py" "${MONITOR_ARGS[@]}" \
  > "$SESSION_DIR/monitor_stack.log" 2>&1 &
MONITOR_PID=$!
echo "  Monitor PID : $MONITOR_PID"

# ── Optional side terminals (htop + qmassa) ───────────────────────────────────
if [[ "$SIDE_TERMINALS" -eq 1 ]]; then
  if command -v terminator &>/dev/null; then
    echo "  Opening side terminals..."
    terminator -e "htop" --title="htop — ${CONF_SCENARIO} monitor" &
    _QMASSA=$(command -v qmassa 2>/dev/null \
      || find ~/.cargo/bin ~/.local/bin /usr/bin -maxdepth 1 -name qmassa 2>/dev/null \
      | head -1 || true)
    if [[ -n "$_QMASSA" ]]; then
      terminator -e "$_QMASSA" --title="qmassa — GPU monitor" &
      echo "  Side terminals : htop + qmassa"
    else
      echo "  Side terminals : htop only (qmassa not found — run: make install-qmassa)"
    fi
  else
    echo "  WARNING: --side-terminals requested but 'terminator' not found on PATH" >&2
  fi
fi
echo ""

# ── Main loop ─────────────────────────────────────────────────────────────────
echo "[4/6] Running benchmark..."
if [[ -n "$CONF_DONE_PATTERN" ]]; then
  echo "Waiting for '${CONF_DONE_PATTERN}' (timeout: ${MAX_TIMEOUT}s)..."
elif [[ "$GOAL_TARGET" -gt 0 ]]; then
  echo "Watching for goals (stop at $GOAL_TARGET)..."
elif [[ "$MAX_TIMEOUT" -gt 0 ]]; then
  echo "Running for ${MAX_TIMEOUT}s (goals tracked but not used to stop)..."
else
  echo "Running until Ctrl-C..."
fi

START=$(date +%s)
GOAL_COUNT=0
TASK_COUNT=0
DONE_COMPLETE=0

# Catch Ctrl-C here so the run stops gracefully into the normal shutdown +
# post-run analysis menu below, instead of the default SIGINT disposition
# terminating the script immediately (which would skip straight to the
# _cleanup EXIT trap and never show the menu).
_INTERRUPTED=0
trap '_INTERRUPTED=1' SIGINT

while true; do
  sleep 1 || true
  if [[ "$_INTERRUPTED" -eq 1 ]]; then
    echo "Interrupted by user (Ctrl-C) — stopping run early."
    break
  fi
  ELAPSED=$(( $(date +%s) - START ))

  # ── Goal tracking (e.g. wandering) ───────────────────────────────────────
  if [[ -n "$CONF_GOAL_PATTERN" ]]; then
    CURRENT_GOALS=$(grep -c "$CONF_GOAL_PATTERN" "$LAUNCH_LOG" 2>/dev/null || true)
    CURRENT_GOALS=$(( ${CURRENT_GOALS:-0} + 0 ))
    while [[ "$GOAL_COUNT" -lt "$CURRENT_GOALS" ]]; do
      GOAL_COUNT=$(( GOAL_COUNT + 1 ))
      RAW_TS=$(grep "$CONF_GOAL_PATTERN" "$LAUNCH_LOG" 2>/dev/null \
               | sed -n "${GOAL_COUNT}p" \
               | grep -oP '\[\K[0-9]+(?=\.[0-9]+\])' || true)
      if [[ -n "${RAW_TS:-}" ]]; then
        TS=$(date -d "@${RAW_TS}" '+%H:%M:%S')
      else
        TS=$(date '+%H:%M:%S')
      fi
      echo "  ✔ Goal #${GOAL_COUNT} at ${TS}"
    done
  fi

  # ── Task tracking (e.g. picknplace) ──────────────────────────────────────
  if [[ -n "$CONF_TASK_PATTERN" ]]; then
    CURRENT_TASKS=$(grep -c "$CONF_TASK_PATTERN" "$LAUNCH_LOG" 2>/dev/null || true)
    CURRENT_TASKS=$(( ${CURRENT_TASKS:-0} + 0 ))
    while [[ "$TASK_COUNT" -lt "$CURRENT_TASKS" ]]; do
      TASK_COUNT=$(( TASK_COUNT + 1 ))
      echo "  ✔ Task #${TASK_COUNT} complete at $(date '+%H:%M:%S')"
    done
  fi

  # ── Done-pattern stop (e.g. picknplace "ARM2 at standby") ────────────────
  if [[ -n "$CONF_DONE_PATTERN" ]]; then
    if grep -qE "$CONF_DONE_PATTERN" "$LAUNCH_LOG" 2>/dev/null; then
      DONE_COMPLETE=1
      echo "  ✅ DONE: detected at $(date '+%H:%M:%S') (${ELAPSED}s)"
      break
    fi
  fi

  # ── Goal-count stop ───────────────────────────────────────────────────────
  [[ "$GOAL_TARGET" -gt 0 && "$GOAL_COUNT" -ge "$GOAL_TARGET" ]] \
    && { echo "All ${GOAL_TARGET} goal(s) reached — stopping."; break; }

  # ── Timeout stop ──────────────────────────────────────────────────────────
  [[ "$MAX_TIMEOUT" -gt 0 && "$ELAPSED" -ge "$MAX_TIMEOUT" ]] \
    && { echo "Timeout: ${MAX_TIMEOUT}s elapsed (goals: ${GOAL_COUNT})."; break; }
done

# Restore default SIGINT handling now that we're past the wait loop, so a
# further Ctrl-C (e.g. at the analysis menu prompt) behaves normally.
trap - SIGINT

ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "--- Summary ---"
[[ -n "$CONF_GOAL_PATTERN" ]] && echo "  Goals reached   : $GOAL_COUNT"
[[ -n "$CONF_TASK_PATTERN" ]] && echo "  Tasks completed : $TASK_COUNT"
[[ -n "$CONF_DONE_PATTERN" ]] && \
  echo "  Demo complete   : $([ $DONE_COMPLETE -eq 1 ] && echo yes || echo no)"
echo "  Elapsed         : ${ELAPSED}s"

# ── Post-run log analysis (scenario-specific, e.g. analyze_fastmapping_log) ──
if [[ -n "${CONF_POST_RUN_CMD:-}" ]]; then
  echo ""
  echo "[5/6] Post-Run Analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  _post_cmd="${CONF_POST_RUN_CMD//SESSION_DIR/$SESSION_DIR}"
  echo "  Running: $_post_cmd"
  eval "$_post_cmd" || echo "  ⚠ Post-run analysis failed (exit $?)"
fi

# ── Analysis functions ────────────────────────────────────────────────────────
# _run_trigger_analysis, _run_kpi_export, _run_e2e_analysis, _run_resource_summary,
# and _show_analysis_menu are defined in _session_menu.sh (sourced above), shared
# with bench_menu.sh so both callers stay in sync.


# Stop the monitor so it flushes CSV + topology before we read them
if [[ "$MONITOR_PID" -gt 0 ]]; then
  kill -SIGTERM "$MONITOR_PID" 2>/dev/null || true
  sleep 2
  MONITOR_PID=0
fi

# Shut down simulation and bag recorder fully before showing the menu so the
# user sees a clean prompt on a completed session (not a live one).
echo ""
echo "Shutting down..."
if [[ "$RECORD_PID" -gt 0 ]]; then
  kill -SIGINT "$RECORD_PID" 2>/dev/null || true
  echo "  Waiting for bag recorder to flush (max 15s)..."
  for _i in $(seq 1 15); do
    kill -0 "$RECORD_PID" 2>/dev/null || break
    sleep 1
  done
  kill -SIGKILL "$RECORD_PID" 2>/dev/null || true
  RECORD_PID=0
fi
if [[ "$LAUNCH_PID" -gt 0 ]]; then
  kill -SIGINT  -- -"$LAUNCH_PID" 2>/dev/null || true
  kill -SIGINT         "$LAUNCH_PID" 2>/dev/null || true
  sleep 2
  kill -SIGKILL -- -"$LAUNCH_PID" 2>/dev/null || true
  kill -SIGKILL        "$LAUNCH_PID" 2>/dev/null || true
  LAUNCH_PID=0
fi
sleep 1
_pkill_sweep -SIGINT
sleep 2
_pkill_sweep -SIGKILL
echo "  Done."

# ── Bag reindex safety-net ────────────────────────────────────────────────────
# Must run after the recorder above has actually stopped and flushed — running
# this while the recorder is still writing produces a stale/incomplete
# metadata.yaml that then blocks this check from re-running later, even after
# the bag is fully flushed (causing KPI export below to read partial data).
if [[ "$RECORD_MODE" -eq 1 && -d "$SESSION_DIR/bag" && ! -f "$SESSION_DIR/bag/metadata.yaml" ]]; then
  echo ""
  echo "  ⚠ Bag metadata missing — reindexing..."
  ros2 bag reindex "$SESSION_DIR/bag" 2>&1 | grep -v '^\[INFO\]' || true
fi

# Manual shutdown is complete — disable the EXIT trap so _cleanup doesn't
# run again (which would duplicate "Shutting down..." output and sleeps).
trap - EXIT

if [[ "$NO_PROMPT" -eq 1 ]]; then
  # Non-interactive (CI / --no-prompt): silently write kpi.json if bag exists
  if [[ "$RECORD_MODE" -eq 1 && -d "$SESSION_DIR/bag" ]]; then
    _run_kpi_export "$SESSION_DIR"
  fi
else
  echo ""
  echo "[6/6] Post-Run Analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  _show_analysis_menu "$SESSION_DIR"
  echo ""
  for _choice in "${_MENU_CHOICES[@]}"; do
    case "$_choice" in
      trigger)   _run_trigger_analysis "$SESSION_DIR" ;;
      kpi)       echo ""; _run_kpi_export "$SESSION_DIR" ;;
      e2e)       echo ""; _run_e2e_analysis "$SESSION_DIR" ;;
      resources) echo ""; _run_resource_summary "$SESSION_DIR" ;;
      results)   echo ""; _run_results "$SESSION_DIR" "$REPO_ROOT" ;;
    esac
  done
fi

# ── Auto-open results (--show flag) ──────────────────────────────────────────
if [[ "$SHOW_MODE" -eq 1 ]]; then
  echo ""
  echo "Auto-opening results (--show)..."
  _run_results "$SESSION_DIR" "$REPO_ROOT"
fi
