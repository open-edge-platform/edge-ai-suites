#!/usr/bin/env bash
# Stop RTSP pushers (and mediamtx) started by start-streams.sh.
#
# Usage:
#   ./stop_streams.sh                 # stop every running stream + mediamtx
#   ./stop_streams.sh cam_fridge ...  # stop only the named streams
#   ./stop_streams.sh --status        # show running PIDs
#
# Reads PID files under .run/ (written by start-streams.sh).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$SCRIPT_DIR/.run"

if [[ ! -d "$RUN_DIR" ]]; then
  echo "no run dir: $RUN_DIR (nothing to stop)"
  exit 0
fi

stop_one() {
  local sid="$1"
  local pidfile="$RUN_DIR/$sid.pid"
  [[ -f "$pidfile" ]] || { echo "  no pidfile for $sid"; return 0; }
  local pid
  pid="$(cat "$pidfile")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    echo "stopped $sid (pid $pid)"
  else
    echo "  $sid not running (stale pidfile)"
  fi
  rm -f "$pidfile"
}

cmd_status() {
  shopt -s nullglob
  local any=0
  for pidfile in "$RUN_DIR"/*.pid; do
    any=1
    local sid pid
    sid="$(basename "$pidfile" .pid)"
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "  $sid	pid=$pid	running"
    else
      echo "  $sid	pid=$pid	dead (stale pidfile)"
    fi
  done
  [[ $any -eq 0 ]] && echo "  (no pidfiles in $RUN_DIR)"
}

# Argument parsing
case "${1:-}" in
  --status) cmd_status; exit 0 ;;
  -h|--help)
    sed -n '2,10p' "$0"
    exit 0 ;;
esac

# Optional positional filter: only stop these stream IDs
declare -A WANTED=()
for arg in "$@"; do WANTED["$arg"]=1; done
filter_active=$(( ${#WANTED[@]} > 0 ))

stopped=0
shopt -s nullglob

if (( filter_active )); then
  # Stop only the named streams (leave mediamtx alone).
  for sid in "${!WANTED[@]}"; do
    stop_one "$sid"
    stopped=$((stopped+1))
  done
else
  # Stop every stream, then mediamtx last so pushers disconnect cleanly.
  for pidfile in "$RUN_DIR"/*.pid; do
    sid="$(basename "$pidfile" .pid)"
    [[ "$sid" == "_mediamtx" ]] && continue
    stop_one "$sid"
    stopped=$((stopped+1))
  done
  [[ -f "$RUN_DIR/_mediamtx.pid" ]] && stop_one "_mediamtx"
fi

echo
echo "summary: stopped=$stopped"
