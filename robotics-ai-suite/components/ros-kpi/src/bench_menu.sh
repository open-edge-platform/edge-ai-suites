#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# bench_menu.sh  BENCH_DIR  [REPO_ROOT]
#   Interactive post-benchmark menu.  Shows after all runs complete, letting
#   the user inspect the benchmark summary or drill into individual runs.
set -euo pipefail

BENCH_DIR="${1:?Usage: bench_menu.sh BENCH_DIR [REPO_ROOT]}"
REPO_ROOT="${2:-$(cd "$(dirname "$0")/.." && pwd)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
_PYTHON=$(command -v uv >/dev/null 2>&1 && echo "uv run python" || echo "python3")

# shellcheck source=./_session_menu.sh disable=SC1091
source "$SCRIPT_DIR/_session_menu.sh"

# ── Per-run submenu ────────────────────────────────────────────────────────
# _run_submenu SESSION_DIR
#   Show analysis options for a single session and execute the selection.
#   Reuses _show_analysis_menu + the _run_* functions from _session_menu.sh —
#   the same ones benchmark_runner.sh's inline post-run menu uses — so a
#   single-run session can be (re-)analyzed on demand after the fact without
#   the two menus drifting apart.
_run_submenu() {
  local _sess="$1"
  echo ""
  echo "  ── $(basename "$_sess") ──"
  _show_analysis_menu "$_sess"

  for _rchoice in "${_MENU_CHOICES[@]}"; do
    case "$_rchoice" in
      trigger)   echo ""; _run_trigger_analysis "$_sess" ;;
      kpi)       echo ""; _run_kpi_export "$_sess" ;;
      e2e)       echo ""; _run_e2e_analysis "$_sess" ;;
      resources) echo ""; _run_resource_summary "$_sess" ;;
      results)   echo ""; _run_results "$_sess" "$REPO_ROOT" ;;
    esac
  done
}

# ── Single-run vs. multi-run sweep detection ────────────────────────────────
# A single-run session directory has its own session_info.txt written directly
# by monitor_stack.py's setup(); a bench_* sweep directory does not (only its
# per-run subdirectories do). If BENCH_DIR is itself a single-run session,
# skip straight to the per-run submenu instead of misinterpreting its
# subdirectories (bag/, visualizations/) as separate benchmark runs.
if [[ -f "$BENCH_DIR/session_info.txt" ]]; then
  echo ""
  echo "  ℹ  $BENCH_DIR looks like a single-run session, not a benchmark sweep."
  echo "     Showing the single-run analysis menu instead."
  _run_submenu "$BENCH_DIR"
  echo ""
  exit 0
fi

# ── Collect session dirs ───────────────────────────────────────────────────
# Avoid `find -exec test -f '{}/session_info.txt'`: {} substitution inside a
# larger argument (rather than as a standalone token) isn't portable across
# find implementations and can silently match nothing.
declare -a _SESSIONS=()
while IFS= read -r -d '' _dir; do
  [[ -f "$_dir/session_info.txt" ]] && _SESSIONS+=("$_dir")
done < <(find "$BENCH_DIR" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

if [[ ${#_SESSIONS[@]} -eq 0 ]]; then
  echo "  (no session directories found in $BENCH_DIR)"
  exit 0
fi

# ── Main menu ──────────────────────────────────────────────────────────────
declare -a _KEYS=("summary" "e2e" "runs")
declare -a _LABELS=(
  "Benchmark summary table  (all runs)"
  "E2E pipeline latency     (all runs)"
  "Browse individual runs  →"
)

echo ""
echo "▶  Post-benchmark analysis ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Available (Enter = all, or type numbers space-separated):"
for (( i=0; i<${#_KEYS[@]}; i++ )); do
  printf "    %d) %s\n" "$((i+1))" "${_LABELS[$i]}"
done
printf "    0) Skip\n"
printf "\n  Select [all]: "

read -r _input

declare -a _CHOICES=()
if [[ "$_input" == "0" ]]; then
  _CHOICES=()
elif [[ -z "$_input" || "$_input" == "all" ]]; then
  _CHOICES=("${_KEYS[@]}")
else
  for _num in $_input; do
    _idx=$(( _num - 1 ))
    if [[ $_idx -ge 0 && $_idx -lt ${#_KEYS[@]} ]]; then
      _CHOICES+=("${_KEYS[$_idx]}")
    else
      echo "  ⚠ Ignoring unknown option: $_num"
    fi
  done
fi

# ── Dispatch ───────────────────────────────────────────────────────────────
for _choice in "${_CHOICES[@]}"; do
  case "$_choice" in

    summary)
      echo ""
      $_PYTHON "$SCRIPT_DIR/summarize_benchmark.py" "$BENCH_DIR"
      ;;

    e2e)
      echo ""
      _has_e2e=0
      for _sess in "${_SESSIONS[@]}"; do
        _kpi="$_sess/kpi.json"
        if [[ -d "$_sess/bag" && -f "$_kpi" ]]; then
          echo "  → $(basename "$_sess")"
          $_PYTHON "$SCRIPT_DIR/analyze_bag_e2e.py" \
            --bag "$_sess/bag" \
            --kpi "$_kpi" || true
          _has_e2e=1
        fi
      done
      [[ "$_has_e2e" -eq 0 ]] && echo "  (no bag data found for E2E analysis)"
      ;;

    runs)
      # ── Run picker submenu ───────────────────────────────────────────────
      echo ""
      echo "  Select a run:"
      for (( i=0; i<${#_SESSIONS[@]}; i++ )); do
        printf "    %d) %s\n" "$((i+1))" "$(basename "${_SESSIONS[$i]}")"
      done
      printf "\n  Run number (0 to cancel): "

      read -r _run_input
      if [[ -z "$_run_input" || "$_run_input" == "0" ]]; then
        continue
      fi
      _run_idx=$(( _run_input - 1 ))
      if [[ $_run_idx -ge 0 && $_run_idx -lt ${#_SESSIONS[@]} ]]; then
        _run_submenu "${_SESSIONS[$_run_idx]}"
        # Offer to inspect another run
        while true; do
          echo ""
          printf "  Inspect another run? (run number or Enter to finish): "
          read -r _again
          [[ -z "$_again" ]] && break
          _again_idx=$(( _again - 1 ))
          if [[ $_again_idx -ge 0 && $_again_idx -lt ${#_SESSIONS[@]} ]]; then
            _run_submenu "${_SESSIONS[$_again_idx]}"
          else
            echo "  ⚠ Invalid run number"
          fi
        done
      else
        echo "  ⚠ Invalid run number: $_run_input"
      fi
      ;;

  esac
done

echo ""
