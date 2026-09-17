#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
# _session_menu.sh — Shared post-run session analysis functions.
#
# Sourced by both benchmark_runner.sh (shown automatically right after a
# single run completes) and bench_menu.sh (used to browse/re-analyze runs
# on demand, including single-run sessions and multi-run bench_* sweeps).
# Keeping this logic in one place avoids the two callers drifting apart
# (e.g. one passing a CLI flag the other's target script doesn't support).
#
# Requires SCRIPT_DIR and _PYTHON to be set by the sourcing script (SCRIPT_DIR
# is the directory containing the *.py analysis scripts; _PYTHON is the
# "uv run python" / "python3" runner, so this still works on systems without
# uv installed). PLOT_MODE and NO_PROMPT are optional and default to 0 when
# unset.

: "${PLOT_MODE:=0}"
: "${NO_PROMPT:=0}"

# _run_trigger_analysis SESSION_DIR
#   Print live trigger-latency summary from graph_timing.csv.
#   Returns 1 if required monitor data is missing.
_run_trigger_analysis() {
  local _sess="$1"
  if [[ ! -f "$_sess/graph_timing.csv" || ! -f "$_sess/graph_topology.json" ]]; then
    echo "  ⚠ Monitor data missing (graph_timing.csv or graph_topology.json not found)"
    echo "    Session dir: $_sess"
    return 1
  fi
  local _plot_args=()
  [[ "$PLOT_MODE" -eq 1 ]] && _plot_args+=("--plot" "--no-show")
  $_PYTHON "$SCRIPT_DIR/analyze_trigger_latency.py" \
    --session "$_sess" \
    --summary-only \
    "${_plot_args[@]}"
  echo ""
  echo "  Full detail:"
  echo "    $_PYTHON src/analyze_trigger_latency.py --session $_sess"
}

# _run_kpi_export SESSION_DIR
#   Run bag-based KPI analysis and write kpi.json.
#   Returns 1 if no bag/ directory exists.
_run_kpi_export() {
  local _sess="$1"
  local _bag_dir="$_sess/bag"
  if [[ ! -d "$_bag_dir" ]]; then
    echo "  ⚠ No bag/ directory — run with --record to enable KPI export"
    return 1
  fi
  # Copy topology so --bag mode works without a --topology flag
  [[ -f "$_sess/graph_topology.json" ]] && \
    cp "$_sess/graph_topology.json" "$_bag_dir/graph_topology.json"
  local _plot_args=()
  [[ "$PLOT_MODE" -eq 1 ]] && _plot_args+=("--plot" "--no-show")
  local _table_args=()
  [[ "${NO_PROMPT:-0}" -eq 1 ]] && _table_args+=("--no-table")
  if [[ "${NO_PROMPT:-0}" -eq 0 ]]; then
    echo "  Bag analysis:"
    echo "    $_PYTHON src/analyze_trigger_latency.py --bag $_bag_dir"
    echo ""
    echo "  Running bag-based KPI analysis (for benchmark aggregation)..."
  fi
  if [[ "${NO_PROMPT:-0}" -eq 1 ]]; then
    $_PYTHON "$SCRIPT_DIR/analyze_trigger_latency.py" \
      --bag "$_bag_dir" \
      --summary-only \
      --json-out "$_sess/kpi.json" \
      "${_plot_args[@]}" "${_table_args[@]}" >/dev/null 2>&1 || \
      echo "  ⚠ Bag analysis failed (bag may still be flushing)"
  else
    $_PYTHON "$SCRIPT_DIR/analyze_trigger_latency.py" \
      --bag "$_bag_dir" \
      --summary-only \
      --json-out "$_sess/kpi.json" \
      "${_plot_args[@]}" "${_table_args[@]}" 2>/dev/null || \
      echo "  ⚠ Bag analysis failed (bag may still be flushing)"
  fi
}

