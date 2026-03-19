#!/bin/bash
# compare_runs.sh  —  Run all 4 sim permutations back-to-back and print a
#                     side-by-side comparison of throttling / performance metrics.
#
# Permutations:
#   1. Headless + stock world  (RTF cap = 1, ODE iters = 150)
#   2. Headless + fast world   (RTF cap = 3, ODE iters = 50)
#   3. GUI      + stock world  (RTF cap = 1, ODE iters = 150)
#   4. GUI      + fast world   (RTF cap = 3, ODE iters = 50)
#
# Usage:
#   bash src/compare_runs.sh [--goals N] [--timeout SECS] [--skip-gui] [--analyze]
#
#   --goals   N    Goals per run (default: 3)
#   --timeout N    Per-run hard timeout in seconds (default: 75)
#   --skip-gui     Only run the 2 headless permutations (saves time)
#   --analyze      Run graph monitor + trigger-latency analysis during each run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$SCRIPT_DIR"
[[ "$(basename "$REPO_ROOT")" == "src" ]] && REPO_ROOT="$(dirname "$REPO_ROOT")"

WANDERING="$REPO_ROOT/src/wandering_run.sh"
STOCK_WORLD="/opt/ros/jazzy/share/turtlebot3_gazebo/worlds/turtlebot3_world.world"

GOALS=3
TIMEOUT=75
SKIP_GUI=0
ANALYZE_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --goals)    GOALS="$2";   shift 2 ;;
    --timeout)  TIMEOUT="$2"; shift 2 ;;
    --skip-gui) SKIP_GUI=1;   shift ;;
    --analyze)  ANALYZE_FLAG="--analyze"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

OUT_DIR="$REPO_ROOT/throttling_check/$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$OUT_DIR"

HL_STOCK_LOG="$OUT_DIR/headless_stock.log"
HL_FAST_LOG="$OUT_DIR/headless_fast.log"
GUI_STOCK_LOG="$OUT_DIR/gui_stock.log"
GUI_FAST_LOG="$OUT_DIR/gui_fast.log"

_cleanup_between() {
  echo ""
  echo "── Waiting 20s for ROS nodes to fully shut down... ──────────"
  sleep 20
  echo ""
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  4-Permutation Throttling Comparison                         ║"
printf "║  Goals: %-3s   Timeout: %-3ss per run                       ║\n" "$GOALS" "$TIMEOUT"
if [[ "$SKIP_GUI" -eq 1 ]]; then
echo "║  Mode: headless only (--skip-gui)                            ║"
fi
if [[ -n "$ANALYZE_FLAG" ]]; then
echo "║  Analysis: trigger-latency enabled (--analyze)               ║"
fi
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Run 1: Headless + stock world ────────────────────────────────────────────
echo "━━━━ RUN 1/4: HEADLESS + STOCK WORLD (RTF=1, iters=150) ━━━━━━"
bash "$WANDERING" --goals "$GOALS" --timeout "$TIMEOUT" \
  --world "$STOCK_WORLD" $ANALYZE_FLAG 2>&1 | tee "$HL_STOCK_LOG" || true
_cleanup_between

# ── Run 2: Headless + fast world ───────────────────────────────────────────────
echo "━━━━ RUN 2/4: HEADLESS + FAST WORLD (RTF=3, iters=50) ━━━━━━━━"
bash "$WANDERING" --goals "$GOALS" --timeout "$TIMEOUT" \
  $ANALYZE_FLAG 2>&1 | tee "$HL_FAST_LOG" || true

if [[ "$SKIP_GUI" -eq 0 ]]; then
  _cleanup_between

  # ── Run 3: GUI + stock world ────────────────────────────────────────────────
  echo "━━━━ RUN 3/4: GUI + STOCK WORLD (RTF=1, iters=150) ━━━━━━━━━━"
  bash "$WANDERING" --goals "$GOALS" --timeout "$TIMEOUT" \
    --gui --system-launch $ANALYZE_FLAG 2>&1 | tee "$GUI_STOCK_LOG" || true
  _cleanup_between

  # ── Run 4: GUI + fast world ─────────────────────────────────────────────────
  echo "━━━━ RUN 4/4: GUI + FAST WORLD (RTF=3, iters=50) ━━━━━━━━━━━━"
  bash "$WANDERING" --goals "$GOALS" --timeout "$TIMEOUT" \
    --gui $ANALYZE_FLAG 2>&1 | tee "$GUI_FAST_LOG" || true
fi

echo ""

# ── Build label:path args for wandering_metrics.py ───────────────────────────
COMPARE_ARGS=(
  "Headless+Stock:$HL_STOCK_LOG"
  "Headless+Fast:$HL_FAST_LOG"
)
if [[ "$SKIP_GUI" -eq 0 ]]; then
  COMPARE_ARGS+=(
    "GUI+Stock:$GUI_STOCK_LOG"
    "GUI+Fast:$GUI_FAST_LOG"
  )
fi

python3 "$REPO_ROOT/src/wandering_metrics.py" compare \
  "${COMPARE_ARGS[@]}" "$OUT_DIR"
