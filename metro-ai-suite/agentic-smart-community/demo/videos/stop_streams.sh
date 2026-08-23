#!/usr/bin/env bash
# Stop RTSP pushers (and mediamtx) started by start-streams.sh.
#
# Usage:
#   ./stop_streams.sh                 # stop every running stream + mediamtx
#   ./stop_streams.sh cam_fridge ...  # stop only the named streams
#   ./stop_streams.sh --status        # show running PIDs
#
# Uses PID files under .run/ when present. If an interrupted prior shutdown
# removed them, it also finds this user's ffmpeg publishers by the RTSP URLs in
# streams.yaml and this user's MediaMTX by its generated configuration path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$SCRIPT_DIR/.run"
CONFIG_FILE="${STREAMS_CONFIG:-$SCRIPT_DIR/../quick-start/streams.yaml}"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

declare -A STREAM_URLS=()

load_stream_urls() {
  local python="python3" output sid url
  [[ -x "$VENV_PYTHON" ]] && python="$VENV_PYTHON"
  [[ -f "$CONFIG_FILE" ]] || {
    echo "warning: streams config not found: $CONFIG_FILE" >&2
    return 1
  }
  if ! output="$("$python" - "$CONFIG_FILE" <<'PY'
import sys

import yaml

with open(sys.argv[1], encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}
for stream_id, stream in (config.get("streams") or {}).items():
    url = stream.get("rtsp_url")
    if url:
        print(f"{stream_id}\x1f{url}")
PY
  )"; then
    echo "warning: could not read stream URLs from $CONFIG_FILE" >&2
    return 1
  fi
  while IFS=$'\x1f' read -r sid url; do
    [[ -n "$sid" && -n "$url" ]] && STREAM_URLS["$sid"]="$url"
  done <<<"$output"
}

is_stream_pid() {
  local pid="$1" url="$2" command
  command="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  [[ "$command" == *"ffmpeg"* && "$command" == *"-f rtsp"* && \
     "$command" == *"$url"* ]]
}

find_stream_pids() {
  local url="$1" pid command
  while read -r pid command; do
    [[ "$command" == *"ffmpeg"* && "$command" == *"-f rtsp"* && \
       "$command" == *"$url"* ]] && printf '%s\n' "$pid"
  done < <(ps -u "$(id -u)" -o pid=,args=)
}

is_mediamtx_pid() {
  local pid="$1" command
  command="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  [[ "$command" == *"mediamtx"* && "$command" == *"$RUN_DIR/_mediamtx.yml"* ]]
}

find_mediamtx_pids() {
  local pid command
  while read -r pid command; do
    [[ "$command" == *"mediamtx"* && "$command" == *"$RUN_DIR/_mediamtx.yml"* ]] && \
      printf '%s\n' "$pid"
  done < <(ps -u "$(id -u)" -o pid=,args=)
}

stop_pid() {
  local pid="$1"
  kill -TERM "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.2
  done
  kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
}

stop_one() {
  local sid="$1"
  local pidfile="$RUN_DIR/$sid.pid"
  local pid url="${STREAM_URLS[$sid]:-}"
  declare -A candidate_pids=()

  if [[ -z "$url" ]]; then
    echo "  no configured RTSP URL for $sid; skipped fallback lookup" >&2
  else
    if [[ -f "$pidfile" ]]; then
      pid="$(cat "$pidfile")"
      is_stream_pid "$pid" "$url" && candidate_pids["$pid"]=1
    fi
    while read -r pid; do
      [[ -n "$pid" ]] && candidate_pids["$pid"]=1
    done < <(find_stream_pids "$url")
  fi

  if (( ${#candidate_pids[@]} == 0 )); then
    echo "  no running publisher for $sid"
  else
    for pid in "${!candidate_pids[@]}"; do
      stop_pid "$pid"
      echo "stopped $sid (pid $pid)"
    done
  fi
  rm -f "$pidfile"
}

stop_mediamtx() {
  local pidfile="$RUN_DIR/_mediamtx.pid" pid
  declare -A candidate_pids=()
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    is_mediamtx_pid "$pid" && candidate_pids["$pid"]=1
  fi
  while read -r pid; do
    [[ -n "$pid" ]] && candidate_pids["$pid"]=1
  done < <(find_mediamtx_pids)

  for pid in "${!candidate_pids[@]}"; do
    stop_pid "$pid"
    echo "stopped _mediamtx (pid $pid)"
  done
  rm -f "$pidfile"
}

load_stream_urls || true

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

case "${1:-}" in
  --status) cmd_status; exit 0 ;;
  -h|--help)
    sed -n '2,10p' "$0"
    exit 0
    ;;
esac

# Optional positional filter: only stop these stream IDs
declare -A WANTED=()
for arg in "$@"; do WANTED["$arg"]=1; done
filter_active=$(( ${#WANTED[@]} > 0 ))

stopped=0
if (( filter_active )); then
  # Stop only the named streams (leave mediamtx alone).
  for sid in "${!WANTED[@]}"; do
    stop_one "$sid"
    stopped=$((stopped+1))
  done
else
  # Stop every configured stream, then mediamtx last so pushers disconnect cleanly.
  for sid in "${!STREAM_URLS[@]}"; do
    stop_one "$sid"
    stopped=$((stopped+1))
  done
  stop_mediamtx
fi

echo
echo "summary: stopped=$stopped"