# _run_e2e_analysis SESSION_DIR
#   Run end-to-end bag latency analysis via analyze_bag_e2e.py.
#   Returns 1 if no bag/ directory exists.
_run_e2e_analysis() {
  local _sess="$1"
  local _bag_dir="$_sess/bag"
  if [[ ! -d "$_bag_dir" ]]; then
    echo "  ⚠ No bag/ directory — run with --record to enable E2E analysis"
    return 1
  fi
  echo "  E2E pipeline latency:"
  $_PYTHON "$SCRIPT_DIR/analyze_bag_e2e.py" --bag "$_bag_dir" || \
    echo "  ⚠ E2E analysis failed"
  echo ""
  echo "  Full detail:"
  echo "    $_PYTHON src/analyze_bag_e2e.py --bag $_bag_dir"
}

# _run_resource_summary SESSION_DIR
#   Print resource usage summary from resource_usage.json in the session.
#   Returns 1 if no resource_usage.json is found.
_run_resource_summary() {
  local _sess="$1"
  if [[ ! -f "$_sess/resource_usage.json" ]]; then
    echo "  ⚠ No resource_usage.json found in session"
    return 1
  fi
  $_PYTHON "$SCRIPT_DIR/visualize_resources.py" \
    "$_sess/resource_usage.json" \
    --summary || \
    echo "  ⚠ Resource summary failed"
}

# _run_results SESSION_DIR REPO_ROOT
#   Open the KPI charts + HTML report for a session via `make results`.
_run_results() {
  local _sess="$1"
  local _repo_root="$2"
  make -C "$_repo_root" results SESSION="$_sess" 2>/dev/null || \
    echo "  ⚠ make results failed — open manually: $_sess/report.html"
}

# _show_analysis_menu SESSION_DIR
#   Print an interactive numbered menu of available analyses and read the
#   user's selection.  Populates the _MENU_CHOICES global array with the
#   keys of the selected options.  Defaults to all available options if
#   the user presses Enter without typing anything.
_show_analysis_menu() {
  local _sess="$1"
  local -a _keys=()
  local -a _labels=()

  [[ -f "$_sess/graph_timing.csv" && -f "$_sess/graph_topology.json" ]] && \
    _keys+=("trigger")   && _labels+=("Trigger-latency node summary")

  [[ -d "$_sess/bag" ]] && \
    _keys+=("kpi")       && _labels+=("KPI export  ->  kpi.json")

  [[ -d "$_sess/bag" ]] && \
    _keys+=("e2e")       && _labels+=("E2E pipeline latency (bag)")

  [[ -f "$_sess/resource_usage.json" ]] && \
    _keys+=("resources") && _labels+=("Resource usage charts")

  # Results (charts + HTML report) is always available once the session exists
  _keys+=("results") && _labels+=("Open results  (KPI charts + HTML report)")

  if [[ ${#_keys[@]} -eq 0 ]]; then
    echo "  (no analysis data found in session)"
    _MENU_CHOICES=()
    return
  fi

  echo "  Available analyses (Enter = all, or type numbers space-separated):"
  local i
  for (( i=0; i<${#_keys[@]}; i++ )); do
    printf "    %d) %s\n" "$((i+1))" "${_labels[$i]}"
  done
  printf "    0) Skip\n"
  printf "\n  Select [all]: "

  local _input
  read -r _input

  if [[ "$_input" == "0" ]]; then
    _MENU_CHOICES=()
  elif [[ -z "$_input" || "$_input" == "all" ]]; then
    _MENU_CHOICES=("${_keys[@]}")
  else
    _MENU_CHOICES=()
    local _num
    for _num in $_input; do
      if ! [[ "$_num" =~ ^[0-9]+$ ]]; then
        echo "  ⚠ Ignoring invalid option: $_num"
        continue
      fi
      local _idx=$(( _num - 1 ))
      if [[ $_idx -ge 0 && $_idx -lt ${#_keys[@]} ]]; then
        _MENU_CHOICES+=("${_keys[$_idx]}")
      else
        echo "  ⚠ Ignoring unknown option: $_num"
      fi
    done
  fi
}
